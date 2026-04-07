import { useState, useRef } from "react";

export default function AudioCapture() {
  const [isRecording, setIsRecording] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState("");

  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const chunksRef = useRef([]);

  const startRecording = async () => {
    setError("");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      streamRef.current = stream;

      const audioContext = new (window.AudioContext ||
        window.webkitAudioContext)();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);

      // 🔥 Script processor (simple chunking)
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      source.connect(processor);
      processor.connect(audioContext.destination);

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);

        // Copy audio data
        const chunk = new Float32Array(inputData);
        chunksRef.current.push(chunk);

        // Approx log every few chunks
        console.log("Chunk captured:", chunk.length);

        // Optional: simulate ~250ms batching
        if (chunksRef.current.length >= 10) {
          const batch = chunksRef.current.flat();
          console.log("📦 Batch ready (~250ms):", batch.length);

          // Here is where WebSocket sending will go later
          chunksRef.current = [];
        }
      };

      setIsRecording(true);
      console.log("🎤 Chunking started");

    } catch (err) {
      console.error(err);
      setError("Microphone access denied.");
    }
  };

  const stopRecording = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
    }

    setIsRecording(false);
    setIsSpeaking(false);

    console.log("🛑 Stopped chunking");
  };

  return (
    <div style={styles.container}>
      <h2>SignBridge Audio Chunking</h2>

      <button
        onClick={isRecording ? stopRecording : startRecording}
        style={{
          ...styles.button,
          backgroundColor: isRecording ? "#dc2626" : "#16a34a",
        }}
      >
        {isRecording ? "Stop Recording" : "Start Recording"}
      </button>

      <p>Status: {isRecording ? "🎙️ Chunking..." : "Idle"}</p>

      <p>
        Speech: {isSpeaking ? "🗣️ Speaking" : "🤫 Silent"}
      </p>

      {error && <p style={styles.error}>{error}</p>}
    </div>
  );
}

const styles = {
  container: {
    textAlign: "center",
    marginTop: "80px",
    fontFamily: "sans-serif",
  },
  button: {
    padding: "12px 24px",
    fontSize: "16px",
    border: "none",
    borderRadius: "8px",
    color: "#fff",
    cursor: "pointer",
  },
  error: {
    color: "red",
    marginTop: "10px",
  },
};