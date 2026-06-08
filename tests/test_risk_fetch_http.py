"""Test the FRED HTTP merge into the raw contract (fixture-injected, no network)."""

import json

from risk_engine.fetch_http import merge_fred_channels
from risk_engine.run_risk import bootstrap


def _fred_payload(*values):
    obs = [{"date": f"2026-07-{11 - i:02d}", "value": str(v)}
           for i, v in enumerate(values)]
    return json.dumps({"observations": obs})


def test_merge_fills_fred_channels(tmp_path):
    bootstrap(tmp_path, "2026-07-12")

    def fake_get(url):
        # every FRED series gets the same little history for the test
        return _fred_payload(3.1, 3.0, 2.9)

    status = merge_fred_channels(tmp_path, http_get=fake_get, api_key="k")

    # hy_credit_spread is FRED-only -> its channel value is now populated
    assert status["hy_credit_spread"]["value"] == 3.1
    raw = json.loads((tmp_path / "raw" / "raw.json").read_text())
    hy = raw["indicators"]["hy_credit_spread"]
    fred_ch = [c for c in hy["channels"] if c["source"] == "fred"][0]
    assert fred_ch["value"] == 3.1
    assert hy["history"] == [2.9, 3.0]      # oldest..newest, current excluded


def test_merge_degrades_without_key(tmp_path):
    bootstrap(tmp_path, "2026-07-12")
    status = merge_fred_channels(tmp_path, http_get=lambda u: _fred_payload(1),
                                 api_key=None)
    assert all(s["error"] for s in status.values())      # no key -> all error
    raw = json.loads((tmp_path / "raw" / "raw.json").read_text())
    # channel exists but value is null -> engine will treat as missing/provisional
    hy = raw["indicators"]["hy_credit_spread"]
    assert [c for c in hy["channels"] if c["source"] == "fred"][0]["value"] is None
