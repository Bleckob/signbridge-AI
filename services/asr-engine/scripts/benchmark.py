"""
Benchmark Script
================
Tests ASR accuracy against audio files with known transcriptions.

Use this to:
1. Compare model sizes (base vs medium vs large-v3)
2. Measure Word Error Rate (WER) on Nigerian-accented speech
3. Validate fine-tuning improvements

Setup:
    Create a folder with test audio files and a references.json:
    benchmark_data/
        sample_01.wav
        sample_02.wav
        references.json  ← {"sample_01.wav": "expected text here", ...}

Usage:
    python scripts/benchmark.py --data-dir ./benchmark_data
    python scripts/benchmark.py --data-dir ./benchmark_data --model large-v3
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from scipy.io import wavfile

from src.transcriber import Transcriber
from src.postprocessor import Postprocessor


def word_error_rate(reference: str, hypothesis: str) -> float:
    """
    Compute Word Error Rate (WER) between reference and hypothesis.

    WER = (Substitutions + Insertions + Deletions) / Words in Reference

    Standard ASR metric. Lower is better. 0.0 = perfect, 1.0 = completely wrong.
    """
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()

    # Dynamic programming (Levenshtein distance at word level)
    d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]

    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = 1 + min(
                    d[i - 1][j],      # deletion
                    d[i][j - 1],      # insertion
                    d[i - 1][j - 1],  # substitution
                )

    if len(ref_words) == 0:
        return 0.0 if len(hyp_words) == 0 else 1.0

    return d[len(ref_words)][len(hyp_words)] / len(ref_words)


def run_benchmark(data_dir: str):
    data_path = Path(data_dir)
    refs_file = data_path / "references.json"

    if not refs_file.exists():
        print(f"Error: {refs_file} not found.")
        print("Create a references.json mapping audio filenames to expected transcriptions.")
        sys.exit(1)

    with open(refs_file) as f:
        references = json.load(f)

    print(f"Found {len(references)} test samples in {data_dir}\n")

    # Initialize pipeline
    transcriber = Transcriber()
    postprocessor = Postprocessor()

    results = []
    total_wer = 0.0

    for filename, expected_text in references.items():
        filepath = data_path / filename
        if not filepath.exists():
            print(f"  SKIP: {filename} not found")
            continue

        # Load audio file
        sample_rate, audio = wavfile.read(str(filepath))
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0

        # Resample to 16kHz if needed
        if sample_rate != 16000:
            from scipy.signal import resample
            num_samples = int(len(audio) * 16000 / sample_rate)
            audio = resample(audio, num_samples).astype(np.float32)

        # Transcribe
        result = transcriber.transcribe(audio)
        if result is None:
            hypothesis = ""
        else:
            hypothesis = postprocessor.clean_text(result.text)

        # Calculate WER
        wer = word_error_rate(expected_text, hypothesis)
        total_wer += wer

        results.append({
            "file": filename,
            "expected": expected_text,
            "got": hypothesis,
            "wer": round(wer, 3),
        })

        status = "OK" if wer < 0.2 else "WARN" if wer < 0.5 else "FAIL"
        print(f"  [{status}] {filename}: WER={wer:.1%}")
        print(f"         Expected: {expected_text}")
        print(f"         Got:      {hypothesis}\n")

    # Summary
    avg_wer = total_wer / len(results) if results else 0
    print("=" * 60)
    print(f"RESULTS: {len(results)} samples, Average WER: {avg_wer:.1%}")
    print(f"  {'PASS' if avg_wer < 0.25 else 'NEEDS IMPROVEMENT'}")
    print(f"  Target: < 25% WER for Nigerian-accented English")
    print("=" * 60)

    # Save detailed results
    output_file = data_path / "benchmark_results.json"
    with open(output_file, "w") as f:
        json.dump({"average_wer": round(avg_wer, 3), "results": results}, f, indent=2)
    print(f"\nDetailed results saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark ASR accuracy")
    parser.add_argument("--data-dir", required=True, help="Path to benchmark data folder")
    args = parser.parse_args()
    run_benchmark(args.data_dir)
