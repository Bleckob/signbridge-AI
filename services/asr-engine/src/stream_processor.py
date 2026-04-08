"""
Stream Processor
================
Main entry point for the ASR service. Runs as a long-lived process that:

1. Consumes audio chunks from Redis (pushed by Blessing's backend)
2. Buffers chunks per session until VAD detects end-of-speech
3. Runs: preprocess → transcribe → postprocess
4. Publishes transcription results to Redis (for Amos's NLP engine)

Pipeline position:
    [Blessing's backend] → Redis "audio-chunks"
        → stream_processor (THIS FILE — orchestrates everything)
            → audio_preprocessor → transcriber → postprocessor
        → Redis "transcriptions" → [Amos's NLP engine]

Usage:
    python -m src.stream_processor
"""

import json
import time
import base64
import redis

from config.asr_config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    REDIS_USERNAME,
    REDIS_INPUT_STREAM,
    REDIS_OUTPUT_STREAM,
    REDIS_CONSUMER_GROUP,
    MAX_AUDIO_BUFFER,
)
from src.audio_preprocessor import AudioPreprocessor
from src.transcriber import Transcriber
from src.postprocessor import Postprocessor


class StreamProcessor:
    """
    Consumes audio from Redis, runs the ASR pipeline, publishes transcriptions.

    Each connected user (session) gets their own audio buffer. When VAD detects
    a speech segment ending (or the buffer gets too large), we transcribe and flush.
    """

    def __init__(self):
        # Initialize the three pipeline stages
        print("Initializing ASR pipeline...")
        self.preprocessor = AudioPreprocessor()
        self.transcriber = Transcriber()
        self.postprocessor = Postprocessor()

        # Connect to Redis (same instance as Blessing's backend)
        self.redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            username=REDIS_USERNAME,
            password=REDIS_PASSWORD,
            decode_responses=True,
            ssl=False,
        )

        # Per-session audio buffers: {session_id: [raw_bytes_chunk1, chunk2, ...]}
        self.audio_buffers: dict[str, list[bytes]] = {}

        # Track buffer durations to know when to flush
        self.buffer_durations: dict[str, float] = {}

        self._ensure_consumer_group()
        print("ASR pipeline ready. Listening for audio chunks...")

    def _ensure_consumer_group(self):
        """
        Create the Redis consumer group if it doesn't exist.

        Consumer groups allow multiple ASR workers to split the load —
        each audio chunk is processed by exactly one worker.
        """
        try:
            self.redis.xgroup_create(
                REDIS_INPUT_STREAM,
                REDIS_CONSUMER_GROUP,
                id="0",  # Start reading from the beginning
                mkstream=True,  # Create the stream if it doesn't exist
            )
            print(f"Created consumer group '{REDIS_CONSUMER_GROUP}'")
        except redis.exceptions.ResponseError as e:
            if "BUSYGROUP" in str(e):
                pass  # Group already exists, that's fine
            else:
                raise

    def run(self, worker_name: str = "asr-worker-1"):
        """
        Main loop. Blocks forever, consuming audio chunks from Redis.

        Args:
            worker_name: Unique name for this worker (for consumer group tracking)
        """
        while True:
            try:
                # Read new messages from the consumer group
                # Block for up to 1 second waiting for new messages
                messages = self.redis.xreadgroup(
                    groupname=REDIS_CONSUMER_GROUP,
                    consumername=worker_name,
                    streams={REDIS_INPUT_STREAM: ">"},  # ">" = only new messages
                    count=10,       # Process up to 10 chunks at a time
                    block=1000,     # Block for 1 second if no messages
                )

                if not messages:
                    continue

                # messages format: [(stream_name, [(msg_id, {field: value}), ...])]
                for stream_name, entries in messages:
                    for msg_id, fields in entries:
                        self._process_message(msg_id, fields)

            except redis.exceptions.ConnectionError:
                print("Redis connection lost. Retrying in 3 seconds...")
                time.sleep(3)
            except KeyboardInterrupt:
                print("Shutting down ASR worker...")
                break

    def _process_message(self, msg_id: str, fields: dict):
        """
        Process a single audio chunk message from Redis.

        The message format (from Blessing's backend main.py:79) is:
            {"session_id": "abc123", "data": json.dumps(payload)}

        We buffer chunks per session, and when we have enough audio,
        we run the full transcription pipeline.
        """
        session_id = fields.get("session_id", "unknown")
        raw_data = fields.get("data", "{}")

        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            self._ack(msg_id)
            return

        # Extract audio bytes — David's frontend likely sends base64-encoded audio
        audio_b64 = payload.get("audio", payload.get("data", ""))
        if not audio_b64:
            self._ack(msg_id)
            return

        # Decode base64 to raw bytes
        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception:
            # Maybe it's already raw bytes sent as a string
            audio_bytes = audio_b64.encode("latin-1") if isinstance(audio_b64, str) else audio_b64

        # Add to this session's buffer
        if session_id not in self.audio_buffers:
            self.audio_buffers[session_id] = []
            self.buffer_durations[session_id] = 0.0

        self.audio_buffers[session_id].append(audio_bytes)

        # Estimate chunk duration (assuming 48kHz float32 mono from browser)
        chunk_samples = len(audio_bytes) / 4  # float32 = 4 bytes per sample
        chunk_duration = chunk_samples / 48000  # Browser default sample rate
        self.buffer_durations[session_id] += chunk_duration

        # Decide whether to transcribe now
        # Transcribe if buffer exceeds max duration (prevents unbounded memory growth)
        if self.buffer_durations[session_id] >= MAX_AUDIO_BUFFER:
            self._transcribe_buffer(session_id)

        # Also try to transcribe shorter buffers — the preprocessor's VAD
        # will determine if there's a complete speech segment
        elif self.buffer_durations[session_id] >= 2.0:
            self._transcribe_buffer(session_id)

        # Acknowledge the message so it won't be redelivered
        self._ack(msg_id)

    def _transcribe_buffer(self, session_id: str):
        """
        Run the full ASR pipeline on a session's buffered audio.

        Pipeline: raw bytes → preprocess → transcribe → postprocess → Redis output
        """
        if session_id not in self.audio_buffers or not self.audio_buffers[session_id]:
            return

        # Combine all buffered chunks into one byte string
        combined_bytes = b"".join(self.audio_buffers[session_id])

        # Clear the buffer
        self.audio_buffers[session_id] = []
        self.buffer_durations[session_id] = 0.0

        # --- STAGE 1: Preprocess ---
        speech_audio = self.preprocessor.process(combined_bytes)
        if speech_audio is None or len(speech_audio) == 0:
            return  # No speech detected, skip

        # --- STAGE 2: Transcribe ---
        result = self.transcriber.transcribe(speech_audio)
        if result is None:
            return  # Too short or too low confidence

        # --- STAGE 3: Postprocess ---
        cleaned_text = self.postprocessor.clean_text(result.text)
        if not cleaned_text:
            return

        # --- STAGE 4: Publish to Redis for Amos's NLP engine ---
        output_payload = {
            "session_id": session_id,
            "text": cleaned_text,
            "confidence": str(result.confidence),
            "language": result.language,
            "segments": json.dumps(result.segments),
            "timestamp": str(time.time()),
        }

        self.redis.xadd(REDIS_OUTPUT_STREAM, output_payload)
        print(f"[{session_id}] Transcribed: \"{cleaned_text}\" (confidence: {result.confidence})")

    def _ack(self, msg_id: str):
        """Acknowledge a message so Redis doesn't redeliver it."""
        self.redis.xack(REDIS_INPUT_STREAM, REDIS_CONSUMER_GROUP, msg_id)


# ---------------------------------------------------------------------------
# Entry point: python -m src.stream_processor
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    processor = StreamProcessor()
    processor.run()
