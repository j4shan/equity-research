"""Tests for HTTP adapters (fixture-injected, no network) and the MCP fetch spec."""

import json

from risk_engine.adapters import (
    MCP_SOURCES,
    build_fetch_spec,
)
from risk_engine.adapters.http_sources import (
    fred_series,
    history_values,
    latest,
)
from risk_engine.adapters.mcp_fetch_spec import HTTP_SOURCES
from risk_engine.registry import load_registry

_FRED_FIXTURE = json.dumps({"observations": [
    {"date": "2026-07-11", "value": "3.10"},
    {"date": "2026-07-10", "value": "3.05"},
    {"date": "2026-07-09", "value": "."},      # missing -> skipped
    {"date": "2026-07-08", "value": "3.00"},
]})


def test_fred_series_parses_and_orders_oldest_to_newest():
    res = fred_series("BAMLH0A0HYM2", api_key="k", http_get=lambda url: _FRED_FIXTURE)
    assert res["value"] == 3.10                      # latest
    assert [p["value"] for p in res["series"]] == [3.00, 3.05, 3.10]
    assert latest(res) == 3.10
    assert history_values(res) == [3.00, 3.05]       # current excluded


def test_fred_missing_key_degrades():
    res = fred_series("X", api_key=None, http_get=lambda url: _FRED_FIXTURE)
    assert "error" in res and latest(res) is None


def test_fred_network_failure_degrades():
    def boom(url):
        raise OSError("connection reset")
    res = fred_series("X", api_key="k", http_get=boom)
    assert "error" in res
    assert res["provenance"]["source"] == "fred"


def test_fred_key_not_leaked_in_provenance():
    res = fred_series("X", api_key="SECRET", http_get=lambda url: _FRED_FIXTURE)
    assert "SECRET" not in json.dumps(res["provenance"])


def test_fetch_spec_splits_mcp_and_http_and_covers_registry():
    reg = load_registry()
    spec = build_fetch_spec(reg)
    for call in spec["mcp_calls"]:
        assert call["source"] in MCP_SOURCES
        assert "tool_hint" in call
        assert call["dest"].startswith("indicators.")
    for call in spec["http_calls"]:
        assert call["source"] in HTTP_SOURCES

    # every registry channel appears exactly once across the two lists
    total_channels = sum(len(i.channels) for i in reg)
    assert len(spec["mcp_calls"]) + len(spec["http_calls"]) == total_channels
    assert "av" in spec["budget_notes"]              # 25/day guard documented
