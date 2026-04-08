"""
Model Download Script
=====================
Downloads and caches the faster-whisper model weights.

Run this ONCE before starting the ASR service:
    python scripts/download_model.py

By default downloads the model set in ASR_MODEL_SIZE env var (or "base").
Pass a model name to override:
    python scripts/download_model.py large-v3
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from faster_whisper import WhisperModel
from config.asr_config import MODEL_SIZE, MODEL_DIR, DEVICE, COMPUTE_TYPE


def download_model(model_size: str | None = None):
    size = model_size or MODEL_SIZE
    print(f"Downloading Whisper model: {size}")
    print(f"Cache directory: {MODEL_DIR}")
    print(f"Device: {DEVICE}, Compute type: {COMPUTE_TYPE}")
    print("This may take a few minutes on first run...\n")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Loading the model triggers the download if not cached
    WhisperModel(
        size,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        download_root=str(MODEL_DIR),
    )

    print(f"\nModel '{size}' downloaded and cached successfully.")
    print(f"Location: {MODEL_DIR}")
    print("You can now start the ASR service.")


if __name__ == "__main__":
    override = sys.argv[1] if len(sys.argv) > 1 else None
    download_model(override)
