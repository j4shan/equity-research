"""Non-directional lint — the contract that keeps this an *indicator* product.

The agent advises trading of SPX/NDX/SMH by presenting cross-verified state; it
must never issue a trade instruction, timing call, or price target. This scanner
is the enforceable form of that promise: the build/test fails if a rendered report
contains directive language. Kept as word-boundary regexes so substrings inside
legitimate words (e.g. "shorten", "buyer-side data quality") don't false-positive.
"""

from __future__ import annotations

import re

# (pattern, human label). Matched case-insensitively on word boundaries.
BANNED_PATTERNS: list[tuple[str, str]] = [
    (r"\bbuy\b", "buy directive"),
    (r"\bsell\b", "sell directive"),
    (r"\bgo long\b", "long directive"),
    (r"\bgo short\b", "short directive"),
    (r"\bshort the\b", "short directive"),
    (r"\bhedge now\b", "timing directive"),
    (r"\btake profits?\b", "trade directive"),
    (r"\bprice target\b", "price target"),
    (r"\bwe recommend\b", "recommendation"),
    (r"\brecommend (buying|selling|shorting|hedging)\b", "recommendation"),
    (r"\benter (a )?(long|short) position\b", "position directive"),
    (r"\bstrong (buy|sell)\b", "rating directive"),
    (r"\bovervalued\b", "valuation verdict"),   # prefer "rich vs history"
    (r"\bundervalued\b", "valuation verdict"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in BANNED_PATTERNS]


class NonDirectionalError(AssertionError):
    """Raised when report text contains directive/recommendation language."""


def lint_non_directional(text: str) -> list[dict[str, str]]:
    """Return a list of violations ``[{"match", "label"}]`` (empty = clean)."""
    violations = []
    for rx, label in _COMPILED:
        for m in rx.finditer(text or ""):
            violations.append({"match": m.group(0), "label": label})
    return violations


def assert_non_directional(text: str) -> None:
    """Raise ``NonDirectionalError`` if ``text`` violates the contract."""
    v = lint_non_directional(text)
    if v:
        joined = ", ".join(f"{x['match']!r} ({x['label']})" for x in v)
        raise NonDirectionalError(f"directional language in report: {joined}")
