"""Tool: calculator — safe arithmetic expression evaluator."""

from __future__ import annotations

import ast
import json
import operator

# Allowed operators for safe evaluation
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

calculator_schema = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": (
            "Evaluate a mathematical expression and return the numeric result. "
            "Supports: +, -, *, /, //, %, **, parentheses. "
            "Use this for any arithmetic calculation, percentage computations, or unit conversions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A mathematical expression to evaluate, e.g. '21 / 100 * 1240' or '(5000 - 1200) * 0.85'",
                }
            },
            "required": ["expression"],
        },
    },
}


def _safe_eval(node: ast.AST) -> float:
    """Recursively evaluate an AST node with only safe operators."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    elif isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return _SAFE_OPS[type(node.op)](left, right)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        operand = _safe_eval(node.operand)
        return _SAFE_OPS[type(node.op)](operand)
    else:
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def calculator_tool(expression: str) -> str:
    """Safely evaluate a math expression and return JSON result."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
        return json.dumps({"result": result, "expression": expression})
    except Exception as e:
        return json.dumps({"error": f"Could not evaluate expression: {e}", "expression": expression})
