"""A/B experiment — compare two models on the golden dataset."""

from __future__ import annotations

import json
import sys
import io
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from store_analytics.config import DATABASE_PATH
from store_analytics.db.seed import seed_database
from store_analytics.evals.harness import run_evals, save_results, print_summary

# Ensure database exists
if not DATABASE_PATH.exists():
    seed_database(DATABASE_PATH)


def run_experiment(model_a: str, model_b: str, max_cases: int | None = None) -> dict:
    """
    Run both models on the same dataset and return comparison results.

    Both models use the same golden dataset, same seed, same DB.
    Only the LLM model differs.
    """
    import os
    os.environ["AGENT_MODEL"] = model_a
    # Force re-import of config
    import importlib
    import store_analytics.config as config_mod
    importlib.reload(config_mod)
    import store_analytics.llm as llm_mod
    importlib.reload(llm_mod)
    import store_analytics.agent as agent_mod
    importlib.reload(agent_mod)

    print(f"\n{'='*60}")
    print(f"EXPERIMENT A: {model_a}")
    print(f"{'='*60}")
    results_a = run_evals("data/golden.json", max_cases=max_cases)
    print_summary(results_a)

    # Switch to model B
    os.environ["AGENT_MODEL"] = model_b
    importlib.reload(config_mod)
    importlib.reload(llm_mod)
    importlib.reload(agent_mod)

    print(f"\n{'='*60}")
    print(f"EXPERIMENT B: {model_b}")
    print(f"{'='*60}")
    results_b = run_evals("data/golden.json", max_cases=max_cases)
    print_summary(results_b)

    return {"model_a": model_a, "model_b": model_b, "results_a": results_a, "results_b": results_b}


def print_comparison_table(comparison: dict) -> None:
    """Print a side-by-side comparison table."""
    a = comparison["results_a"]
    b = comparison["results_b"]
    model_a = comparison["model_a"]
    model_b = comparison["model_b"]

    # Truncate model names for display
    ma = model_a.split("/")[-1][:20]
    mb = model_b.split("/")[-1][:20]

    print(f"\n{'='*80}")
    print(f"A/B COMPARISON: {ma} vs {mb}")
    print(f"{'='*80}")
    print(f"{'Metric':<30} {ma:>20} {mb:>20} {'Winner':>10}")
    print(f"{'-'*30} {'-'*20} {'-'*20} {'-'*10}")

    metrics = [
        ("Tool Selection", "tool_selection_accuracy"),
        ("Task Completion", "task_completion_rate"),
        ("Tool Validity", "tool_validity_rate"),
        ("No Hallucination", "no_hallucination_rate"),
        ("Error Handling", "error_handling_rate"),
        ("Trajectory Quality", "trajectory_quality_avg"),
    ]

    a_wins = 0
    b_wins = 0

    for name, attr in metrics:
        va = getattr(a, attr)
        vb = getattr(b, attr)
        winner = ma if va > vb else (mb if vb > va else "TIE")
        if va > vb:
            a_wins += 1
        elif vb > va:
            b_wins += 1
        print(f"{name:<30} {va:>20.3f} {vb:>20.3f} {winner:>10}")

    # Additional metrics
    print(f"{'-'*30} {'-'*20} {'-'*20} {'-'*10}")
    a_latency = a.total_latency_ms / max(a.total_cases, 1)
    b_latency = b.total_latency_ms / max(b.total_cases, 1)
    winner_lat = ma if a_latency < b_latency else (mb if b_latency < a_latency else "TIE")
    print(f"{'Avg Latency (ms)':<30} {a_latency:>20.0f} {b_latency:>20.0f} {winner_lat:>10}")

    a_tokens = a.total_tokens / max(a.total_cases, 1)
    b_tokens = b.total_tokens / max(b.total_cases, 1)
    winner_tok = ma if a_tokens < b_tokens else (mb if b_tokens < a_tokens else "TIE")
    print(f"{'Avg Tokens/Case':<30} {a_tokens:>20.0f} {b_tokens:>20.0f} {winner_tok:>10}")

    a_passed = a.cases_passed / max(a.total_cases, 1) * 100
    b_passed = b.cases_passed / max(b.total_cases, 1) * 100
    winner_pass = ma if a_passed > b_passed else (mb if b_passed > a_passed else "TIE")
    print(f"{'Cases Passed %':<30} {a_passed:>19.1f}% {b_passed:>19.1f}% {winner_pass:>10}")

    print(f"{'-'*30} {'-'*20} {'-'*20} {'-'*10}")
    print(f"{'Score':<30} {a_wins:>20} {b_wins:>20}")

    print(f"\n{'='*80}")
    print("CONCLUSION:")
    if a_wins > b_wins:
        print(f"  {ma} wins on {a_wins}/{len(metrics)} metrics.")
        print(f"  Recommendation: Use {ma}")
    elif b_wins > a_wins:
        print(f"  {mb} wins on {b_wins}/{len(metrics)} metrics.")
        print(f"  Recommendation: Use {mb}")
    else:
        print(f"  Tie! Both models perform similarly.")
        # Break tie by latency
        if a_latency < b_latency:
            print(f"  {ma} is faster, recommend for production.")
        else:
            print(f"  {mb} is faster, recommend for production.")
    print(f"{'='*80}\n")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="A/B experiment comparing two models")
    parser.add_argument("--model-a", default="openai/gpt-oss-120b", help="Model A (default: openai/gpt-oss-120b)")
    parser.add_argument("--model-b", default="qwen/qwen3.8-27b", help="Model B (default: qwen/qwen3.8-27b)")
    parser.add_argument("--max-cases", type=int, default=30, help="Max cases per model (default: 30)")
    parser.add_argument("--output", default="data/ab_results.json", help="Output file")
    args = parser.parse_args()

    comparison = run_experiment(args.model_a, args.model_b, max_cases=args.max_cases)
    print_comparison_table(comparison)

    # Save results
    output = {
        "model_a": comparison["model_a"],
        "model_b": comparison["model_b"],
        "results_a": {
            "tool_selection_accuracy": comparison["results_a"].tool_selection_accuracy,
            "task_completion_rate": comparison["results_a"].task_completion_rate,
            "no_hallucination_rate": comparison["results_a"].no_hallucination_rate,
            "error_handling_rate": comparison["results_a"].error_handling_rate,
            "trajectory_quality_avg": comparison["results_a"].trajectory_quality_avg,
            "total_latency_ms": comparison["results_a"].total_latency_ms,
            "total_tokens": comparison["results_a"].total_tokens,
            "cases_passed": comparison["results_a"].cases_passed,
            "total_cases": comparison["results_a"].total_cases,
        },
        "results_b": {
            "tool_selection_accuracy": comparison["results_b"].tool_selection_accuracy,
            "task_completion_rate": comparison["results_b"].task_completion_rate,
            "no_hallucination_rate": comparison["results_b"].no_hallucination_rate,
            "error_handling_rate": comparison["results_b"].error_handling_rate,
            "trajectory_quality_avg": comparison["results_b"].trajectory_quality_avg,
            "total_latency_ms": comparison["results_b"].total_latency_ms,
            "total_tokens": comparison["results_b"].total_tokens,
            "cases_passed": comparison["results_b"].cases_passed,
            "total_cases": comparison["results_b"].total_cases,
        },
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
