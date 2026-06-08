#!/usr/bin/env python3
"""Render interactive analytical charts (plotly) for a research run.

Inputs (all optional — charts are produced for whatever exists in <run-dir>/data):
  data/technical_series.json  -> price + indicators chart
  data/fundamentals.json      -> peer valuation/profitability bars (if peer data present)
  data/sentiment.json         -> sentiment posture gauge/bars

Outputs: <run-dir>/charts/*.html

Usage:
    python scripts/plot_charts.py --run-dir <RUN_DIR>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# How to bundle plotly.js into each chart. "cdn" keeps files ~KB (good for the
# version-controlled assets repo) but needs network to render; "inline" is fully
# self-contained (~4.8MB/chart). Overridable via --plotlyjs.
PLOTLYJS = "cdn"


def _write(fig: go.Figure, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs=PLOTLYJS, full_html=True)
    return out


def _load(path: Path) -> Optional[Any]:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None
    return None


def price_technical_chart(series: dict, out: Path) -> Optional[Path]:
    """series = {"dates":[...], "close":[...], "sma50":[...], "sma200":[...],
                 "rsi":[...], "volume":[...]} (any subset)."""
    dates = series.get("dates")
    close = series.get("close")
    if not dates or not close:
        return None

    has_rsi = bool(series.get("rsi"))
    rows = 3 if has_rsi else 2
    specs = [[{}], [{}], [{}]][:rows]
    titles = ["Price & Moving Averages", "Volume"] + (["RSI (14)"] if has_rsi else [])
    fig = make_subplots(
        rows=rows, cols=1, shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2][:rows], vertical_spacing=0.04,
        subplot_titles=titles, specs=specs,
    )

    fig.add_trace(go.Scatter(x=dates, y=close, name="Close",
                             line=dict(color="#1d3557", width=2)), row=1, col=1)
    for key, color in (("sma50", "#e9a000"), ("sma200", "#e63946")):
        if series.get(key):
            fig.add_trace(go.Scatter(x=dates, y=series[key], name=key.upper(),
                                     line=dict(color=color, width=1.3)), row=1, col=1)
    if series.get("volume"):
        fig.add_trace(go.Bar(x=dates, y=series["volume"], name="Volume",
                             marker_color="#8d99ae"), row=2, col=1)
    if has_rsi:
        fig.add_trace(go.Scatter(x=dates, y=series["rsi"], name="RSI",
                                 line=dict(color="#2a9d8f", width=1.3)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#e63946", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#2a9d8f", row=3, col=1)

    fig.update_layout(template="plotly_white", height=720,
                      title=series.get("title", "Price & Technicals"),
                      legend=dict(orientation="h", y=1.02, x=0),
                      margin=dict(l=40, r=20, t=70, b=30))
    return _write(fig, out)


def sentiment_chart(sent: dict, out: Path) -> Optional[Path]:
    bars = []
    news = sent.get("news", {})
    if "avg_sentiment" in news:
        bars.append(("News sentiment", news["avg_sentiment"]))
    insider = sent.get("insider", {})
    if {"net_buys", "net_sells"} & set(insider):
        net = insider.get("net_buys", 0) - insider.get("net_sells", 0)
        # squash a small integer net into a -1..1 proxy
        bars.append(("Insider flow", round(max(-1, min(1, net / 5)), 2)))
    if "score" in sent:
        bars.append(("Composite", sent["score"]))
    if not bars:
        return None
    labels, vals = zip(*bars)
    colors = ["#2a9d8f" if v >= 0 else "#e63946" for v in vals]
    fig = go.Figure(go.Bar(x=list(vals), y=list(labels), orientation="h",
                           marker_color=colors,
                           text=[f"{v:+.2f}" for v in vals], textposition="outside"))
    fig.update_layout(template="plotly_white", height=360,
                      title=f"Sentiment posture — {sent.get('ticker','')}",
                      xaxis=dict(range=[-1.1, 1.1], title="bearish ← → bullish"),
                      margin=dict(l=120, r=30, t=60, b=40))
    return _write(fig, out)


def peer_valuation_chart(fund: dict, out: Path) -> Optional[Path]:
    peers = fund.get("peer_comparison")
    if not isinstance(peers, list) or not peers:
        return None
    tickers = [p.get("ticker", "?") for p in peers]
    pe = [p.get("pe") for p in peers]
    if not any(pe):
        return None
    fig = go.Figure(go.Bar(x=tickers, y=pe, marker_color="#457b9d",
                           text=[f"{v:.1f}" if v else "" for v in pe],
                           textposition="outside"))
    fig.update_layout(template="plotly_white", height=380,
                      title="P/E vs peers", margin=dict(l=40, r=20, t=60, b=40))
    return _write(fig, out)


def main() -> None:
    global PLOTLYJS
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--plotlyjs", choices=["cdn", "inline"], default=PLOTLYJS,
                    help="cdn = small files (needs network); inline = self-contained")
    args = ap.parse_args()
    PLOTLYJS = args.plotlyjs
    run = Path(args.run_dir)
    data = run / "data"
    charts = run / "charts"

    written = []
    series = _load(data / "technical_series.json")
    if series:
        p = price_technical_chart(series, charts / "price_technical.html")
        if p:
            written.append(p)
    sent = _load(data / "sentiment.json")
    if sent:
        p = sentiment_chart(sent, charts / "sentiment.html")
        if p:
            written.append(p)
    fund = _load(data / "fundamentals.json")
    if fund:
        p = peer_valuation_chart(fund, charts / "peer_valuation.html")
        if p:
            written.append(p)

    if written:
        for p in written:
            print(f"wrote {p}")
    else:
        print("no chartable data found in", data)


if __name__ == "__main__":
    main()
