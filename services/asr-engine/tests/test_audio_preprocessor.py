"""Tests for the AudioPreprocessor module."""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.audio_preprocessor import AudioPreprocessor


class TestAudioPreprocessor:
    """Tests that can run without GPU or model downloads."""

    def setup_method(self):
        """Note: Full init loads Silero VAD. Skip if testing without torch."""
        pass

    def test_decode_float32_pcm(self):
        """Decoding raw float32 PCM bytes should produce a valid numpy array."""
        # Simulate 1 second of 48kHz float32 silence
        silence = np.zeros(48000, dtype=np.float32)
        raw_bytes = silence.tobytes()

        preprocessor = AudioPreprocessor()
        result = preprocessor.decode_audio_bytes(raw_bytes, source_sample_rate=48000)

        # Should be resampled to 16kHz
        assert len(result) == 16000
        assert result.dtype == np.float32

    def test_decode_int16_pcm(self):
        """Decoding int16 PCM should normalize to [-1, 1] float32."""
        # 1 second of 16kHz int16 audio (half-volume sine wave)
        t = np.linspace(0, 1, 16000, dtype=np.float32)
        sine = (np.sin(2 * np.pi * 440 * t) * 16384).astype(np.int16)
        raw_bytes = sine.tobytes()

        preprocessor = AudioPreprocessor()
        result = preprocessor.decode_audio_bytes(raw_bytes, source_sample_rate=16000)

        assert result.dtype == np.float32
        assert np.abs(result).max() <= 1.0

    def test_reduce_noise_preserves_shape(self):
        """Noise reduction should not change the audio length."""
        audio = np.random.randn(16000).astype(np.float32) * 0.1
        preprocessor = AudioPreprocessor()
        denoised = preprocessor.reduce_noise(audio)

        assert len(denoised) == len(audio)

    def test_extract_speech_empty_segments(self):
        """No segments should return empty array."""
        audio = np.zeros(16000, dtype=np.float32)
        preprocessor = AudioPreprocessor()
        result = preprocessor.extract_speech_audio(audio, [])

        assert len(result) == 0

    def test_extract_speech_with_segments(self):
        """Should extract only the specified segments."""
        audio = np.arange(32000, dtype=np.float32)
        segments = [
            {"start": 0, "end": 8000},
            {"start": 16000, "end": 24000},
        ]
        preprocessor = AudioPreprocessor()
        result = preprocessor.extract_speech_audio(audio, segments)

        assert len(result) == 16000  # Two 8000-sample segments


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
