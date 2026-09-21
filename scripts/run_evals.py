"""CLI entry point for running the evaluation harness."""

from __future__ import annotations

import sys
import io
from pathlib import Path

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from store_analytics.config import DATABASE_PATH
from store_analytics.db.seed import seed_database
from store_analytics.evals.harness import run_evals, save_results, print_summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run evaluation harness on golden dataset")
    parser.add_argument("--dataset", default="data/golden.json", help="Path to golden dataset")
    parser.add_argument("--output", default="data/eval_results.json", help="Path to save results")
    parser.add_argument("--max-cases", type=int, default=None, help="Limit number of cases")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-case progress")
    parser.add_argument("--quick", action="store_true", help="Run first 5 cases only (smoke test)")
    args = parser.parse_args()

    # Ensure database exists
    if not DATABASE_PATH.exists():
        print("Seeding database...")
        seed_database(DATABASE_PATH)

    if args.quick:
        args.max_cases = 5
        args.verbose = True

    print(f"Running evals on {args.dataset}...")
    results = run_evals(
        args.dataset,
        verbose=args.verbose,
        max_cases=args.max_cases,
    )

    print_summary(results)
    save_results(results, args.output)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
