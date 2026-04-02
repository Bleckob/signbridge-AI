import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the services root (shared with Blessing's backend)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ---------------------------------------------------------------------------
# Model settings
# ---------------------------------------------------------------------------
# Model size: "tiny", "base", "small", "medium", "large-v3"
# Start with "base" for dev speed, switch to "large-v3" for production accuracy
MODEL_SIZE = os.getenv("ASR_MODEL_SIZE", "base")

# Where to cache downloaded model weights (gitignored)
MODEL_DIR = Path(__file__).parent.parent / "models"

# Device: "cuda" for GPU, "cpu" for CPU-only, "auto" to let faster-whisper decide
DEVICE = os.getenv("ASR_DEVICE", "auto")

# Compute type: "float16" for GPU (faster), "int8" for CPU (lower memory), "float32" for max accuracy
COMPUTE_TYPE = os.getenv("ASR_COMPUTE_TYPE", "int8")

# ---------------------------------------------------------------------------
# Audio settings
# ---------------------------------------------------------------------------
# Whisper expects 16kHz mono audio — all incoming audio gets resampled to this
SAMPLE_RATE = 16000

# Minimum audio duration (seconds) before attempting transcription
# Too short = garbage output. Too long = latency.
MIN_AUDIO_DURATION = 1.0

# Maximum audio buffer (seconds) before forcing transcription
# Prevents memory buildup if someone talks nonstop
MAX_AUDIO_BUFFER = 30.0

# ---------------------------------------------------------------------------
# VAD (Voice Activity Detection) settings
# ---------------------------------------------------------------------------
# Silero VAD threshold: 0.0 (everything is speech) to 1.0 (only loud clear speech)
# Lower = more sensitive, higher = stricter. 0.4 works well for accented speech.
VAD_THRESHOLD = float(os.getenv("ASR_VAD_THRESHOLD", "0.4"))

# Minimum silence duration (seconds) to consider a speech segment "done"
VAD_MIN_SILENCE = 0.5

# ---------------------------------------------------------------------------
# Transcription settings
# ---------------------------------------------------------------------------
# Language: "en" for English. Whisper auto-detects if set to None,
# but forcing "en" avoids misdetection of Nigerian-accented English as other languages
LANGUAGE = "en"

# Beam size for decoding: higher = more accurate but slower
# 5 is a good balance. Use 1 for fastest, 10 for best accuracy.
BEAM_SIZE = int(os.getenv("ASR_BEAM_SIZE", "5"))

# Minimum confidence (log probability) to accept a transcription segment
# Segments below this get discarded as unreliable
MIN_CONFIDENCE = float(os.getenv("ASR_MIN_CONFIDENCE", "-1.0"))

# ---------------------------------------------------------------------------
# Redis stream keys — how your service connects to the rest of the pipeline
# ---------------------------------------------------------------------------
# INPUT: Blessing's backend pushes audio chunks here (see backend/main.py line 79)
REDIS_INPUT_STREAM = "audio-chunks"

# OUTPUT: You push transcription results here for Amos's NLP engine to consume
REDIS_OUTPUT_STREAM = "transcriptions"

# Consumer group name — allows multiple ASR workers to share the load
REDIS_CONSUMER_GROUP = "asr-workers"

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
