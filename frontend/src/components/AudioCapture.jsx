import { useState, useRef } from "react";
import { v4 as uuidv4 } from "uuid";

export default function AudioCapture() {
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState("");

  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const chunksRef = useRef([]);
  const socketRef = useRef(null);

  const startRecording = async () => {
    setError("");

    try {
      // Prevent duplicate sockets
      if (socketRef.current) {
        socketRef.current.close();
      }

      // Generate session ID
      const sessionId = uuidv4();

      // Connect WebSocket
      const socket = new WebSocket(
        `ws://localhost:8000/ws/${sessionId}`
      );

      socket.onopen = () => {
        console.log("🟢 WebSocket connected");
      };

      socket.onerror = (err) => {
        console.error("WebSocket error:", err);
        setError("WebSocket connection failed");
      };

      socket.onclose = () => {
        console.log("🔴 WebSocket closed");
      };

      socketRef.current = socket;

      // Get microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          noiseSuppression: true,
          echoCancellation: true,
          autoGainControl: true,
          channelCount: 1,
          sampleRate: 16000,
        },
      });

      streamRef.current = stream;

      const audioContext = new (window.AudioContext ||
        window.webkitAudioContext)();

      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      source.connect(processor);
      processor.connect(audioContext.destination);

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);

        // 🔊 VAD (Volume Detection)
        let sum = 0;
        for (let i = 0; i < inputData.length; i++) {
          sum += inputData[i] * inputData[i];
        }
        const rms = Math.sqrt(sum / inputData.length);

        const THRESHOLD = 0.01;

        if (rms > THRESHOLD) {
          setIsSpeaking(true);
        } else {
          setIsSpeaking(false);
        }

        const chunk = new Float32Array(inputData);

        // ✅ Send only when speaking
        if (rms > THRESHOLD) {
          chunksRef.current.push(chunk);

          if (chunksRef.current.length >= 10) {
            const batch = chunksRef.current.flat();

            if (socketRef.current?.readyState === WebSocket.OPEN) {
              socketRef.current.send(
                JSON.stringify({
                  type: "audio_chunk",
                  data: Array.from(batch),
                })
              );

              console.log("📡 Sent audio batch (speaking)");
            }

            chunksRef.current = [];
          }
        }
      };

      setIsRecording(true);
      console.log("🎤 Streaming started");

    } catch (err) {
      console.error("Start recording error:", err);
      setError(err.message || "Error starting audio");
    }
  };

  const stopRecording = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
    }

    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    chunksRef.current = [];
    setIsRecording(false);
    setIsSpeaking(false);

    console.log("🛑 Stopped streaming");
  };

  return (
    <div style={styles.container}>
      <h2>SignBridge Live Audio</h2>

      <button
        onClick={isRecording ? stopRecording : startRecording}
        style={{
          ...styles.button,
          backgroundColor: isRecording ? "#dc2626" : "#16a34a",
        }}
      >
        {isRecording ? "Stop" : "Start"}
      </button>

      <p>
        {isRecording
          ? isSpeaking
            ? "🟢 Speaking..."
            : "⚪ Silent"
          : "Idle"}
      </p>

      {error && <p style={styles.error}>{error}</p>}
    </div>
  );
}

const styles = {
  container: {
    textAlign: "center",
    marginTop: "80px",
  },
  button: {
    padding: "12px 24px",
    border: "none",
    borderRadius: "8px",
    color: "#fff",
    cursor: "pointer",
  },
  error: {
    color: "red",
  },
};