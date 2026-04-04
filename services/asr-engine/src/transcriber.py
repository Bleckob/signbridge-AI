"""
Transcriber
===========
Core ASR module. Loads a faster-whisper model and transcribes speech audio to text.

Pipeline position:
    [audio_preprocessor] → transcriber → [postprocessor]

This uses faster-whisper (CTranslate2 backend) instead of vanilla Whisper for:
- 4x faster inference speed
- Lower VRAM/RAM usage via int8/float16 quantization
- Word-level timestamps out of the box
"""

import numpy as np
from faster_whisper import WhisperModel
from config.asr_config import (
    MODEL_SIZE,
    MODEL_DIR,
    DEVICE,
    COMPUTE_TYPE,
    LANGUAGE,
    BEAM_SIZE,
    MIN_CONFIDENCE,
    MIN_AUDIO_DURATION,
    SAMPLE_RATE,
)


class TranscriptionResult:
    """Holds the output of a transcription run."""

    def __init__(self, text: str, segments: list, language: str, confidence: float):
        self.text = text              # Full transcribed text
        self.segments = segments      # List of segment dicts with timestamps
        self.language = language      # Detected/forced language
        self.confidence = confidence  # Average log probability (higher = more confident)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "segments": self.segments,
            "language": self.language,
            "confidence": self.confidence,
        }


class Transcriber:
    def __init__(self):
        """
        Load the faster-whisper model into memory.

        This is slow (~5-20s depending on model size), so we do it ONCE at startup.
        The model stays in memory and handles all subsequent transcription requests.
        """
        print(f"Loading Whisper model: {MODEL_SIZE} (device={DEVICE}, compute={COMPUTE_TYPE})")

        self.model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            download_root=str(MODEL_DIR),
        )

        print(f"Whisper model '{MODEL_SIZE}' loaded successfully.")

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult | None:
        """
        Transcribe a numpy audio array into text.

        Args:
            audio: float32 numpy array at 16kHz (output of AudioPreprocessor)

        Returns:
            TranscriptionResult with text, segments, and confidence,
            or None if audio is too short or confidence is too low.
        """
        # Guard: skip audio shorter than minimum duration
        duration = len(audio) / SAMPLE_RATE
        if duration < MIN_AUDIO_DURATION:
            return None

        # Run faster-whisper inference
        # - language="en" forces English (prevents Nigerian accent misdetection as Dutch/etc.)
        # - beam_size=5 balances speed vs accuracy
        # - vad_filter=False because we already ran Silero VAD in the preprocessor
        raw_segments, info = self.model.transcribe(
            audio,
            language=LANGUAGE,
            beam_size=BEAM_SIZE,
            vad_filter=False,
            word_timestamps=True,
            condition_on_previous_text=True,  # Helps maintain context across segments
        )

        # Collect segments and build full text
        segments = []
        full_text_parts = []
        total_log_prob = 0.0
        segment_count = 0

        for seg in raw_segments:
            # Build word-level detail (useful for debugging and future subtitle features)
            words = []
            if seg.words:
                words = [
                    {
                        "word": w.word,
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "probability": round(w.probability, 3),
                    }
                    for w in seg.words
                ]

            segments.append({
                "id": seg.id,
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip(),
                "words": words,
                "avg_logprob": round(seg.avg_logprob, 3),
            })

            full_text_parts.append(seg.text.strip())
            total_log_prob += seg.avg_logprob
            segment_count += 1

        # No segments produced
        if segment_count == 0:
            return None

        avg_confidence = total_log_prob / segment_count

        # Filter out low-confidence transcriptions (likely noise/gibberish)
        if avg_confidence < MIN_CONFIDENCE:
            return None

        full_text = " ".join(full_text_parts)

        return TranscriptionResult(
            text=full_text,
            segments=segments,
            language=info.language,
            confidence=round(avg_confidence, 3),
        )
