"""
Audio Preprocessor
==================
Converts raw audio bytes into clean, normalized numpy arrays ready for Whisper.
Handles: decoding, resampling to 16kHz, noise reduction, and VAD segmentation.

Pipeline position:
    [Redis raw audio] → audio_preprocessor → [transcriber]
"""

import numpy as np
import torch
import io
from scipy.signal import resample
import noisereduce as nr
from config.asr_config import SAMPLE_RATE, VAD_THRESHOLD, VAD_MIN_SILENCE


class AudioPreprocessor:
    def __init__(self):
        """Load the Silero VAD model once at startup (lightweight, ~1MB)."""
        self.vad_model, self.vad_utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True
        )
        self.vad_model.eval()

    def decode_audio_bytes(self, raw_bytes: bytes, source_sample_rate: int = 48000) -> np.ndarray:
        """
        Decode raw audio bytes (from the browser mic) into a numpy float32 array.

        Browser MediaRecorder typically sends:
        - WebM/Opus at 48kHz (Chrome/Edge)
        - OGG/Opus at 48kHz (Firefox)
        - Or raw PCM float32 if David's frontend sends it that way

        Args:
            raw_bytes: Raw audio data from Redis
            source_sample_rate: Sample rate of the incoming audio (browser default: 48kHz)

        Returns:
            numpy float32 array normalized to [-1.0, 1.0], resampled to 16kHz mono
        """
        # Try decoding as raw PCM float32 first (simplest case)
        # If David's frontend sends raw Float32Array from AudioWorklet, this works directly
        try:
            audio = np.frombuffer(raw_bytes, dtype=np.float32)
        except ValueError:
            # Fallback: try as int16 PCM (common format)
            audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Handle stereo → mono by averaging channels
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # Resample to 16kHz (what Whisper expects)
        if source_sample_rate != SAMPLE_RATE:
            num_samples = int(len(audio) * SAMPLE_RATE / source_sample_rate)
            audio = resample(audio, num_samples)

        # Normalize to [-1.0, 1.0]
        max_val = np.abs(audio).max()
        if max_val > 0:
            audio = audio / max_val

        return audio.astype(np.float32)

    def reduce_noise(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply spectral gating noise reduction.

        This helps a LOT with Nigerian classroom/office environments where
        there's background noise from generators, fans, traffic, etc.

        Args:
            audio: 16kHz float32 numpy array

        Returns:
            Denoised audio array (same shape)
        """
        return nr.reduce_noise(
            y=audio,
            sr=SAMPLE_RATE,
            stationary=False,  # Non-stationary = handles varying noise (generators, etc.)
            prop_decrease=0.75  # How aggressively to reduce noise (0.0-1.0)
        )

    def detect_speech_segments(self, audio: np.ndarray) -> list[dict]:
        """
        Use Silero VAD to find segments where someone is actually speaking.

        This is critical for real-time performance:
        - Avoids wasting GPU cycles transcribing silence/noise
        - Gives natural breakpoints for chunked transcription
        - Works well with accented speech (Silero is accent-agnostic)

        Args:
            audio: 16kHz float32 numpy array

        Returns:
            List of dicts with 'start' and 'end' sample indices:
            [{"start": 0, "end": 16000}, {"start": 32000, "end": 48000}]
        """
        # Silero VAD expects a torch tensor
        audio_tensor = torch.from_numpy(audio).float()

        # Get speech timestamps (in samples, not seconds)
        speech_timestamps = self.vad_utils[0](
            audio_tensor,
            self.vad_model,
            sampling_rate=SAMPLE_RATE,
            threshold=VAD_THRESHOLD,
            min_silence_duration_ms=int(VAD_MIN_SILENCE * 1000),
            min_speech_duration_ms=250  # Ignore speech shorter than 250ms (likely noise)
        )

        return speech_timestamps

    def extract_speech_audio(self, audio: np.ndarray, segments: list[dict]) -> np.ndarray:
        """
        Extract only the speech portions from the audio, concatenated together.

        Args:
            audio: Full audio array
            segments: Speech segments from detect_speech_segments()

        Returns:
            Concatenated speech-only audio
        """
        if not segments:
            return np.array([], dtype=np.float32)

        speech_parts = []
        for seg in segments:
            start = seg["start"]
            end = seg["end"]
            speech_parts.append(audio[start:end])

        return np.concatenate(speech_parts)

    def process(self, raw_bytes: bytes, source_sample_rate: int = 48000) -> np.ndarray | None:
        """
        Full preprocessing pipeline: decode → resample → denoise → VAD → extract speech.

        This is the main method called by stream_processor.py.

        Args:
            raw_bytes: Raw audio data from Redis
            source_sample_rate: Sample rate of incoming audio

        Returns:
            Clean speech-only audio ready for Whisper, or None if no speech detected
        """
        # Step 1: Decode and resample
        audio = self.decode_audio_bytes(raw_bytes, source_sample_rate)

        # Step 2: Noise reduction
        audio = self.reduce_noise(audio)

        # Step 3: VAD — find speech segments
        segments = self.detect_speech_segments(audio)

        if not segments:
            return None  # No speech detected, skip transcription

        # Step 4: Extract speech-only audio
        speech_audio = self.extract_speech_audio(audio, segments)

        return speech_audio
