"""Gate script — checks eval results against thresholds and exits 1 if any fail."""

from __future__ import annotations

import json
import sys
import io
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Thresholds — tune these based on acceptable quality
THRESHOLDS = {
    "tool_selection_accuracy": 0.85,
    "task_completion_rate": 0.80,
    "tool_validity_rate": 0.95,
    "no_hallucination_rate": 0.90,
    "error_handling_rate": 0.85,
    "trajectory_quality_avg": 0.60,
}

MAX_HALLUCINATED_NUMBERS = 0  # Zero tolerance for hallucinated numbers


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Gate check on eval results")
    parser.add_argument("--results", default="data/eval_results.json", help="Path to results JSON")
    args = parser.parse_args()

    with open(args.results, encoding='utf-8') as f:
        data = json.load(f)

    failures = []

    # Check metric thresholds
    for metric, threshold in THRESHOLDS.items():
        value = data.get(metric, 0)
        status = "PASS" if value >= threshold else "FAIL"
        print(f"  {metric:30s}  {value:.3f}  {'>=' if value >= threshold else '<'}  {threshold:.3f}  [{status}]")
        if value < threshold:
            failures.append(f"{metric}: {value:.3f} < {threshold:.3f}")

    # Check hallucination count
    halluc_count = sum(
        1 for c in data.get("cases", [])
        if c.get("no_hallucination", 1.0) < 0.5
    )
    halluc_status = "PASS" if halluc_count <= MAX_HALLUCINATED_NUMBERS else "FAIL"
    print(f"  {'hallucinated_numbers_count':30s}  {halluc_count}  {'<=' if halluc_count <= MAX_HALLUCINATED_NUMBERS else '>'}  {MAX_HALLUCINATED_NUMBERS}  [{halluc_status}]")
    if halluc_count > MAX_HALLUCINATED_NUMBERS:
        failures.append(f"hallucinated_numbers: {halluc_count} > {MAX_HALLUCINATED_NUMBERS}")

    # Check for regression cases
    regression_cases = [c for c in data.get("cases", []) if c.get("id", "").startswith("reg_")]
    reg_failures = [c for c in regression_cases if c.get("task_completion", 0) < 0.5]
    if reg_failures:
        print(f"\n  REGRESSION CASES FAILED: {[c['id'] for c in reg_failures]}")
        failures.append(f"regression_failures: {len(reg_failures)}")

    print()
    if failures:
        print(f"GATE FAILED — {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("GATE PASSED — all metrics within thresholds")
        sys.exit(0)


if __name__ == "__main__":
    main()
