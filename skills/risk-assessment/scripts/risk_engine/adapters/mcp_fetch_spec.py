"""Turn the registry into an explicit fetch plan for the agent.

MCP tools can only be invoked by the Claude agent, not by this Python. So instead
of calling them, we EMIT the exact list of calls the agent must make and where to
drop each result. The agent reads this spec, runs the calls, and writes
``raw/raw.json`` in the engine's raw contract. HTTP sources are split out so the
Python fetch layer can pull them directly.
"""

from __future__ import annotations

from typing import Any

from ..registry import Indicator, load_registry

# Which sources are MCP (agent-only) vs HTTP (python-callable).
MCP_SOURCES = ("fmp", "av", "massive")
HTTP_SOURCES = ("fred", "fgc", "aaii")

# Source -> the MCP tool namespace the agent should reach for. The concrete tool
# within the namespace is chosen by the agent from the channel's `call` string.
_MCP_TOOL_HINT = {
    "fmp": "mcp__claude_ai_FMP__*  (quote | economics | marketPerformance | "
           "technicalIndicators | commitmentOfTraders | indexes)",
    "av": "mcp__claude_ai_Alpha_Vantage__*  (RSI | ATR | SMA | GLOBAL_QUOTE | "
          "CPI | HISTORICAL_PUT_CALL_RATIO) — MIND the 25 req/day free cap",
    "massive": "mcp__claude_ai_Massive__search_endpoints -> call_api "
               "(snapshots/indices/ETFs; query_data for breadth)",
}


def build_fetch_spec(registry: list[Indicator] | None = None) -> dict[str, Any]:
    """Produce the agent's fetch plan.

    Returns a dict with ``mcp_calls`` (the agent must execute), ``http_calls``
    (the python adapter executes), and a per-source budget note. Each call carries
    the ``indicator_id`` and ``dest`` (``indicators.<id>.channels[]``) so results
    can be routed into the raw contract deterministically.
    """
    registry = registry if registry is not None else load_registry()

    mcp_calls: list[dict[str, Any]] = []
    http_calls: list[dict[str, Any]] = []
    per_source: dict[str, int] = {}

    for ind in registry:
        for ch in ind.channels:
            per_source[ch.source] = per_source.get(ch.source, 0) + 1
            entry = {
                "indicator_id": ind.id,
                "layer": ind.layer,
                "source": ch.source,
                "call": ch.call,
                "key": ch.key,
                "refresh_class": ind.refresh_class,
                "dest": f"indicators.{ind.id}.channels[]",
                "expects": "components" if (ind.formula and ch.key
                                            and "components" in ch.key)
                           else "value",
            }
            if ch.source in MCP_SOURCES:
                entry["tool_hint"] = _MCP_TOOL_HINT[ch.source]
                mcp_calls.append(entry)
            else:
                http_calls.append(entry)

    return {
        "mcp_calls": mcp_calls,
        "http_calls": http_calls,
        "source_counts": per_source,
        "budget_notes": {
            "av": "Alpha Vantage free tier = 25 requests/day — batch and cache; "
                  "prefer FMP/FRED where a channel overlaps.",
        },
    }
