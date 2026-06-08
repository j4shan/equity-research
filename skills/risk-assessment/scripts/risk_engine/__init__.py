"""Market Risk Assessment Agent — deterministic compute core.

A daily, non-directional risk/sentiment assessment for SPX, NDX, and SMH. The
promise is *rigorous quantitative indicators cross-verified across independent
channels* — so every number is computed here, in tested Python (reusing
``research_hub.calculator``), never by the LLM. The Claude agent orchestrates
MCP data collection and writes narrative; this package normalizes, cross-checks,
composites, and reports.

Independent of the equity-research subagents/investment model; it only reuses
``research_hub`` primitives. See ``skills/risk-assessment/scripts/risk_engine/build-plan.md``.
"""

from __future__ import annotations

__version__ = "0.1.0"

LAYERS = ("macro", "sector", "market", "fear")
