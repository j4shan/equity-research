"""Assemble a point-in-time panel for calibration.

Joins an indicator's historical ``value_pct`` series to a benchmark's forward
returns on matching dates. The heavy lifting — pulling multi-year vintages from
FMP/FRED/Massive — is done by the agent/operator (MCP calls) and handed here as
plain date/value series, so this stays pure and testable and free of look-ahead
(only dates present in BOTH series survive the join).
"""

from __future__ import annotations

from typing import Any

from .calibrate import forward_returns


def build_panel(indicator_series: list[dict[str, Any]],
                prices: list[dict[str, Any]],
                horizon: int = 21) -> list[dict[str, Any]]:
    """Inner-join indicator value_pct history with forward benchmark returns.

    ``indicator_series`` = ``[{"date", "value_pct"}, ...]``.
    ``prices``           = ``[{"date", "close"}, ...]`` for the benchmark.
    Returns ``[{"date", "value_pct", "fwd_return"}]`` for dates present in both,
    ordered by date.
    """
    fwd = {r["date"]: r["fwd_return"] for r in forward_returns(prices, horizon)}
    joined = []
    for row in indicator_series:
        d = row.get("date")
        if d in fwd and row.get("value_pct") is not None:
            joined.append({"date": d, "value_pct": row["value_pct"],
                           "fwd_return": fwd[d]})
    joined.sort(key=lambda r: r["date"])
    return joined
