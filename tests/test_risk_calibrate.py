"""Tests for episode labeling and forward-return calibration."""

from risk_engine.calibrate import (
    build_panel,
    calibrate_indicator,
    forward_returns,
    label_episodes,
)


def _prices(closes, start_day=1):
    return [{"date": f"2020-01-{start_day + i:02d}", "close": c}
            for i, c in enumerate(closes)]


def test_label_10pct_drawdown_and_recovery():
    # peak 110 -> trough 99 (-10%) -> recovers above 110
    eps = label_episodes(_prices([100, 105, 110, 104, 99, 103, 111]), threshold=0.10)
    assert len(eps) == 1
    e = eps[0]
    assert e.peak == 110.0 and e.trough == 99.0
    assert e.depth_pct == -10.0
    assert e.recovered is True
    assert e.length_to_trough == 2


def test_unrecovered_drawdown_left_open():
    eps = label_episodes(_prices([100, 90, 85]), threshold=0.05)
    assert len(eps) == 1 and eps[0].recovered is False
    assert eps[0].recovery_date is None


def test_shallow_dip_below_threshold_ignored():
    eps = label_episodes(_prices([100, 98, 100, 102]), threshold=0.10)
    assert eps == []


def test_forward_returns_alignment():
    fr = forward_returns(_prices([100, 110, 121]), horizon=1)
    assert fr[0]["fwd_return"] == 10.0
    assert fr[1]["fwd_return"] == 10.0
    assert len(fr) == 2  # last point has no forward window


def test_calibration_buckets_capture_edge():
    # higher indicator percentile -> more negative forward return
    obs = [{"date": f"d{i}", "value_pct": p, "fwd_return": -(p / 10.0)}
           for i, p in enumerate(range(0, 100, 5))]
    cal = calibrate_indicator(obs, n_buckets=5)
    scores = {b["bucket"]: b["mean_fwd_return"] for b in cal["buckets"]}
    assert scores[4] < scores[0]                    # top bucket more negative
    assert cal["buckets"][-1]["neg_hit_rate"] == 100.0


def test_build_panel_inner_join():
    prices = _prices([100, 101, 102, 103])
    ind_series = [{"date": p["date"], "value_pct": 50.0} for p in prices]
    panel = build_panel(ind_series, prices, horizon=1)
    # only dates with a forward window survive (last date dropped)
    assert len(panel) == 3
    assert all("fwd_return" in row for row in panel)
