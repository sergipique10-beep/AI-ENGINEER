"""Demo script — intentionally breaks the calculator tool to show CI catching the regression."""

import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from store_analytics.tools import calculator_tool, calculator_schema

# INTENTIONAL BUG: calculator now divides everything by 2
_original_calculator = calculator_tool

def broken_calculator(expression: str) -> str:
    """Broken calculator — always divides result by 2 (simulates a regression)."""
    import json
    result = _original_calculator(expression)
    data = json.loads(result)
    if "result" in data:
        data["result"] = data["result"] / 2
        data["note"] = "INTENTIONAL BUG: result divided by 2"
    return json.dumps(data)

# Monkey-patch the tool
import store_analytics.tools as tools_module
tools_module.ALL_TOOL_FUNCTIONS["calculator"] = broken_calculator

print("=" * 60)
print("DEMO: Intentional calculator regression")
print("=" * 60)
print()
print("Running evals with broken calculator...")
print("The gate SHOULD fail on task_completion and hallucination metrics.")
print()

from store_analytics.evals.harness import run_evals, save_results, print_summary

results = run_evals("data/golden.json", max_cases=20)
print_summary(results)
save_results(results, "data/eval_results_broken.json")

print()
print("Now running gate check...")
from store_analytics.config import DATABASE_PATH
from store_analytics.db.seed import seed_database
if not DATABASE_PATH.exists():
    seed_database(DATABASE_PATH)

import subprocess
result = subprocess.run(
    ["python", "scripts/gate.py", "--results", "data/eval_results_broken.json"],
    capture_output=False
)
print(f"Gate exit code: {result.returncode}")
if result.returncode != 0:
    print("CI WOULD BLOCK THE MERGE — regression detected!")
else:
    print("Gate passed (unexpected)")
