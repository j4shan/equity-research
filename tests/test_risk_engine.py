"""Golden-fixture + reproducibility tests for the full engine.

Committed ``golden_raw.json`` -> asserted indicator values. Hand-computed so a
regression in normalize/crosscheck/formula-reduction is caught at exact numbers.
"""

import json
from pathlib import Path

import pytest

from risk_engine.engine import run_engine
from risk_engine.registry import load_registry

FIXTURE = Path(__file__).parent / "fixtures" / "risk" / "golden_raw.json"


@pytest.fixture(scope="module")
def engine_out():
    raw = json.loads(FIXTURE.read_text())
    return run_engine(raw, load_registry())


def _by_id(out, ind_id):
    return next(r for r in out["indicators"] if r["id"] == ind_id)


def test_vix_agrees_and_ranks(engine_out):
    vix = _by_id(engine_out, "vix_level")
    assert vix["consensus"] == 15.1          # median(15.0, 15.2, 15.1)
    assert vix["value_pct"] == 60.0          # rank of 15.1 in [10,12,14,16,18]
    assert vix["cross_check"] == "agree"
    assert vix["confidence"] == 0.72         # 0.90 * 0.8 (short history)
    assert vix["provisional"] is False
    assert vix["n_channels"] == 3


def test_yield_curve_formula_and_divergence(engine_out):
    yc = _by_id(engine_out, "yield_curve_2s10s")
    # fmp channel reduces via "y10 - y2" = 0.5; fred channel = 0.9 -> diverge
    assert yc["consensus"] == 0.7
    assert yc["cross_check"] == "divergence"
    assert yc["value_pct"] == 80.0
    assert yc["divergence"]["rel_spread"] > 0.15


def test_single_channel_is_provisional(engine_out):
    hy = _by_id(engine_out, "hy_credit_spread")
    assert hy["cross_check"] == "provisional"
    assert hy["provisional"] is True
    assert hy["value_pct"] == 50.0           # rank of 3.0 in [2,2.5,3.5,4]
    assert hy["confidence"] == 0.4           # 0.50 * 0.8


def test_unfetched_indicators_are_missing(engine_out):
    # registry has ~19 indicators; the fixture only supplies 6
    nfci = _by_id(engine_out, "nfci")
    assert nfci["cross_check"] == "missing"
    assert nfci["value_pct"] is None


def test_composite_present_and_oriented(engine_out):
    comp = engine_out["composite"]
    assert comp["weighting"] == "equal_weight_v1"
    assert comp["agreement_pct"] == 66.7     # 4 agree of 6 scored
    assert comp["layers"]["fear"]["score"] == 55.0   # (60 + 50)/2, equal conf


def test_engine_is_reproducible():
    raw = json.loads(FIXTURE.read_text())
    reg = load_registry()
    a = json.dumps(run_engine(raw, reg), sort_keys=True)
    b = json.dumps(run_engine(json.loads(FIXTURE.read_text()), reg), sort_keys=True)
    assert a == b
