"""Report layer: render engine artifacts into a non-directional Markdown brief
plus a compact ``dashboard.json``, and enforce the non-directional lint gate.
"""

from __future__ import annotations

from .lint import BANNED_PATTERNS, NonDirectionalError, lint_non_directional
from .report import build_dashboard, render_report

__all__ = [
    "BANNED_PATTERNS",
    "NonDirectionalError",
    "lint_non_directional",
    "build_dashboard",
    "render_report",
]
