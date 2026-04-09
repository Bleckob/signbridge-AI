// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act, cleanup } from "@testing-library/react";
import { float32ToInt16, sendChunked } from "./AudioCapture";

describe("float32ToInt16", () => {
  it("converts silence to silence", () => {
    expect(Array.from(float32ToInt16(new Float32Array([0,0,0])))).toEqual([0,0,0]);
  });
  it("converts +1.0 to 32767", () => {
    expect(float32ToInt16(new Float32Array([1.0]))[0]).toBe(32767);
  });
  it("converts -1.0 to -32768", () => {
    expect(float32ToInt16(new Float32Array([-1.0]))[0]).toBe(-32768);
  });
  it("clamps values above 1.0", () => {
    expect(float32ToInt16(new Float32Array([5.0]))[0]).toBe(32767);
  });
  it("returns Int16Array", () => {
    expect(float32ToInt16(new Float32Array([0.5]))).toBeInstanceOf(Int16Array);
  });
  it("output length equals input length", () => {
    expect(float32ToInt16(new Float32Array(4000)).length).toBe(4000);
  });
});

describe("sendChunked", () => {
  let socket;
  beforeEach(() => {
    socket = { readyState: WebSocket.OPEN, send: vi.fn() };
  });

  it("returns 0 when socket is null", () => {
    expect(sendChunked(new Float32Array(4000), null)).toBe(0);
  });
  it("returns 0 when socket not open", () => {
    socket.readyState = 0;
    expect(sendChunked(new Float32Array(4000), socket)).toBe(0);
  });
  it("sends 1 chunk for 4000 samples", () => {
    expect(sendChunked(new Float32Array(4000), socket)).toBe(1);
    expect(socket.send).toHaveBeenCalledTimes(1);
  });
  it("sends 4 chunks for 16000 samples", () => {
    expect(sendChunked(new Float32Array(16000), socket)).toBe(4);
  });
  it("pads and sends last chunk when audio is not multiple of 4000", () => {
    expect(sendChunked(new Float32Array(4500), socket)).toBe(2);
  });
  it("each message is an ArrayBuffer", () => {
    sendChunked(new Float32Array(4000), socket);
    expect(socket.send.mock.calls[0][0]).toBeInstanceOf(ArrayBuffer);
  });
  it("each chunk is 8000 bytes", () => {
    sendChunked(new Float32Array(8000), socket);
    socket.send.mock.calls.forEach(([buf]) => expect(buf.byteLength).toBe(8000));
  });
});

describe("AudioCapture UI", () => {
  beforeEach(() => {
    Object.defineProperty(global.navigator, "mediaDevices", {
      writable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: vi.fn() }],
        }),
      },
    });
    global.AudioContext = vi.fn().mockImplementation(() => ({
      createMediaStreamSource: vi.fn().mockReturnValue({ connect: vi.fn() }),
      createAnalyser: vi.fn().mockReturnValue({
        fftSize: 256,
        frequencyBinCount: 128,
        connect: vi.fn(),
        disconnect: vi.fn(),
        getByteTimeDomainData: vi.fn(),
      }),
      close: vi.fn(),
    }));
    global.WebSocket = vi.fn().mockImplementation(() => ({
      binaryType: "",
      readyState: 0,
      send: vi.fn(),
      close: vi.fn(),
      onopen: null,
      onclose: null,
      onerror: null,
    }));
    global.WebSocket.OPEN = 1;
    global.WebSocket.CONNECTING = 0;
    global.requestAnimationFrame = vi.fn((cb) => { cb(); return 1; });
    global.cancelAnimationFrame  = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows Ready on load", async () => {
    const { default: AC } = await import("./AudioCapture");
    render(<AC />);
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("shows Start recording button", async () => {
    const { default: AC } = await import("./AudioCapture");
    render(<AC />);
    expect(screen.getByRole("button", { name: "Start recording" })).toBeInTheDocument();
  });

  it("requests mic when Start clicked", async () => {
    const { default: AC } = await import("./AudioCapture");
    render(<AC />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    });
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalled();
  });

  it("shows error when mic denied", async () => {
    navigator.mediaDevices.getUserMedia = vi.fn().mockRejectedValue(
      Object.assign(new Error(), { name: "NotAllowedError" })
    );
    const { default: AC } = await import("./AudioCapture");
    render(<AC />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    });
    await waitFor(() =>
      expect(screen.getByText(/microphone access denied/i)).toBeInTheDocument()
    );
  });

  it("shows Try again after error", async () => {
    navigator.mediaDevices.getUserMedia = vi.fn().mockRejectedValue(
      Object.assign(new Error(), { name: "NotAllowedError" })
    );
    const { default: AC } = await import("./AudioCapture");
    render(<AC />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Start recording" }));
    });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument()
    );
  });

  it("shows format pills", async () => {
    const { default: AC } = await import("./AudioCapture");
    render(<AC />);
    expect(screen.getAllByText("16 kHz").length).toBeGreaterThan(0);
    expect(screen.getAllByText("ONNX VAD").length).toBeGreaterThan(0);
  });
});