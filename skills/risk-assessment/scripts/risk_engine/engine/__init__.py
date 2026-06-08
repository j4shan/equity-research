"""Deterministic indicator engine: raw readings -> indicators.json -> composite.json.

Pure Python, unit-tested, reproducible: the same raw input always yields a
byte-identical result. Every arithmetic step routes through
``research_hub.calculator`` so numbers are auditable, matching the repo's
numerical-discipline convention.
"""

from __future__ import annotations

from .engine import run_engine
from .normalize import normalize, percentile_rank
from .crosscheck import cross_check
from .composite import build_composite

__all__ = [
    "run_engine",
    "normalize",
    "percentile_rank",
    "cross_check",
    "build_composite",
]
