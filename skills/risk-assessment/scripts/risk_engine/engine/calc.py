"""Thin wrapper around ``research_hub.calculator`` for the engine.

The equity_research repo mandates that every derived figure flow through the one
deterministic evaluator rather than ad-hoc Python arithmetic. ``calc`` raises on
error (the engine wants a hard failure, not a silent bad number); ranking/counting
that isn't an arithmetic expression is done in plain Python but its reductions
(means, ratios, divisions) still go through the evaluator.
"""

from __future__ import annotations

from typing import Any

from research_hub.calculator import evaluate


class CalcError(RuntimeError):
    """Raised when a mandated calculation fails."""


def calc(expression: str, variables: dict[str, Any] | None = None) -> float:
    """Evaluate ``expression`` and return the numeric result, or raise."""
    out = evaluate(expression, variables or {})
    if "error" in out:
        raise CalcError(f"{expression!r} {variables or {}}: {out['error']}")
    return out["result"]
