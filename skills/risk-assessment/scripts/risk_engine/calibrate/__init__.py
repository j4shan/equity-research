"""Historical calibration: label drawdown/recovery episodes and measure whether an
indicator's state actually precedes adverse moves — a flat-JSON store, no graph.

Kept deliberately separate from the daily engine: calibration is periodic
(quarterly), reads a multi-year panel, and its output (per-indicator conditional
forward-return distributions + labeled episodes) is what lets the report cite
*historical analogues* instead of asserting a forecast.
"""

from __future__ import annotations

from .episodes import Episode, label_episodes
from .calibrate import calibrate_indicator, forward_returns
from .backfill import build_panel

__all__ = [
    "Episode",
    "label_episodes",
    "calibrate_indicator",
    "forward_returns",
    "build_panel",
]
