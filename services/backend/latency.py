import time
from typing import Dict, List
from collections import defaultdict

# In-memory storage for latency measurements
# Key: stage name, Value: list of measured times in milliseconds
# Example: {"audio_capture": [245, 251, 248], "asr_engine": [298, 310, 305]}
latency_records: Dict[str, List[float]] = defaultdict(list)


def record_latency(stage: str, duration_ms: float):
    """
    Records a latency measurement for a specific pipeline stage.
    Called every time a stage completes.

    stage: name of the pipeline stage
           Example: "audio_capture", "asr_engine", "nlp_engine",
                    "pose_lookup", "pipeline_total"
    duration_ms: how long the stage took in milliseconds
    """
    latency_records[stage].append(duration_ms)

    # Keep only the last 100 measurements per stage
    # This prevents memory from growing forever
    if len(latency_records[stage]) > 100:
        latency_records[stage] = latency_records[stage][-100:]

    print(f"Latency recorded — {stage}: {duration_ms:.2f}ms")


def calculate_percentile(measurements: List[float], percentile: int) -> float:
    """
    Calculates a percentile from a list of measurements.

    measurements: list of latency values
    percentile: which percentile to calculate (50 or 95)

    p50 = the middle value — 50% of requests are faster than this
    p95 = 95% of requests are faster than this
          This shows your worst case performance
    """
    if not measurements:
        return 0.0

    sorted_measurements = sorted(measurements)
    index = int(len(sorted_measurements) * percentile / 100)

    # Make sure index doesn't go out of bounds
    index = min(index, len(sorted_measurements) - 1)
    return round(sorted_measurements[index], 2)


def get_latency_stats() -> dict:
    """
    Returns p50 and p95 latency stats for every pipeline stage.
    Used by your /latency-stats endpoint.
    """
    stats = {}

    # Define all pipeline stages in order
    all_stages = [
        "audio_capture",
        "asr_engine",
        "nlp_engine",
        "pose_lookup",
        "pipeline_total"
    ]

    for stage in all_stages:
        measurements = latency_records.get(stage, [])

        if measurements:
            stats[stage] = {
                "p50_ms": calculate_percentile(measurements, 50),
                "p95_ms": calculate_percentile(measurements, 95),
                "total_measurements": len(measurements),
                "latest_ms": round(measurements[-1], 2),
                "status": "within budget ✅" if calculate_percentile(measurements, 95) < 1500 else "over budget ❌"
            }
        else:
            stats[stage] = {
                "p50_ms": 0,
                "p95_ms": 0,
                "total_measurements": 0,
                "latest_ms": 0,
                "status": "no data yet ⏳"
            }

    return stats


class StageTimer:
    """
    A simple timer for measuring how long a stage takes.

    Usage:
        timer = StageTimer("pose_lookup")
        timer.start()
        # ... do your work ...
        timer.stop()  # automatically records the latency
    """

    def __init__(self, stage: str):
        self.stage = stage
        self.start_time = None

    def start(self):
        """Start the timer"""
        self.start_time = time.time()

    def stop(self):
        """
        Stop the timer and automatically record the latency.
        Returns the duration in milliseconds.
        """
        if self.start_time is None:
            print(f"Timer for {self.stage} was never started!")
            return 0.0

        duration_ms = (time.time() - self.start_time) * 1000
        record_latency(self.stage, duration_ms)
        return duration_ms
