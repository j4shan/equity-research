"""Smoke tests for the rendering scripts against a generated fixture run."""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tests.fixtures.make_fixture_run import build  # noqa: E402


def _load(mod_name: str):
    path = REPO / "scripts" / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_render_pipeline(tmp_path: Path):
    run = tmp_path / "NVDA_2026-06-08"
    build(run)
    assert (run / "knowledge_graph.json").exists()

    viz = _load("visualize_graph")
    out = viz.render(run / "knowledge_graph.json", run / "graph.html")
    html = out.read_text()
    assert out.exists() and len(html) > 10_000
    assert "Sector Knowledge Graph" in html  # legend injected
    assert "NVDA" in html

    charts = _load("plot_charts")
    charts.PLOTLYJS = "cdn"
    charts.price_technical_chart(
        __import__("json").loads((run / "data" / "technical_series.json").read_text()),
        run / "charts" / "price_technical.html")
    charts.sentiment_chart(
        __import__("json").loads((run / "data" / "sentiment.json").read_text()),
        run / "charts" / "sentiment.html")
    assert (run / "charts" / "price_technical.html").exists()
    assert (run / "charts" / "sentiment.html").exists()

    report = _load("assemble_report")
    rep = report.render(run)
    body = rep.read_text()
    assert rep.exists()
    assert body.count('iframe class="embed') >= 2   # graph + at least one chart
    assert "Not investment advice" in body
