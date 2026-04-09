// AudioCapture.jsx — SignBridge AI | Task 01
// Owner: Confidence

import { useState, useRef, useCallback, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";

// ── Constants ────────────────────────────────────────────────────────────────
const SAMPLE_RATE      = 16000;   // Hz — matches Ife's Whisper ASR (Task 02)
const CHUNK_MS         = 250;     // ms per WebSocket message
const CHUNK_SAMPLES    = (SAMPLE_RATE * CHUNK_MS) / 1000; // 4000 samples
const SP_BUFFER        = 4096;    // ScriptProcessorNode buffer size

// VAD hysteresis — prevents flicker on brief noise
const VAD_THRESHOLD    = 0.015;   // RMS threshold
const VAD_ON_COUNT     = 2;       // consecutive loud frames → speaking
const VAD_OFF_COUNT    = 8;       // consecutive quiet frames → silent

// WebSocket reconnect
const WS_BASE_URL      = "ws://localhost:8000/ws";
const WS_RETRY_DELAY   = 2000;    // ms

// ── Helper: Float32 PCM → Int16 PCM (binary, compact) ────────────────────────
// This is what Ife's ASR endpoint expects — NOT JSON
function float32ToInt16(float32) {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const clamped = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  return int16;
}

// ── Helper: Merge Float32Arrays ───────────────────────────────────────────────
// .flat() does NOT work on typed arrays — we need this instead
function mergeFloat32(arrays) {
  const total = arrays.reduce((sum, a) => sum + a.length, 0);
  const out   = new Float32Array(total);
  let   offset = 0;
  for (const arr of arrays) {
    out.set(arr, offset);
    offset += arr.length;
  }
  return out;
}

// ── Helper: Downsample Float32 by integer ratio ───────────────────────────────
// Browser AudioContext runs at 48 kHz; ASR needs 16 kHz → ratio = 3
function downsample(input, fromRate, toRate) {
  if (fromRate === toRate) return input;
  const ratio  = fromRate / toRate;
  const outLen = Math.floor(input.length / ratio);
  const output = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const base = Math.floor(i * ratio);
    // Average the ratio samples to avoid aliasing
    let sum = 0;
    for (let j = 0; j < ratio; j++) sum += input[base + j] || 0;
    output[i] = sum / ratio;
  }
  return output;
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function AudioCapture() {
  const [status, setStatus]         = useState("idle");
  // idle | requesting | connecting | active | speaking | error
  const [errorMsg, setErrorMsg]     = useState("");
  const [audioLevel, setAudioLevel] = useState(0);   // 0–1 for meter
  const [stats, setStats]           = useState({ chunks: 0, kb: 0 });

  // Refs — changes here don't trigger re-renders
  const streamRef      = useRef(null);
  const audioCtxRef    = useRef(null);
  const processorRef   = useRef(null);
  const socketRef      = useRef(null);
  const sessionIdRef   = useRef(null);
  const retryTimerRef  = useRef(null);
  const stoppedRef     = useRef(false);

  // 250 ms accumulator buffer (16 kHz)
  const chunkBufRef    = useRef(new Float32Array(CHUNK_SAMPLES));
  const chunkFillRef   = useRef(0);

  // VAD hysteresis counters
  const loudCntRef     = useRef(0);
  const quietCntRef    = useRef(0);
  const isSpeakingRef  = useRef(false);

  // Running stats
  const chunksRef      = useRef(0);
  const bytesRef       = useRef(0);

  // Actual AudioContext sample rate (may differ from SAMPLE_RATE hint)
  const ctxRateRef     = useRef(48000);

  // ── WebSocket connect ───────────────────────────────────────────────────────
  const connectSocket = useCallback(() => {
    if (stoppedRef.current) return;

    const url = `${WS_BASE_URL}/${sessionIdRef.current}`;
    let   ws;

    try {
      ws = new WebSocket(url);
    } catch {
      setStatus("error");
      setErrorMsg("Invalid WebSocket URL.");
      return;
    }

    ws.binaryType = "arraybuffer";
    socketRef.current = ws;

    ws.onopen = () => {
      console.log("🟢 WebSocket connected");
      setStatus(isSpeakingRef.current ? "speaking" : "active");
    };

    ws.onerror = () => {
      console.warn("⚠️ WebSocket error");
    };

    ws.onclose = () => {
      if (stoppedRef.current) return;
      console.log("🔴 WS closed — retrying in", WS_RETRY_DELAY, "ms");
      setStatus("connecting");
      retryTimerRef.current = setTimeout(connectSocket, WS_RETRY_DELAY);
    };
  }, []);

  // ── Send a full 250 ms chunk ────────────────────────────────────────────────
  const flushChunk = useCallback((buf) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const pcm16 = float32ToInt16(buf);
    ws.send(pcm16.buffer);  // ✅ Binary, not JSON

    chunksRef.current++;
    bytesRef.current += pcm16.byteLength;
    setStats({ chunks: chunksRef.current, kb: +(bytesRef.current / 1024).toFixed(1) });
  }, []);

  // ── ScriptProcessor callback ────────────────────────────────────────────────
  const onAudioProcess = useCallback((e) => {
    const raw = e.inputBuffer.getChannelData(0);

    // Downsample from AudioContext rate (usually 48 kHz) to 16 kHz
    const samples = downsample(raw, ctxRateRef.current, SAMPLE_RATE);

    // ── RMS for level meter + VAD ───────────────────────────────────────
    let sum = 0;
    for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
    const rms = Math.sqrt(sum / samples.length);
    setAudioLevel(Math.min(rms * 12, 1));

    // ── VAD hysteresis ──────────────────────────────────────────────────
    if (rms > VAD_THRESHOLD) {
      loudCntRef.current++;
      quietCntRef.current = 0;
      if (!isSpeakingRef.current && loudCntRef.current >= VAD_ON_COUNT) {
        isSpeakingRef.current = true;
        setStatus("speaking");
      }
    } else {
      quietCntRef.current++;
      loudCntRef.current = 0;
      if (isSpeakingRef.current && quietCntRef.current >= VAD_OFF_COUNT) {
        isSpeakingRef.current = false;
        setStatus("active");
        // Flush partial chunk at end of speech
        if (chunkFillRef.current > 0) {
          flushChunk(chunkBufRef.current.slice(0, chunkFillRef.current));
          chunkFillRef.current = 0;
        }
      }
    }

    // ── Only buffer during speech ───────────────────────────────────────
    if (!isSpeakingRef.current) return;

    // ── Fill 250 ms buffer ──────────────────────────────────────────────
    let offset = 0;
    while (offset < samples.length) {
      const space  = CHUNK_SAMPLES - chunkFillRef.current;
      const toCopy = Math.min(space, samples.length - offset);
      chunkBufRef.current.set(samples.subarray(offset, offset + toCopy), chunkFillRef.current);
      chunkFillRef.current += toCopy;
      offset               += toCopy;

      if (chunkFillRef.current === CHUNK_SAMPLES) {
        flushChunk(chunkBufRef.current.slice());
        chunkFillRef.current = 0;
      }
    }
  }, [flushChunk]);

  // ── Start ───────────────────────────────────────────────────────────────────
  const start = async () => {
    stoppedRef.current  = false;
    sessionIdRef.current = uuidv4();
    chunksRef.current   = 0;
    bytesRef.current    = 0;
    chunkFillRef.current = 0;
    isSpeakingRef.current = false;
    loudCntRef.current  = 0;
    quietCntRef.current = 0;
    setStats({ chunks: 0, kb: 0 });
    setErrorMsg("");
    setStatus("requesting");

    // 1. Get mic
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount:     1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl:  true,
        },
      });
      streamRef.current = stream;
    } catch (err) {
      const denied = err?.name === "NotAllowedError";
      setErrorMsg(
        denied
          ? "Microphone access denied. Allow mic in browser settings."
          : "No microphone found. Check your device."
      );
      setStatus("error");
      return;
    }

    // 2. Build audio graph
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      audioCtxRef.current = ctx;
      ctxRateRef.current  = ctx.sampleRate; // capture actual rate

      const source    = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(SP_BUFFER, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = onAudioProcess;
      source.connect(processor);
      processor.connect(ctx.destination);
    } catch {
      setErrorMsg("Failed to initialise audio. Try refreshing.");
      setStatus("error");
      stream.getTracks().forEach((t) => t.stop());
      return;
    }

    // 3. Connect WebSocket
    setStatus("connecting");
    connectSocket();
  };

  // ── Stop ────────────────────────────────────────────────────────────────────
  const stop = () => {
    stoppedRef.current = true;

    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }

    if (socketRef.current) {
      socketRef.current.onclose = null; // prevent retry loop
      socketRef.current.close();
      socketRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.onaudioprocess = null;
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    chunkFillRef.current  = 0;
    isSpeakingRef.current = false;
    setAudioLevel(0);
    setStatus("idle");
  };

  // Cleanup on unmount
  useEffect(() => () => stop(), []);

  // ── Derived UI state ────────────────────────────────────────────────────────
  const isRunning = ["connecting", "active", "speaking"].includes(status);

  const statusLabel = {
    idle:       "Ready",
    requesting: "Requesting mic…",
    connecting: "Connecting…",
    active:     "Listening",
    speaking:   "Speaking",
    error:      "Error",
  }[status];

  const statusColor = {
    idle:       "#888780",
    requesting: "#854F0B",
    connecting: "#854F0B",
    active:     "#185FA5",
    speaking:   "#0F6E56",
    error:      "#993C1D",
  }[status];

  const statusBg = {
    idle:       "#F1EFE8",
    requesting: "#FAEEDA",
    connecting: "#FAEEDA",
    active:     "#E6F1FB",
    speaking:   "#E1F5EE",
    error:      "#FAECE7",
  }[status];

  const btnBg = status === "speaking"
    ? "#1D9E75"
    : isRunning
    ? "#378ADD"
    : "#F1EFE8";

  const btnColor = isRunning ? "#fff" : "#5F5E5A";

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div style={s.page}>
      <div style={s.card}>

        {/* Header */}
        <div style={s.header}>
          <div style={s.logo}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
              stroke="#378ADD" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
          </div>
          <div>
            <div style={s.title}>SignBridge Audio</div>
            <div style={s.subtitle}>Task 01 — Live capture</div>
          </div>
        </div>

        <div style={s.divider} />

        {/* Status badge */}
        <div style={{ ...s.badge, color: statusColor, background: statusBg }}>
          <span style={{ ...s.dot, background: statusColor }} />
          {statusLabel}
        </div>

        {/* Mic button */}
        <div style={s.btnWrap}>
          {/* Pulse ring when speaking */}
          {status === "speaking" && (
            <div style={s.pulse} />
          )}
          <button
            onClick={isRunning ? stop : start}
            disabled={status === "requesting"}
            style={{
              ...s.micBtn,
              background: btnBg,
              color:      btnColor,
              cursor:     status === "requesting" ? "wait" : "pointer",
              transform:  status === "requesting" ? "scale(0.95)" : "scale(1)",
            }}
            aria-label={isRunning ? "Stop recording" : "Start recording"}
          >
            {isRunning ? <StopIcon /> : <MicOffIcon />}
          </button>
        </div>

        {/* Level meter */}
        {isRunning && (
          <LevelMeter level={audioLevel} speaking={status === "speaking"} />
        )}

        {/* WS connection indicator */}
        {isRunning && (
          <div style={s.wsRow}>
            <span style={{
              ...s.wsDot,
              background: status === "connecting" ? "#EF9F27" : "#1D9E75",
            }} />
            <span style={{ fontSize: 11, color: "#888780" }}>
              {status === "connecting"
                ? "Waiting for server…"
                : `ws://localhost:8000/ws/...`}
            </span>
          </div>
        )}

        {/* Error */}
        {status === "error" && errorMsg && (
          <div style={s.errorBox}>
            <span style={s.errorTitle}>⚠ {errorMsg}</span>
            <button onClick={start} style={s.retryBtn}>Try again</button>
          </div>
        )}

        {/* Stats */}
        {stats.chunks > 0 && (
          <div style={s.statsRow}>
            <Stat label="Chunks sent" value={stats.chunks} />
            <Stat label="Data sent"   value={`${stats.kb} KB`} />
            <Stat label="Format"      value="Int16 PCM" />
          </div>
        )}

        <div style={s.divider} />

        {/* Format info footer */}
        <div style={s.footer}>
          16 kHz · Mono · 250 ms windows · Binary PCM → Ife (ASR)
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function LevelMeter({ level, speaking }) {
  const bars = 14;
  return (
    <div style={{ display: "flex", gap: 2, alignItems: "flex-end", height: 28 }}
      role="meter" aria-valuenow={Math.round(level * 100)}
      aria-label="Microphone level">
      {Array.from({ length: bars }, (_, i) => {
        const threshold = (i + 1) / bars;
        const active    = level >= threshold;
        const color     = speaking
          ? (active ? "#1D9E75" : "#9FE1CB")
          : (active ? "#378ADD" : "#B5D4F4");
        return (
          <div key={i} style={{
            width:           3,
            height:          `${30 + (i / bars) * 70}%`,
            borderRadius:    2,
            backgroundColor: color,
            transition:      "background-color 80ms ease",
          }} />
        );
      })}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 13, fontWeight: 500, color: "#3d3d3a" }}>{value}</div>
      <div style={{ fontSize: 10, color: "#888780", marginTop: 2 }}>{label}</div>
    </div>
  );
}

function MicOffIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="1" y1="1" x2="23" y2="23"/>
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/>
      <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8"  y1="23" x2="16" y2="23"/>
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="6" width="12" height="12" rx="2"/>
    </svg>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = {
  page: {
    minHeight:       "100vh",
    display:         "flex",
    alignItems:      "center",
    justifyContent:  "center",
    background:      "#F5F4EF",
    fontFamily:      "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    padding:         "24px",
  },
  card: {
    background:    "#ffffff",
    borderRadius:  20,
    border:        "1px solid #E5E3DC",
    boxShadow:     "0 2px 20px rgba(0,0,0,0.07)",
    padding:       "28px 32px",
    width:         "100%",
    maxWidth:      340,
    display:       "flex",
    flexDirection: "column",
    alignItems:    "center",
    gap:           16,
  },
  header: {
    display:    "flex",
    alignItems: "center",
    gap:        12,
    width:      "100%",
  },
  logo: {
    width:          40,
    height:         40,
    borderRadius:   10,
    background:     "#E6F1FB",
    display:        "flex",
    alignItems:     "center",
    justifyContent: "center",
    flexShrink:     0,
  },
  title: {
    fontSize:   15,
    fontWeight: 600,
    color:      "#1a1a18",
  },
  subtitle: {
    fontSize: 11,
    color:    "#888780",
    marginTop: 1,
  },
  divider: {
    width:      "100%",
    height:     1,
    background: "#F1EFE8",
  },
  badge: {
    display:      "inline-flex",
    alignItems:   "center",
    gap:          6,
    fontSize:     11,
    fontWeight:   500,
    padding:      "4px 12px",
    borderRadius: 20,
    transition:   "all 0.2s",
  },
  dot: {
    width:        6,
    height:       6,
    borderRadius: "50%",
    flexShrink:   0,
  },
  btnWrap: {
    position: "relative",
    display:  "flex",
    alignItems: "center",
    justifyContent: "center",
    margin: "4px 0",
  },
  pulse: {
    position:     "absolute",
    inset:        -12,
    borderRadius: "50%",
    border:       "2px solid #1D9E75",
    animation:    "none",
    opacity:      0.5,
    // CSS animation injected via <style> tag below
    animationName:           "sbRipple",
    animationDuration:       "1.5s",
    animationTimingFunction: "ease-out",
    animationIterationCount: "infinite",
  },
  micBtn: {
    width:          68,
    height:         68,
    borderRadius:   "50%",
    border:         "none",
    display:        "flex",
    alignItems:     "center",
    justifyContent: "center",
    transition:     "background 0.25s, transform 0.15s",
    outline:        "none",
    position:       "relative",
    zIndex:         1,
  },
  wsRow: {
    display:    "flex",
    alignItems: "center",
    gap:        6,
  },
  wsDot: {
    width:        7,
    height:       7,
    borderRadius: "50%",
    flexShrink:   0,
  },
  errorBox: {
    background:    "#FAECE7",
    border:        "1px solid #F5C4B3",
    borderRadius:  10,
    padding:       "12px 16px",
    width:         "100%",
    textAlign:     "center",
  },
  errorTitle: {
    display:    "block",
    fontSize:   12,
    color:      "#993C1D",
    lineHeight: 1.5,
  },
  retryBtn: {
    marginTop:    8,
    fontSize:     11,
    color:        "#993C1D",
    background:   "none",
    border:       "1px solid #F0997B",
    borderRadius: 6,
    cursor:       "pointer",
    padding:      "3px 12px",
    fontWeight:   500,
  },
  statsRow: {
    display:        "flex",
    justifyContent: "space-between",
    width:          "100%",
    padding:        "4px 0",
  },
  footer: {
    fontSize: 10,
    color:    "#B4B2A9",
    textAlign: "center",
    lineHeight: 1.6,
  },
};

// Inject pulse keyframe (avoids a separate CSS file)
if (typeof document !== "undefined" && !document.getElementById("sb-pulse-style")) {
  const style = document.createElement("style");
  style.id = "sb-pulse-style";
  style.textContent = `
    @keyframes sbRipple {
      0%   { transform: scale(1);    opacity: 0.55; }
      100% { transform: scale(1.6);  opacity: 0;    }
    }
  `;
  document.head.appendChild(style);
}
