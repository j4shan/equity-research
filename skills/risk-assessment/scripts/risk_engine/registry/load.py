"""Load and validate ``indicators.yaml`` into typed ``Indicator`` records.

The registry is the contract between the fetch layer, the engine, and the report.
Validation here fails loudly at load time so a malformed record can never silently
produce a wrong number downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from risk_engine import LAYERS

VALID_DIRECTIONS = ("risk_off_when_high", "risk_off_when_low")
VALID_REFRESH = ("daily", "weekly", "monthly")
VALID_SOURCES = ("fmp", "fred", "fgc", "av", "massive", "aaii")
VALID_METHODS = ("percentile", "zscore", "level")

_TRANSFORM_RE = re.compile(r"^(percentile|zscore|level)_(\d+)([dwm])$")
_WINDOW_DAYS = {"d": 1, "w": 5, "m": 21}  # trading-day multipliers for a window


class RegistryError(ValueError):
    """Raised when the indicator registry is malformed."""


@dataclass(frozen=True)
class Channel:
    source: str
    call: str
    key: str | None = None


@dataclass(frozen=True)
class Indicator:
    id: str
    layer: str
    refresh_class: str
    direction: str
    transform: str
    channels: tuple[Channel, ...]
    formula: str | None = None
    contrarian: bool = False
    tolerance: float = 0.05
    thresholds: dict[str, Any] = field(default_factory=dict)
    note: str | None = None

    @property
    def method(self) -> str:
        return parse_transform(self.transform)[0]

    @property
    def window(self) -> int:
        """Window length in observations (trading days)."""
        return parse_transform(self.transform)[1]

    @property
    def single_channel(self) -> bool:
        return len(self.channels) < 2


def parse_transform(transform: str) -> tuple[str, int]:
    """``"percentile_252d"`` -> ``("percentile", 252)``.

    Weekly/monthly units are converted to an approximate trading-day count so a
    single trailing series can serve any refresh class.
    """
    m = _TRANSFORM_RE.match(transform or "")
    if not m:
        raise RegistryError(
            f"bad transform {transform!r}; expected <method>_<N><d|w|m>"
        )
    method, n, unit = m.group(1), int(m.group(2)), m.group(3)
    return method, n * _WINDOW_DAYS[unit]


def default_registry_path() -> Path:
    return Path(__file__).with_name("indicators.yaml")


def load_registry(path: str | Path | None = None) -> list[Indicator]:
    """Parse + validate the registry. Raises ``RegistryError`` on any problem."""
    p = Path(path) if path else default_registry_path()
    if not p.exists():
        raise RegistryError(f"registry not found: {p}")
    raw = yaml.safe_load(p.read_text())
    if not isinstance(raw, list) or not raw:
        raise RegistryError("registry must be a non-empty list of indicators")

    indicators: list[Indicator] = []
    seen: set[str] = set()
    for i, rec in enumerate(raw):
        ind = _build(rec, i)
        if ind.id in seen:
            raise RegistryError(f"duplicate indicator id {ind.id!r}")
        seen.add(ind.id)
        indicators.append(ind)
    return indicators


def _build(rec: Any, i: int) -> Indicator:
    if not isinstance(rec, dict):
        raise RegistryError(f"indicator #{i} is not a mapping")
    ind_id = rec.get("id")
    if not ind_id or not isinstance(ind_id, str):
        raise RegistryError(f"indicator #{i} missing string id")

    def bad(msg: str) -> RegistryError:
        return RegistryError(f"indicator {ind_id!r}: {msg}")

    if rec.get("layer") not in LAYERS:
        raise bad(f"layer must be one of {LAYERS}, got {rec.get('layer')!r}")
    if rec.get("refresh_class") not in VALID_REFRESH:
        raise bad(f"refresh_class must be one of {VALID_REFRESH}")
    if rec.get("direction") not in VALID_DIRECTIONS:
        raise bad(f"direction must be one of {VALID_DIRECTIONS}")

    transform = rec.get("transform")
    parse_transform(transform)  # validates or raises

    raw_channels = rec.get("channels")
    if not isinstance(raw_channels, list) or not raw_channels:
        raise bad("channels must be a non-empty list")
    channels: list[Channel] = []
    for ch in raw_channels:
        if not isinstance(ch, dict) or "source" not in ch or "call" not in ch:
            raise bad(f"malformed channel {ch!r}")
        if ch["source"] not in VALID_SOURCES:
            raise bad(f"channel source must be one of {VALID_SOURCES}, got {ch['source']!r}")
        channels.append(Channel(source=ch["source"], call=ch["call"], key=ch.get("key")))

    tolerance = rec.get("tolerance", 0.05)
    if not isinstance(tolerance, (int, float)) or tolerance <= 0:
        raise bad("tolerance must be a positive number")

    return Indicator(
        id=ind_id,
        layer=rec["layer"],
        refresh_class=rec["refresh_class"],
        direction=rec["direction"],
        transform=transform,
        channels=tuple(channels),
        formula=rec.get("formula"),
        contrarian=bool(rec.get("contrarian", False)),
        tolerance=float(tolerance),
        thresholds=rec.get("thresholds", {}) or {},
        note=rec.get("note"),
    )
