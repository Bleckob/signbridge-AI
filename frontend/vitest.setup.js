import "@testing-library/jest-dom";
import { vi } from "vitest";

global.WebSocket = vi.fn().mockImplementation(() => ({
  binaryType:"", readyState:0, send:vi.fn(), close:vi.fn(), onopen:null, onclose:null, onerror:null,
}));
global.WebSocket.CONNECTING = 0;
global.WebSocket.OPEN       = 1;
global.WebSocket.CLOSING    = 2;
global.WebSocket.CLOSED     = 3;

global.AudioContext = vi.fn().mockImplementation(() => ({
  sampleRate: 48000,
  createMediaStreamSource: vi.fn().mockReturnValue({ connect: vi.fn() }),
  createAnalyser: vi.fn().mockReturnValue({
    fftSize:256, frequencyBinCount:128,
    connect:vi.fn(), disconnect:vi.fn(),
    getByteTimeDomainData: vi.fn((arr) => arr.fill(128)),
  }),
  close: vi.fn().mockResolvedValue(undefined),
}));
global.window.AudioContext = global.AudioContext;

Object.defineProperty(global.navigator, "mediaDevices", {
  writable: true,
  value: {
    getUserMedia: vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn(), kind: "audio" }],
    }),
  },
});

global.requestAnimationFrame = vi.fn((cb) => setTimeout(() => cb(performance.now()), 16));
global.cancelAnimationFrame  = vi.fn((id) => clearTimeout(id));

vi.mock("@ricky0123/vad-web", () => ({
  MicVAD: { new: vi.fn().mockResolvedValue({ start: vi.fn(), pause: vi.fn() }) },
}));