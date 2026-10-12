"""Build-metric anomaly detection.

Records each run's duration to metrics/history.jsonl and flags the latest run if it
deviates from the rolling baseline by more than THRESHOLD standard deviations (z-score).
This is the honest, CI-sized version of the "detect deviations from normal build patterns"
idea: a statistical baseline, not a trained ML model. Same intent (isolation-forest /
autoencoder articles approximate the same signal), far less to operate.

Usage: python scripts/anomaly_check.py <duration_seconds>
Exit 0 always (anomaly is a signal, not a failure); prints a GITHUB_STEP_SUMMARY-friendly note.
"""

import json
import os
import pathlib
import statistics
import sys

HIST = pathlib.Path("metrics/history.jsonl")
THRESHOLD = 3.0  # z-score beyond which we flag
MIN_SAMPLES = 5  # need a baseline before flagging


def main() -> int:
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    HIST.parent.mkdir(exist_ok=True)

    past = []
    if HIST.exists():
        for line in HIST.read_text().splitlines():
            try:
                past.append(json.loads(line)["duration"])
            except (json.JSONDecodeError, KeyError):
                continue

    verdict = "baseline"
    detail = f"duration={duration:.1f}s"
    if len(past) >= MIN_SAMPLES:
        mean = statistics.mean(past)
        stdev = statistics.pstdev(past) or 1e-9
        z = (duration - mean) / stdev
        if abs(z) > THRESHOLD:
            verdict = "ANOMALY"
            detail = f"duration={duration:.1f}s vs mean={mean:.1f}s (z={z:+.2f})"
        else:
            verdict = "normal"
            detail = f"duration={duration:.1f}s vs mean={mean:.1f}s (z={z:+.2f})"

    # append current run to history
    with HIST.open("a") as f:
        f.write(json.dumps({"duration": duration}) + "\n")

    line = f"Build metric: {verdict} — {detail}"
    print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            icon = "🚨" if verdict == "ANOMALY" else "📊"
            f.write(f"{icon} {line}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
