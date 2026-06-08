"""Data adapters.

Two callability worlds, per the architecture constraint:
  * ``mcp_fetch_spec`` — MCP tools (FMP, Alpha Vantage, Massive) are callable
    only by the Claude agent; this module tells the agent exactly what to call.
  * ``http_sources`` — FRED, FearGreedChart, AAII are plain HTTP and callable by
    Python directly.
"""

from __future__ import annotations

from .mcp_fetch_spec import MCP_SOURCES, build_fetch_spec

__all__ = ["MCP_SOURCES", "build_fetch_spec"]
