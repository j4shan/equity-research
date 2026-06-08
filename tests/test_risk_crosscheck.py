"""Tests for cross-verification (agreement / divergence / provisional)."""

from risk_engine.engine.crosscheck import cross_check


def _ch(**kv):
    return [{"source": s, "value": v} for s, v in kv.items()]


def test_agreement_within_tolerance():
    r = cross_check(_ch(fmp=15.0, fred=15.2, fgc=15.1), tolerance=0.05)
    assert r["status"] == "agree"
    assert r["consensus"] == 15.1        # median
    assert r["confidence"] == 0.90
    assert r["n_channels"] == 3


def test_divergence_beyond_tolerance_flags():
    r = cross_check(_ch(fmp=0.5, fred=0.9), tolerance=0.15)
    assert r["status"] == "divergence"
    assert r["divergence"] is not None
    assert r["confidence"] == 0.45
    assert r["divergence"]["rel_spread"] > 0.15


def test_single_channel_is_provisional():
    r = cross_check(_ch(fred=3.0))
    assert r["status"] == "provisional"
    assert r["confidence"] == 0.50
    assert r["consensus"] == 3.0


def test_no_channels_is_missing():
    r = cross_check([{"source": "fmp", "value": None}])
    assert r["status"] == "missing"
    assert r["confidence"] == 0.0 and r["consensus"] is None


def test_short_history_penalty_applies():
    full = cross_check(_ch(a=15.0, b=15.1), history_sufficient=True)
    short = cross_check(_ch(a=15.0, b=15.1), history_sufficient=False)
    assert short["confidence"] < full["confidence"]
    assert short["confidence"] == round(0.90 * 0.8, 4)
