"""Tool: query_db — read-only SQL queries on the store database."""

from __future__ import annotations

import json
import re
import sqlite3

from ..config import DATABASE_PATH

# Dangerous keywords that indicate write operations
_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|ATTACH|DETACH)\b",
    re.IGNORECASE,
)

query_db_schema = {
    "type": "function",
    "function": {
        "name": "query_db",
        "description": (
            "Execute a read-only SQL query on the store database. "
            "Tables: customers(id, name, country, signup_date), "
            "products(id, name, category, price, cost), "
            "orders(id, customer_id, order_date, status), "
            "order_items(id, order_id, product_id, quantity, unit_price). "
            "Use this for any question about sales, revenue, customers, products, or order data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A valid SQLite SELECT query. Only SELECT statements are allowed.",
                }
            },
            "required": ["sql"],
        },
    },
}


def query_db_tool(sql: str) -> str:
    """Execute a read-only SQL query and return JSON results."""
    # Security: block write operations
    if _WRITE_KEYWORDS.search(sql):
        return json.dumps({"error": "Write operations are not allowed. Only SELECT queries are permitted."})

    # Security: enforce SELECT prefix
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are allowed."})

    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = cursor.fetchall()
        conn.close()

        # Convert to list of dicts
        result = [dict(row) for row in rows]
        return json.dumps({"rows": result, "count": len(result)}, default=str)
    except Exception as e:
        return json.dumps({"error": f"SQL error: {e}"})
