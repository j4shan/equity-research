"""Tests for the non-directional lint gate and report rendering."""

import json
from pathlib import Path

import pytest

from risk_engine.engine import run_engine
from risk_engine.registry import load_registry
from risk_engine.report import (
    NonDirectionalError,
    build_dashboard,
    lint_non_directional,
    render_report,
)
from risk_engine.report.report import _band

FIXTURE = Path(__file__).parent / "fixtures" / "risk" / "golden_raw.json"


def test_lint_flags_directive_language():
    bad = "Our model says BUY SPX now and set a price target of 6000."
    v = lint_non_directional(bad)
    labels = {x["label"] for x in v}
    assert "buy directive" in labels
    assert "price target" in labels


def test_lint_ignores_substrings_inside_words():
    # "buyer", "sellside", "shorten" must not trip word-boundary patterns
    ok = "Buyer-side breadth and sellside notes suggest we should shorten the window."
    assert lint_non_directional(ok) == []


def test_rendered_golden_report_is_clean_and_has_disclaimer():
    out = run_engine(json.loads(FIXTURE.read_text()), load_registry())
    md = render_report(out)
    assert lint_non_directional(md) == []
    assert "Not a trading recommendation" in md
    assert "Composite state" in md


def test_render_raises_on_injected_directive(monkeypatch):
    out = run_engine(json.loads(FIXTURE.read_text()), load_registry())
    # Force a directive into a rendered field by poisoning an id.
    out["indicators"][0]["id"] = "buy signal"
    with pytest.raises(NonDirectionalError):
        render_report(out)


def test_dashboard_shape():
    out = run_engine(json.loads(FIXTURE.read_text()), load_registry())
    dash = build_dashboard(out)
    assert set(dash) >= {"as_of", "overall", "band", "agreement_pct", "layers"}
    assert dash["weighting"] == "equal_weight_v1"


def test_band_labels():
    assert _band(10) == "calm / risk-on-leaning"
    assert _band(90) == "high stress / risk-off-leaning"
    assert _band(None) == "insufficient data"
