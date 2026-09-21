"""Smoke tests for tools (no API keys needed)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from store_analytics.db.seed import seed_database
from store_analytics.config import DATABASE_PATH


def test_calculator():
    from store_analytics.tools.calculator import calculator_tool

    # Basic arithmetic
    r = json.loads(calculator_tool("2 + 3"))
    assert r["result"] == 5.0, f"Expected 5.0, got {r}"

    r = json.loads(calculator_tool("100 * 0.21"))
    assert r["result"] == 21.0, f"Expected 21.0, got {r}"

    r = json.loads(calculator_tool("(5000 - 1200) * 0.85"))
    assert r["result"] == 3230.0, f"Expected 3230.0, got {r}"

    # Division
    r = json.loads(calculator_tool("10 / 3"))
    assert abs(r["result"] - 3.333) < 0.01, f"Expected ~3.333, got {r}"

    # Error case
    r = json.loads(calculator_tool("import os"))
    assert "error" in r, f"Expected error for invalid expression, got {r}"

    print("  calculator: ALL PASSED")


def test_query_db():
    from store_analytics.tools.query_db import query_db_tool

    # Ensure DB exists
    if not DATABASE_PATH.exists():
        seed_database(DATABASE_PATH)

    # Basic query
    r = json.loads(query_db_tool("SELECT COUNT(*) as cnt FROM customers"))
    assert r["rows"][0]["cnt"] == 30, f"Expected 30 customers, got {r}"

    # Revenue query
    r = json.loads(query_db_tool("""
        SELECT SUM(oi.quantity * oi.unit_price) as total_revenue
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status = 'completed'
    """))
    assert r["rows"][0]["total_revenue"] > 0, f"Expected positive revenue, got {r}"

    # Write operation blocked
    r = json.loads(query_db_tool("DROP TABLE customers"))
    assert "error" in r, f"Expected error for write op, got {r}"

    # Non-SELECT blocked
    r = json.loads(query_db_tool("INSERT INTO customers VALUES (1, 'test', 'US', '2026-01-01')"))
    assert "error" in r, f"Expected error for non-SELECT, got {r}"

    print("  query_db: ALL PASSED")


def test_web_search():
    from store_analytics.tools.web_search import web_search_tool

    # Should return cached data for EUR/USD
    r = json.loads(web_search_tool("What is the EUR to USD exchange rate?"))
    assert len(r["results"]) > 0, f"Expected results for EUR/USD, got {r}"

    print("  web_search: ALL PASSED")


if __name__ == "__main__":
    print("Running tool smoke tests...\n")
    test_calculator()
    test_query_db()
    test_web_search()
    print("\nAll tool tests passed!")
