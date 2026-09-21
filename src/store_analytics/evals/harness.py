"""Main evaluation harness — runs agent on golden dataset and computes all metrics."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ..agent import run_agent
from ..types import AgentResult
from .metrics import (
    tool_selection_accuracy,
    tool_call_validity,
    no_hallucinated_numbers,
    error_handling,
)
from .judge import trajectory_quality, task_completion_with_judge


@dataclass
class CaseResult:
    """Result of evaluating a single test case."""

    id: str
    input: str
    expected_tools: list[str]
    category: str
    difficulty: str
    should_refuse: bool

    # Agent output
    final_answer: str = ""
    trajectory: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # Metric scores (0.0 - 1.0)
    tool_selection: float = 0.0
    tool_selection_details: str = ""
    task_completion: float = 0.0
    task_completion_details: str = ""
    tool_validity: float = 0.0
    tool_validity_details: str = ""
    no_hallucination: float = 0.0
    no_hallucination_details: str = ""
    error_handling_score: float = 0.0
    error_handling_details: str = ""
    trajectory_quality_score: float = 0.0
    trajectory_quality_details: str = ""

    # Timing
    eval_latency_ms: float = 0.0


@dataclass
class EvalResults:
    """Aggregated results from the full evaluation run."""

    total_cases: int = 0
    cases_passed: int = 0
    cases: list[CaseResult] = field(default_factory=list)

    # Aggregate metrics
    tool_selection_accuracy: float = 0.0
    task_completion_rate: float = 0.0
    tool_validity_rate: float = 0.0
    no_hallucination_rate: float = 0.0
    error_handling_rate: float = 0.0
    trajectory_quality_avg: float = 0.0

    # Cost/latency
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    total_tool_calls: int = 0

    # By category breakdown
    by_category: dict = field(default_factory=dict)
    by_difficulty: dict = field(default_factory=dict)


def load_dataset(path: str | Path) -> list[dict]:
    """Load the golden dataset from a JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate_case(case: dict, *, verbose: bool = False) -> CaseResult:
    """Run the agent on a single case and compute all metrics."""
    t0 = time.perf_counter()

    # Run agent
    result = run_agent(case["input"], verbose=verbose)

    # Build case result
    cr = CaseResult(
        id=case["id"],
        input=case["input"],
        expected_tools=case["expected_tools"],
        category=case["category"],
        difficulty=case["difficulty"],
        should_refuse=case["should_refuse"],
        final_answer=result.final_answer,
        trajectory=[{
            "tool_name": tc.tool_name,
            "arguments": tc.arguments,
            "result": tc.result[:500] if tc.result else "",
            "success": tc.success,
            "latency_ms": tc.latency_ms,
        } for tc in result.trajectory],
        metadata={
            "total_tokens": result.metadata.total_tokens,
            "prompt_tokens": result.metadata.prompt_tokens,
            "completion_tokens": result.metadata.completion_tokens,
            "num_tool_calls": result.metadata.num_tool_calls,
            "latency_ms": result.metadata.latency_ms,
            "model_used": result.metadata.model_used,
        },
    )

    # --- Metric 1: Tool Selection ---
    ts = tool_selection_accuracy(result, case["expected_tools"])
    cr.tool_selection = ts["score"]
    cr.tool_selection_details = ts["details"]

    # --- Metric 2: Task Completion ---
    tc_metric = task_completion_with_judge(result, case["input"], case["acceptance_criteria"])
    cr.task_completion = tc_metric["score"]
    cr.task_completion_details = tc_metric["details"]

    # --- Metric 3: Tool Validity ---
    tv = tool_call_validity(result)
    cr.tool_validity = tv["score"]
    cr.tool_validity_details = json.dumps(tv["details"], default=str)

    # --- Metric 4: No Hallucination ---
    nh = no_hallucinated_numbers(result)
    cr.no_hallucination = nh["score"]
    cr.no_hallucination_details = nh["details"]

    # --- Metric 5: Error Handling ---
    eh = error_handling(result, case["should_refuse"])
    cr.error_handling_score = eh["score"]
    cr.error_handling_details = eh["details"]

    # --- Metric 6: Trajectory Quality ---
    tq = trajectory_quality(result, case["input"], case["expected_tools"], case["acceptance_criteria"])
    cr.trajectory_quality_score = tq["score"]
    cr.trajectory_quality_details = tq["details"]

    cr.eval_latency_ms = (time.perf_counter() - t0) * 1000

    return cr


def run_evals(
    dataset_path: str | Path,
    *,
    verbose: bool = False,
    max_cases: int | None = None,
    judge_cases: bool = True,
) -> EvalResults:
    """
    Run the full evaluation harness on the golden dataset.

    Args:
        dataset_path: Path to golden.json
        verbose: Print progress per case
        max_cases: Limit number of cases (for testing)
        judge_cases: Whether to call LLM judge for trajectory quality
    """
    dataset = load_dataset(dataset_path)
    if max_cases:
        dataset = dataset[:max_cases]

    results = EvalResults(total_cases=len(dataset))

    for i, case in enumerate(dataset):
        if verbose:
            print(f"[{i+1}/{len(dataset)}] {case['id']}: {case['input'][:60]}...")

        try:
            cr = evaluate_case(case, verbose=False)
        except Exception as e:
            cr = CaseResult(
                id=case["id"],
                input=case["input"],
                expected_tools=case["expected_tools"],
                category=case["category"],
                difficulty=case["difficulty"],
                should_refuse=case["should_refuse"],
                final_answer=f"ERROR: {e}",
                error_handling_score=0.0,
                error_handling_details=f"Agent crashed: {e}",
            )

        results.cases.append(cr)

        # Aggregate
        results.total_latency_ms += cr.metadata.get("latency_ms", 0)
        results.total_tokens += cr.metadata.get("total_tokens", 0)
        results.total_tool_calls += cr.metadata.get("num_tool_calls", 0)

        # Category breakdown
        cat = cr.category
        if cat not in results.by_category:
            results.by_category[cat] = {"count": 0, "tool_selection": 0, "task_completion": 0}
        results.by_category[cat]["count"] += 1
        results.by_category[cat]["tool_selection"] += cr.tool_selection
        results.by_category[cat]["task_completion"] += cr.task_completion

        # Difficulty breakdown
        diff = cr.difficulty
        if diff not in results.by_difficulty:
            results.by_difficulty[diff] = {"count": 0, "tool_selection": 0, "task_completion": 0}
        results.by_difficulty[diff]["count"] += 1
        results.by_difficulty[diff]["tool_selection"] += cr.tool_selection
        results.by_difficulty[diff]["task_completion"] += cr.task_completion

        if verbose:
            print(f"  tool_sel={cr.tool_selection:.2f} task_comp={cr.task_completion:.2f} "
                  f"halluc={cr.no_hallucination:.2f} err={cr.error_handling_score:.2f}")

    # Compute aggregate scores
    n = len(results.cases)
    if n > 0:
        results.tool_selection_accuracy = sum(c.tool_selection for c in results.cases) / n
        results.task_completion_rate = sum(c.task_completion for c in results.cases) / n
        results.tool_validity_rate = sum(c.tool_validity for c in results.cases) / n
        results.no_hallucination_rate = sum(c.no_hallucination for c in results.cases) / n
        results.error_handling_rate = sum(c.error_handling_score for c in results.cases) / n
        results.trajectory_quality_avg = sum(c.trajectory_quality_score for c in results.cases) / n
        results.cases_passed = sum(1 for c in results.cases if c.task_completion >= 0.75)

    return results


def save_results(results: EvalResults, path: str | Path) -> None:
    """Save evaluation results to a JSON file."""
    data = asdict(results)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def print_summary(results: EvalResults) -> None:
    """Print a human-readable summary of evaluation results."""
    print("\n" + "=" * 70)
    print("EVALUATION RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total cases:          {results.total_cases}")
    print(f"Cases passed:         {results.cases_passed} ({results.cases_passed/results.total_cases*100:.1f}%)")
    print()
    print("METRIC SCORES (0.0 - 1.0):")
    print(f"  Tool Selection:     {results.tool_selection_accuracy:.3f}")
    print(f"  Task Completion:    {results.task_completion_rate:.3f}")
    print(f"  Tool Validity:      {results.tool_validity_rate:.3f}")
    print(f"  No Hallucination:   {results.no_hallucination_rate:.3f}")
    print(f"  Error Handling:     {results.error_handling_rate:.3f}")
    print(f"  Trajectory Quality: {results.trajectory_quality_avg:.3f}")
    print()
    print("COST & LATENCY:")
    print(f"  Total latency:      {results.total_latency_ms:.0f}ms")
    print(f"  Avg latency/case:   {results.total_latency_ms/max(results.total_cases,1):.0f}ms")
    print(f"  Total tokens:       {results.total_tokens}")
    print(f"  Total tool calls:   {results.total_tool_calls}")
    print()

    if results.by_category:
        print("BY CATEGORY:")
        for cat, data in sorted(results.by_category.items()):
            n = data["count"]
            ts = data["tool_selection"] / n
            tc = data["task_completion"] / n
            print(f"  {cat:25s}  n={n:3d}  tool_sel={ts:.2f}  task_comp={tc:.2f}")

    if results.by_difficulty:
        print("\nBY DIFFICULTY:")
        for diff, data in sorted(results.by_difficulty.items()):
            n = data["count"]
            ts = data["tool_selection"] / n
            tc = data["task_completion"] / n
            print(f"  {diff:10s}  n={n:3d}  tool_sel={ts:.2f}  task_comp={tc:.2f}")

    print("=" * 70)
