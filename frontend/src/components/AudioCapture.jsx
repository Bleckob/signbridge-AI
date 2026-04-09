// AudioCapture.jsx — SignBridge AI | Task 01 | Week 2
// Owner: Confidence

import { useState, useRef, useCallback, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";

const SAMPLE_RATE   = 16_000;
const CHUNK_MS      = 250;
const CHUNK_SAMPLES = (SAMPLE_RATE * CHUNK_MS) / 1000;
const WS_BASE_URL   = "ws://localhost:8000/ws";
const WS_RETRY_MS   = 2_000;
const WS_MAX_RETRY  = 16_000;

const VAD_WORKLET_URL = "https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.19/dist/vad.worklet.bundle.min.js";
const VAD_MODEL_URL   = "https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.19/dist/silero_vad.onnx";
const ORT_WASM_PATH   = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.14.0/dist/";

export function float32ToInt16(f32) {
  const i16 = new Int16Array(f32.length);
  for (let i = 0; i < f32.length; i++) {
    const c = Math.max(-1, Math.min(1, f32[i]));
    i16[i]  = c < 0 ? c * 0x8000 : c * 0x7fff;
  }
  return i16;
}

export function sendChunked(audio, socket) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return 0;
  let sent = 0;
  for (let offset = 0; offset < audio.length; offset += CHUNK_SAMPLES) {
    const slice = audio.subarray(offset, offset + CHUNK_SAMPLES);
    const frame = slice.length === CHUNK_SAMPLES
      ? slice
      : (() => { const p = new Float32Array(CHUNK_SAMPLES); p.set(slice); return p; })();
    socket.send(float32ToInt16(frame).buffer);
    sent++;
  }
  return sent;
}

export default function AudioCapture() {
  const [status,     setStatus]     = useState("idle");
  const [errorMsg,   setErrorMsg]   = useState("");
  const [audioLevel, setAudioLevel] = useState(0);
  const [stats,      setStats]      = useState({ chunks: 0, kb: 0, utterances: 0 });

  const vadRef        = useRef(null);
  const socketRef     = useRef(null);
  const sessionIdRef  = useRef(null);
  const stoppedRef    = useRef(false);
  const retryTimerRef = useRef(null);
  const retryDelayRef = useRef(WS_RETRY_MS);
  const rafRef        = useRef(null);
  const analyserRef   = useRef(null);
  const streamRef     = useRef(null);
  const audioCtxRef   = useRef(null);
  const chunksRef     = useRef(0);
  const bytesRef      = useRef(0);
  const uttRef        = useRef(0);

  const connectWS = useCallback(() => {
    if (stoppedRef.current) return;
    let ws;
    try { ws = new WebSocket(`${WS_BASE_URL}/${sessionIdRef.current}`); }
    catch { setStatus("error"); setErrorMsg("Invalid WebSocket URL."); return; }
    ws.binaryType     = "arraybuffer";
    socketRef.current = ws;
    ws.onopen  = () => { retryDelayRef.current = WS_RETRY_MS; setStatus("active"); };
    ws.onclose = () => {
      if (stoppedRef.current) return;
      const d = retryDelayRef.current;
      retryDelayRef.current = Math.min(d * 2, WS_MAX_RETRY);
      retryTimerRef.current = setTimeout(connectWS, d);
      setStatus("connecting");
    };
    ws.onerror = () => {};
  }, []);

  const startMeter = useCallback((stream) => {
    const ctx      = new AudioContext();
    const source   = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    audioCtxRef.current = ctx;
    analyserRef.current = analyser;
    streamRef.current   = stream;
    const buf = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      if (stoppedRef.current) return;
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
      setAudioLevel(Math.min(Math.sqrt(sum / buf.length) * 10, 1));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const start = useCallback(async () => {
    stoppedRef.current    = false;
    sessionIdRef.current  = uuidv4();
    chunksRef.current     = 0;
    bytesRef.current      = 0;
    uttRef.current        = 0;
    retryDelayRef.current = WS_RETRY_MS;
    setStats({ chunks: 0, kb: 0, utterances: 0 });
    setErrorMsg("");
    setStatus("loading");

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (err) {
      const denied = err?.name === "NotAllowedError" || err?.name === "PermissionDeniedError";
      setErrorMsg(denied
        ? "Microphone access denied. Allow mic in your browser settings."
        : "No microphone found. Check your device.");
      setStatus("error");
      return;
    }

    startMeter(stream);

    try {
      const { MicVAD } = await import("@ricky0123/vad-web");
      const vad = await MicVAD.new({
        stream,
        workletURL: VAD_WORKLET_URL,
        modelURL:   VAD_MODEL_URL,
        ortConfig: (ort) => {
          ort.env.wasm.wasmPaths  = ORT_WASM_PATH;
          ort.env.wasm.numThreads = 1;
        },
        onSpeechStart: () => setStatus("speaking"),
        onSpeechEnd: (audio) => {
          const sent      = sendChunked(audio, socketRef.current);
          const bytesSent = sent * CHUNK_SAMPLES * 2;
          chunksRef.current += sent;
          bytesRef.current  += bytesSent;
          uttRef.current    += 1;
          setStats({ chunks: chunksRef.current, kb: +(bytesRef.current / 1024).toFixed(1), utterances: uttRef.current });
          setStatus("active");
        },
        onVADMisfire: () => setStatus("active"),
      });
      vadRef.current = vad;
      vad.start();
    } catch (err) {
      console.error("[AudioCapture] VAD error:", err);
      setErrorMsg("Failed to load VAD model. Check your internet connection.");
      setStatus("error");
      stream.getTracks().forEach((t) => t.stop());
      return;
    }

    setStatus("connecting");
    connectWS();
  }, [connectWS, startMeter]);

  const stop = useCallback(() => {
    stoppedRef.current = true;
    cancelAnimationFrame(rafRef.current);
    if (retryTimerRef.current) { clearTimeout(retryTimerRef.current); retryTimerRef.current = null; }
    if (vadRef.current)    { try { vadRef.current.pause(); } catch {} vadRef.current = null; }
    if (socketRef.current) { socketRef.current.onclose = null; socketRef.current.close(); socketRef.current = null; }
    if (analyserRef.current) { analyserRef.current.disconnect(); analyserRef.current = null; }
    if (audioCtxRef.current) { audioCtxRef.current.close(); audioCtxRef.current = null; }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setAudioLevel(0);
    setStatus("idle");
  }, []);

  useEffect(() => () => stop(), [stop]);

  const isRunning  = ["loading","connecting","active","speaking"].includes(status);
  const isSpeaking = status === "speaking";
  const isLoading  = status === "loading";
  const LABELS = { idle:"Ready", loading:"Loading model…", connecting:"Connecting…", active:"Listening", speaking:"Speaking", error:"Error" };
  const COLORS = { idle:{text:"#5F5E5A",bg:"#F1EFE8"}, loading:{text:"#854F0B",bg:"#FAEEDA"}, connecting:{text:"#854F0B",bg:"#FAEEDA"}, active:{text:"#185FA5",bg:"#E6F1FB"}, speaking:{text:"#0F6E56",bg:"#E1F5EE"}, error:{text:"#993C1D",bg:"#FAECE7"} };
  const col   = COLORS[status] ?? COLORS.idle;
  const btnBg = isSpeaking ? "#1D9E75" : isRunning ? "#378ADD" : "#F1EFE8";
  const btnFg = isRunning ? "#fff" : "#5F5E5A";

  return (
    <>
      <style>{`
        @keyframes sbPulse { 0%{transform:scale(1);opacity:.6} 100%{transform:scale(1.75);opacity:0} }
        @keyframes sbSpin  { to{transform:rotate(360deg)} }
        .sb-btn:hover:not(:disabled){transform:scale(1.06)!important}
        .sb-btn:active:not(:disabled){transform:scale(0.96)!important}
      `}</style>
      <div style={{minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",background:"#F5F4EF",fontFamily:"-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif",padding:24}}>
        <div style={{background:"#fff",borderRadius:20,border:"1px solid #E5E3DC",boxShadow:"0 2px 24px rgba(0,0,0,0.07)",padding:"28px 32px",width:"100%",maxWidth:360,display:"flex",flexDirection:"column",alignItems:"center",gap:16}}>

          {/* Header */}
          <div style={{display:"flex",alignItems:"center",gap:12,width:"100%"}}>
            <div style={{width:40,height:40,borderRadius:10,background:"#E6F1FB",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0}}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#378ADD" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8" y1="23" x2="16" y2="23"/>
              </svg>
            </div>
            <div>
              <div style={{fontSize:15,fontWeight:600,color:"#1a1a18"}}>SignBridge Audio</div>
              <div style={{fontSize:11,color:"#888780",marginTop:2}}>Task 01 · Week 2 · Confidence</div>
            </div>
          </div>

          <div style={{width:"100%",height:1,background:"#F1EFE8"}}/>

          {/* Status badge */}
          <div style={{display:"inline-flex",alignItems:"center",gap:7,fontSize:11,fontWeight:500,padding:"4px 13px",borderRadius:20,color:col.text,background:col.bg,transition:"all 0.2s"}}>
            {isLoading
              ? <span style={{width:10,height:10,borderRadius:"50%",border:"1.5px solid currentColor",borderTopColor:"transparent",display:"inline-block",animation:"sbSpin 0.7s linear infinite",flexShrink:0}}/>
              : <span style={{width:6,height:6,borderRadius:"50%",background:col.text,flexShrink:0}}/>
            }
            {LABELS[status]}
          </div>

          {/* Mic button */}
          <div style={{position:"relative",display:"flex",alignItems:"center",justifyContent:"center",margin:"6px 0"}}>
            {isSpeaking && <div style={{position:"absolute",inset:-14,borderRadius:"50%",border:"2px solid #1D9E75",animationName:"sbPulse",animationDuration:"1.5s",animationTimingFunction:"ease-out",animationIterationCount:"infinite",pointerEvents:"none"}}/>}
            <button className="sb-btn" onClick={isRunning ? stop : start} disabled={isLoading}
              style={{width:72,height:72,borderRadius:"50%",border:"none",display:"flex",alignItems:"center",justifyContent:"center",transition:"background 0.25s, transform 0.12s",outline:"none",position:"relative",zIndex:1,background:btnBg,color:btnFg,cursor:isLoading?"wait":"pointer"}}
              aria-label={isRunning?"Stop recording":"Start recording"} aria-pressed={isRunning}>
              {isRunning
                ? <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
                : <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="1" y1="1" x2="23" y2="23"/>
                    <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/>
                    <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                    <line x1="8" y1="23" x2="16" y2="23"/>
                  </svg>
              }
            </button>
          </div>

          {/* Level meter */}
          {isRunning && (
            <div role="meter" aria-valuenow={Math.round(audioLevel*100)} aria-label="Mic level"
              style={{display:"flex",gap:2,alignItems:"flex-end",height:32}}>
              {Array.from({length:16},(_,i)=>(
                <div key={i} style={{width:3,height:`${25+(i/16)*75}%`,borderRadius:2,transition:"background-color 60ms ease",
                  backgroundColor:isSpeaking?(audioLevel>=(i+1)/16?"#1D9E75":"#9FE1CB"):(audioLevel>=(i+1)/16?"#378ADD":"#B5D4F4")}}/>
              ))}
            </div>
          )}

          {/* WS status */}
          {isRunning && (
            <div style={{display:"flex",alignItems:"center",gap:7}}>
              <span style={{width:7,height:7,borderRadius:"50%",flexShrink:0,transition:"background 0.3s",
                background:status==="connecting"?"#EF9F27":status==="loading"?"#B4B2A9":"#1D9E75"}}/>
              <span style={{fontSize:11,color:"#888780"}}>
                {status==="connecting"?"Connecting to server…":status==="loading"?"Loading VAD model…":"Streaming → ASR engine"}
              </span>
            </div>
          )}

          {/* Error */}
          {status==="error" && errorMsg && (
            <div role="alert" style={{background:"#FAECE7",border:"1px solid #F5C4B3",borderRadius:12,padding:"12px 16px",width:"100%",display:"flex",flexDirection:"column",alignItems:"center",gap:8}}>
              <span style={{fontSize:12,color:"#993C1D",lineHeight:1.55,textAlign:"center"}}>{errorMsg}</span>
              <button onClick={start} style={{fontSize:11,color:"#993C1D",background:"none",border:"1px solid #F0997B",borderRadius:6,cursor:"pointer",padding:"4px 14px",fontWeight:500}}>
                Try again
              </button>
            </div>
          )}

          {/* Stats */}
          {stats.utterances > 0 && (
            <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:8,width:"100%"}}>
              {[{label:"Utterances",value:stats.utterances},{label:"Chunks",value:stats.chunks},{label:"Sent",value:`${stats.kb} KB`}].map(({label,value})=>(
                <div key={label} style={{background:"#F5F4EF",borderRadius:10,padding:"10px 8px",textAlign:"center"}}>
                  <div style={{fontSize:14,fontWeight:600,color:"#1a1a18",fontVariantNumeric:"tabular-nums"}}>{value}</div>
                  <div style={{fontSize:10,color:"#888780",marginTop:3}}>{label}</div>
                </div>
              ))}
            </div>
          )}

          <div style={{width:"100%",height:1,background:"#F1EFE8"}}/>

          {/* Footer */}
          <div style={{display:"flex",gap:6,flexWrap:"wrap",justifyContent:"center"}}>
            {["16 kHz","Int16 PCM","250 ms","ONNX VAD"].map((t)=>(
              <span key={t} style={{fontSize:10,fontWeight:500,padding:"3px 9px",borderRadius:20,background:"#F1EFE8",color:"#888780",border:"1px solid #E5E3DC"}}>{t}</span>
            ))}
          </div>

        </div>
      </div>
    </>
  );
}