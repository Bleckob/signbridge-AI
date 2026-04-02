# ASR Engine — SignBridge

Automatic Speech Recognition service for SignBridge. Converts live audio streams into text, optimized for Nigerian-accented English.

**Model:** [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2-optimized Whisper)

## Architecture

```
Redis "audio-chunks" (from backend)
        │
        ▼
 stream_processor.py  ← main entry point, buffers & orchestrates
        │
        ├─► audio_preprocessor.py  ← resample, denoise, VAD
        ├─► transcriber.py         ← faster-whisper inference
        └─► postprocessor.py       ← Nigerian English text cleanup
        │
        ▼
Redis "transcriptions" (to NLP engine)
```

## Setup

```bash
# From the asr-engine directory:
pip install -r requirements.txt

# Download model weights (one-time):
python scripts/download_model.py          # downloads "base" model
python scripts/download_model.py large-v3 # or specify a size
```

## Run

```bash
# Start the ASR worker (listens to Redis for audio chunks):
cd services/asr-engine
python -m src.stream_processor
```

## Configuration

Set these in `services/.env` or as environment variables:

| Variable | Default | Description |
|---|---|---|
| `ASR_MODEL_SIZE` | `base` | Whisper model: tiny, base, small, medium, large-v3 |
| `ASR_DEVICE` | `auto` | `cuda` for GPU, `cpu` for CPU, `auto` to detect |
| `ASR_COMPUTE_TYPE` | `int8` | `float16` (GPU), `int8` (CPU), `float32` (max accuracy) |
| `ASR_BEAM_SIZE` | `5` | Higher = more accurate but slower |
| `ASR_VAD_THRESHOLD` | `0.4` | Voice detection sensitivity (0.0-1.0) |
| `ASR_MIN_CONFIDENCE` | `-1.0` | Min log probability to accept transcription |

## Testing

```bash
pytest tests/ -v

# Benchmark against Nigerian accent samples:
python scripts/benchmark.py --data-dir ./benchmark_data
```

## Redis Streams

| Stream | Direction | Format |
|---|---|---|
| `audio-chunks` | INPUT (from backend) | `{session_id, data: json}` |
| `transcriptions` | OUTPUT (to NLP engine) | `{session_id, text, confidence, language}` |

## Fine-tuning for Nigerian English

To improve accuracy on Nigerian-accented speech:

1. Collect audio samples from Nigerian English speakers
2. Create `benchmark_data/` with .wav files and `references.json`
3. Run `python scripts/benchmark.py --data-dir ./benchmark_data` to measure baseline WER
4. Fine-tune using HuggingFace + LoRA (see docs/fine-tuning.md — TBD)
5. Re-benchmark to measure improvement
