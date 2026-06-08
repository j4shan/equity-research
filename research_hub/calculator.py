"""Safe arithmetic evaluator for the Research Hub calculator tool.

All agents in the workflow must delegate numerical calculation here rather than
doing arithmetic "in their head" — LLM mental math is a known error source, and
routing every derived figure through one deterministic evaluator makes numbers
reproducible and reviewable.

Supports: + - * / // % **, parentheses, unary +/-, numeric literals, named
variables, list literals, and a whitelist of math/statistics functions. The
evaluator walks the AST with a strict node whitelist — no attribute access, no
subscripts, no comprehensions, no calls to anything outside the function table —
so arbitrary code cannot execute.
"""

from __future__ import annotations

import ast
import math
import statistics
from typing import Any, Optional

_FUNCS: dict[str, Any] = {
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum, "len": len,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10, "exp": math.exp,
    "floor": math.floor, "ceil": math.ceil,
    "mean": statistics.fmean, "median": statistics.median,
    "std": statistics.pstdev,  # population std dev
}

_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}

_UNARYOPS = {ast.UAdd: lambda a: +a, ast.USub: lambda a: -a}

_MAX_EXPR_LEN = 2000


def evaluate(
    expression: str, variables: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Evaluate an arithmetic expression; returns {"result": ...} or {"error": ...}."""
    variables = variables or {}
    if not isinstance(expression, str) or not expression.strip():
        return {"error": "expression must be a non-empty string"}
    if len(expression) > _MAX_EXPR_LEN:
        return {"error": f"expression exceeds {_MAX_EXPR_LEN} chars"}

    bad = [k for k, v in variables.items() if not _is_number_or_list(v)]
    if bad:
        return {"error": f"variables must be numbers or lists of numbers: {bad}"}

    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval(tree.body, variables)
    except _Unsafe as exc:
        return {"error": f"disallowed construct: {exc}"}
    except ZeroDivisionError:
        return {"error": "division by zero"}
    except (ValueError, TypeError, KeyError, OverflowError, SyntaxError,
            statistics.StatisticsError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

    if isinstance(result, float):
        # Guard against inf/nan leaking into reports.
        if math.isnan(result) or math.isinf(result):
            return {"error": f"non-finite result: {result}"}
        result = round(result, 10)
    return {"expression": expression, "variables": variables, "result": result}


class _Unsafe(Exception):
    pass


def _is_number_or_list(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    return isinstance(v, list) and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) for x in v
    )


def _eval(node: ast.AST, variables: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise _Unsafe(f"literal {node.value!r}")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](
            _eval(node.left, variables), _eval(node.right, variables))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval(node.operand, variables))
    if isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        raise _Unsafe(f"unknown variable {node.id!r}")
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e, variables) for e in node.elts]
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise _Unsafe("only whitelisted functions may be called")
        if node.keywords:
            raise _Unsafe("keyword arguments")
        return _FUNCS[node.func.id](*[_eval(a, variables) for a in node.args])
    raise _Unsafe(type(node).__name__)
