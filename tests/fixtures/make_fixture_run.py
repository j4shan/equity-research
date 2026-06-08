"""Build a self-contained fixture research run so the viz/report scripts can be
exercised without any live MCP calls. Writes into a target run dir.

Usage: python tests/fixtures/make_fixture_run.py <run_dir>
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root for imports

from research_hub.graph_store import GraphStore  # noqa: E402
from research_hub.schemas import Edge, Node  # noqa: E402


def build(run_dir: Path) -> None:
    (run_dir / "data").mkdir(parents=True, exist_ok=True)
    (run_dir / "charts").mkdir(parents=True, exist_ok=True)

    # --- knowledge graph ---
    g = GraphStore()
    g.upsert_node(Node("NVDA", name="NVIDIA", sector="Technology",
                       industry="Semiconductors", role="primary", market_cap=3.0e12))
    g.upsert_node(Node("AMD", name="Advanced Micro Devices", sector="Technology",
                       industry="Semiconductors", role="peer", market_cap=2.6e11))
    g.upsert_node(Node("TSM", name="TSMC", sector="Technology",
                       industry="Semiconductors", role="supplier", market_cap=8.0e11))
    g.upsert_node(Node("MSFT", name="Microsoft", sector="Technology",
                       industry="Software", role="customer", market_cap=3.1e12))
    g.upsert_node(Node("INTC", name="Intel", sector="Technology",
                       industry="Semiconductors", role="peer", market_cap=1.3e11))
    g.add_edge(Edge("NVDA", "AMD", "competition", 0.9, 0.85, "Both lead discrete GPUs / AI accelerators."))
    g.add_edge(Edge("NVDA", "INTC", "competition", 0.6, 0.7, "Compete in data-center accelerators."))
    g.add_edge(Edge("NVDA", "TSM", "dependency", 0.95, 0.9, "Outsources leading-edge fabrication to TSMC."))
    g.add_edge(Edge("AMD", "TSM", "dependency", 0.9, 0.85, "AMD also fabs at TSMC."))
    g.add_edge(Edge("NVDA", "MSFT", "symbiosis", 0.8, 0.75, "Azure scales on NVDA GPUs; co-evolving AI stack."))
    g.set_node_attrs("NVDA", "fundamentals", {"score": 0.62})
    g.set_node_attrs("NVDA", "technical", {"score": 0.40})
    g.set_node_attrs("NVDA", "sentiment", {"score": 0.55})
    g.snapshot(str(run_dir / "knowledge_graph.graphml"),
               str(run_dir / "knowledge_graph.json"))

    # --- analyst artifacts ---
    (run_dir / "data" / "fundamentals.json").write_text(json.dumps({
        "ticker": "NVDA", "score": 0.62,
        "valuation": {"pe": 60.1, "ps": 28.0, "ev_ebitda": 45.0, "peg": 1.1, "vs_peers": "premium"},
        "growth": {"revenue_yoy": 1.22, "eps_yoy": 1.68},
        "profitability": {"gross_margin": 0.75, "op_margin": 0.62, "roe": 0.91},
        "peer_comparison": [
            {"ticker": "NVDA", "pe": 60.1}, {"ticker": "AMD", "pe": 45.0},
            {"ticker": "INTC", "pe": 22.0}, {"ticker": "TSM", "pe": 24.0},
        ],
        "highlights": ["Margins expanding", "Data-center revenue surging"],
        "risks": ["Valuation premium", "Customer concentration"],
    }, indent=2))

    (run_dir / "data" / "sentiment.json").write_text(json.dumps({
        "ticker": "NVDA", "score": 0.55,
        "news": {"avg_sentiment": 0.28, "trend": "rising", "n_articles": 120},
        "narrative": {"top_keywords": ["AI", "data-center", "record revenue"]},
        "insider": {"net_buys": 2, "net_sells": 5, "net_value_usd": -1.2e7},
        "co_mentions": ["AMD", "TSM", "MSFT"],
    }, indent=2))

    # synthetic price series with SMAs and RSI
    n = 180
    dates = [f"2026-{1 + (i // 30) % 12:02d}-{1 + i % 28:02d}" for i in range(n)]
    close = [100 + 30 * math.sin(i / 18) + i * 0.25 for i in range(n)]

    def sma(vals, w):
        out = []
        for i in range(len(vals)):
            lo = max(0, i - w + 1)
            out.append(round(sum(vals[lo:i + 1]) / (i - lo + 1), 2))
        return out

    (run_dir / "data" / "technical_series.json").write_text(json.dumps({
        "title": "NVDA — Price & Technicals",
        "dates": dates,
        "close": [round(c, 2) for c in close],
        "sma50": sma(close, 50),
        "sma200": sma(close, 200),
        "rsi": [round(50 + 25 * math.sin(i / 9), 1) for i in range(n)],
        "volume": [int(2e7 + 5e6 * abs(math.sin(i / 7))) for i in range(n)],
    }, indent=2))

    # --- report.md ---
    (run_dir / "report.md").write_text(
        "# NVIDIA (NVDA) — Equity Research\n\n"
        "**Date:** 2026-06-08 · **Sector:** Technology · **Rating:** Buy · **Composite score:** +0.54\n\n"
        "> Thesis: AI compute leadership and margin expansion outweigh a premium valuation.\n\n"
        "## 2. Fundamentals — score +0.62\nStrong growth and margins; valuation is rich vs peers.\n\n"
        "Embed: charts/peer_valuation.html\n\n"
        "## 3. Technical — score +0.40\nUptrend intact above rising MAs.\n\n"
        "Embed: charts/price_technical.html\n\n"
        "## 4. Sentiment — score +0.55\nUpbeat news and bullish options, but net insider selling.\n\n"
        "Embed: charts/sentiment.html\n\n"
        "## 5. Sector Knowledge Graph\nNVDA as an organism in the semiconductor ecosystem.\n\n"
        "Embed: graph.html\n\n"
        "## 6. Synthesis & Rating\nBuy. Key dependency on TSMC; symbiosis with hyperscalers.\n"
    )
    print(f"fixture run written to {run_dir}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/sample_run")
    build(target)
