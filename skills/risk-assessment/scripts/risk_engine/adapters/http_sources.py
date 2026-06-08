"""Plain-HTTP data adapters: FRED, FearGreedChart, AAII.

These sources are callable by Python directly (unlike the MCP tools). Every
adapter:
  * takes an injectable ``http_get(url) -> str`` so tests run against recorded
    fixtures with no network (CI must never hit the wire),
  * degrades gracefully — a network/parse/key failure returns ``{"error": ...}``
    rather than raising, so one dead source can't sink the daily run,
  * returns a normalized ``{value, series, provenance}`` shape plus provenance.

FRED needs a free API key (env ``FRED_API_KEY``). FearGreedChart and AAII need no
key. Exact endpoint shapes are recorded in ``data-source-validation.md``.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

HttpGet = Callable[[str], str]

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
_TIMEOUT = 20


def _default_http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "risk-agent/0.1"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
        return resp.read().decode("utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _provenance(source: str, url: str, **extra: Any) -> dict[str, Any]:
    return {"source": source, "url": url, "fetched_at": _now(), **extra}


def fred_series(series_id: str, *, api_key: str | None = None,
                http_get: HttpGet | None = None,
                limit: int = 400) -> dict[str, Any]:
    """Fetch a FRED series' recent observations.

    Returns ``{value, date, series: [{date, value}], provenance}`` (newest last),
    or ``{error, provenance}``. ``value`` is the latest non-missing observation.
    """
    key = api_key or os.environ.get("FRED_API_KEY")
    get = http_get or _default_http_get
    url = (f"{FRED_BASE}?series_id={series_id}&api_key={key or 'MISSING'}"
           f"&file_type=json&sort_order=desc&limit={limit}")
    prov = _provenance("fred", url.replace(key or "MISSING", "***"),
                       series_id=series_id)
    if not key:
        return {"error": "FRED_API_KEY not set (register a free key)", "provenance": prov}
    try:
        payload = json.loads(get(url))
    except Exception as exc:  # noqa: BLE001 — degrade, don't raise
        return {"error": f"fetch/parse failed: {exc}", "provenance": prov}

    obs = payload.get("observations", [])
    series = []
    for o in reversed(obs):  # API returned desc; store oldest..newest
        v = o.get("value")
        if v in (None, ".", ""):
            continue
        try:
            series.append({"date": o.get("date"), "value": float(v)})
        except (TypeError, ValueError):
            continue
    if not series:
        return {"error": "no valid observations", "provenance": prov}
    latest = series[-1]
    return {"value": latest["value"], "date": latest["date"],
            "series": series, "provenance": prov}


def fear_greed_chart(path: str, *, http_get: HttpGet | None = None,
                     base: str = "https://www.feargreedchart.com") -> dict[str, Any]:
    """Fetch a FearGreedChart JSON endpoint (no key) and pass it through.

    ``path`` is the endpoint path (e.g. ``/api/fear-and-greed``). The exact schema
    varies by endpoint, so callers parse ``raw``; provenance is always attached.
    Tertiary/convenience source — never the sole channel for a headline signal.
    """
    get = http_get or _default_http_get
    url = f"{base}{path}"
    prov = _provenance("fgc", url)
    try:
        raw = json.loads(get(url))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"fetch/parse failed: {exc}", "provenance": prov}
    return {"raw": raw, "provenance": prov}


def aaii_sentiment(*, http_get: HttpGet | None = None,
                   url: str = "https://www.aaii.com/sentimentsurvey/sent_results") \
        -> dict[str, Any]:
    """Best-effort AAII bull/bear survey scrape.

    AAII has no official API; this is a best-effort read that degrades to an error
    (so it is never a hard dependency). Returned ``raw`` is the HTML for the caller
    to parse when the layout is known.
    """
    get = http_get or _default_http_get
    prov = _provenance("aaii", url)
    try:
        raw = get(url)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"fetch failed: {exc}", "provenance": prov}
    return {"raw": raw, "provenance": prov}


def latest(series_result: dict[str, Any]) -> float | None:
    """Extract the latest scalar from a ``fred_series``-shaped result, or None."""
    return series_result.get("value") if "error" not in series_result else None


def history_values(series_result: dict[str, Any]) -> list[float]:
    """Extract the oldest..newest value list (current excluded) for normalization."""
    if "error" in series_result:
        return []
    vals = [p["value"] for p in series_result.get("series", [])]
    return vals[:-1] if len(vals) > 1 else []
