"""Label correction (drawdown) and recovery episodes from a price series.

A correction episode opens when price falls at least ``threshold`` from a running
peak; its trough is the minimum before price reclaims the prior peak; it is
"recovered" once price closes back at/above that peak. Episodes are the anchors
the calibration conditions forward returns on and the report cites as analogues.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..engine.calc import calc


@dataclass(frozen=True)
class Episode:
    peak_date: str
    peak: float
    trough_date: str
    trough: float
    depth_pct: float          # negative, e.g. -12.4
    recovered: bool
    recovery_date: str | None
    length_to_trough: int     # observations peak -> trough
    length_to_recovery: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def label_episodes(prices: list[dict[str, Any]],
                   threshold: float = 0.10) -> list[Episode]:
    """Label peak-to-trough drawdowns of at least ``threshold`` (e.g. 0.10 = 10%).

    ``prices`` is ``[{"date": "YYYY-MM-DD", "close": float}, ...]`` oldest..newest.
    Overlapping dips inside an unrecovered drawdown are treated as one episode
    (trough tracks the lowest point until the prior peak is reclaimed).
    """
    pts = [(p["date"], float(p["close"])) for p in prices if p.get("close") is not None]
    if len(pts) < 2:
        return []

    episodes: list[Episode] = []
    peak_date, peak = pts[0]
    peak_i = 0
    in_dd = False
    trough_date, trough, trough_i = peak_date, peak, 0

    for i, (d, c) in enumerate(pts):
        if c >= peak and not in_dd:
            peak_date, peak, peak_i = d, c, i
            continue
        drop = calc("(c - pk) / pk", {"c": c, "pk": peak})
        if not in_dd:
            if drop <= -abs(threshold):
                in_dd = True
                trough_date, trough, trough_i = d, c, i
        else:
            if c < trough:
                trough_date, trough, trough_i = d, c, i
            if c >= peak:  # reclaimed the prior peak -> episode closes, recovered
                episodes.append(_make(peak_date, peak, trough_date, trough,
                                      peak_i, trough_i, i, True, d))
                in_dd = False
                peak_date, peak, peak_i = d, c, i

    if in_dd:  # unrecovered drawdown still open at series end
        episodes.append(_make(peak_date, peak, trough_date, trough,
                              peak_i, trough_i, None, False, None))
    return episodes


def _make(peak_date, peak, trough_date, trough, peak_i, trough_i,
          rec_i, recovered, rec_date) -> Episode:
    depth = calc("100 * (tr - pk) / pk", {"tr": trough, "pk": peak})
    return Episode(
        peak_date=peak_date, peak=round(peak, 4),
        trough_date=trough_date, trough=round(trough, 4),
        depth_pct=round(depth, 2), recovered=recovered, recovery_date=rec_date,
        length_to_trough=trough_i - peak_i,
        length_to_recovery=(rec_i - peak_i) if rec_i is not None else None,
    )
