"""CLI entry point for the Store Analytics Agent."""

from __future__ import annotations

import sys
import io
from pathlib import Path

# Fix Windows console encoding for Unicode output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ensure the src directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from store_analytics.agent import run_agent
from store_analytics.config import DATABASE_PATH
from store_analytics.db.seed import seed_database


def main() -> None:
    # Ensure database exists
    if not DATABASE_PATH.exists():
        print("Seeding database...")
        seed_database(DATABASE_PATH)

    # Demo queries
    demo_queries = [
        "What is the total revenue from completed orders?",
        "Which product category has the highest average margin?",
        "How many customers signed up in 2025?",
        "What is 15% tip on $87.50?",
    ]

    if len(sys.argv) > 1:
        # Run specific query from command line
        query = " ".join(sys.argv[1:])
        print(f"\n--- Query: {query} ---\n")
        result = run_agent(query, verbose=True)
        print(f"\nAnswer: {result.final_answer}")
        print(f"Tool calls: {result.metadata.num_tool_calls}")
        print(f"Latency: {result.metadata.latency_ms:.0f}ms")
    else:
        # Run demo queries
        print("Running demo queries...\n")
        for query in demo_queries:
            print(f"--- Query: {query} ---")
            result = run_agent(query, verbose=True)
            print(f"Answer: {result.final_answer}")
            print(f"Tools used: {result.metadata.num_tool_calls}, Latency: {result.metadata.latency_ms:.0f}ms\n")


if __name__ == "__main__":
    main()
