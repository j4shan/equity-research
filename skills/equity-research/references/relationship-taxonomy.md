# Relationship Taxonomy — the Ecological Model

The relationship analyst treats a sector as an **ecosystem of organisms**. Every
company is a node; every relationship is a typed, directed, weighted, evidenced
edge. Four relation types, borrowed from ecology:

| Relation | Ecological analogue | Meaning in markets |
|---|---|---|
| **competition** | competitive exclusion | Firms contend for the same customers/market/inputs; one's gain tends to be the other's loss. |
| **collaboration** | mutualism (facultative) | Deliberate joint action — partnerships, JVs, co-development, standards alliances. |
| **dependency** | host–parasite / commensalism | One firm materially relies on another (supplier→customer, platform→app, fab→fabless). Directional. |
| **symbiosis** | obligate mutualism | Deep two-way interdependence where both materially benefit and co-evolve (ecosystem lock-in). |

## Edge data model (final)

**Node** = stock ticker. **Edge** = directed company relationship.
**Edge identity = the triple `(source, target, relation)`.**

```json
{
  "source": "NVDA",
  "target": "TSM",
  "relation": "dependency",
  "direction": "NVDA->TSM",
  "weight": 0.9,        // strength of the relationship, 0..1
  "confidence": 0.8,    // analyst certainty in the claim, 0..1
  "evidence": "NVDA outsources leading-edge fabrication to TSMC (10-K, news).",
  "summaries": [        // incremental agent output — one entry appended per run
    "2026-06: sole leading-edge foundry for Blackwell; no second source qualified."
  ]
}
```

- **Relations are NOT mutually exclusive.** The same pair can hold a
  `competition` edge and a `collaboration` edge simultaneously (rivalry in one
  business segment, joint standards work in another). Each relation is its own
  edge instance under the identity triple.
- **Merge-update pattern.** Asserting an edge whose identity already exists does
  not duplicate it: scalar attrs (`weight`, `confidence`, `evidence`) refresh to
  the latest values, and the run's finalized relationship `summary` is
  **appended** to `summaries` — the edge accumulates a dated narrative across runs.
- **Fixed universe.** Edges may only connect tickers already in the graph. An
  agent that encounters an out-of-universe company in its study does **not**
  research it or create a node — it records the mention in its artifact
  (`out_of_universe`) and moves on. `graph_add_edge` enforces this.
- **direction** always reads `source->target`. For `dependency`, source depends on
  target. For `competition`/`symbiosis` (symmetric), still pick a source but the
  meaning is mutual; you may add the reverse edge if asymmetry matters.
- **weight** = how strong/material. **confidence** = how sure you are.
- **evidence** = one sentence citing the data (which data tool — Alpha Vantage /
  Massive — / filing / news).

## Inference rules (from market data)

| Relation | How to infer |
|---|---|
| competition | Same sector+industry (`COMPANY_OVERVIEW`) **and** co-membership in the same index/ETF/screen (`ETF_PROFILE` / Massive peer screen); reinforced by overlapping product keywords in `NEWS_SENTIMENT`. |
| dependency | Supplier/customer language in `NEWS_SENTIMENT` co-mentions and filings; known supply-chain roles (e.g. foundry, key vendor). Direction = dependent → depended-upon. |
| collaboration | Announced partnerships, JVs, integrations, co-marketing in `NEWS_SENTIMENT`. |
| symbiosis | Mutual positive co-mention + shared ecosystem/platform where both materially benefit (e.g. OS↔chip, cloud↔GPU). Requires evidence of two-way benefit. |

## Peer discovery (manager only — seeds the node set)

Node creation happens **once, by the manager**, before fan-out. Workers never
expand the universe.

1. `COMPANY_OVERVIEW(primary)` → sector, industry.
2. A Massive peer screen (same sector/industry, by market cap) and/or
   `ETF_PROFILE` holdings of a sector ETF → candidate peers (cap to top 6–8).
3. `NEWS_SENTIMENT(primary)` → frequently co-mentioned tickers (competitors, partners, suppliers).
4. De-dupe, assign `role` (primary | peer | supplier | customer | partner), upsert nodes.

## Moat assessment (relationship analyst, primary ticker)

The ecological extension: a moat is the organism's **defended niche**. The
relationship analyst assesses it because moats are fundamentally *relational* —
they live in the edges (who is locked to whom) as much as in the financials.

**Sources** (score each 0..1 with cited evidence; omit non-applicable):

| Source | What to look for |
|---|---|
| intangibles / brand | pricing power, patents, licenses, brand-led share stability |
| switching costs | customers/partners locked in — inbound `dependency` edges, integration depth |
| network effects | value grows with participants — `symbiosis` density, platform position |
| cost advantage | structural cost lead (scale, process, location) vs `competition` neighbors |
| efficient scale | niche too small for a second entrant; few/no `competition` edges in segment |

**Graph-derived evidence:** inbound `dependency` (weighted) = others rely on the
firm (+); outbound `dependency` = squeezable reliance (−); `symbiosis` density =
lock-in (+); many high-weight `competition` edges = contested niche (−).

**Fundamentals corroboration** (read from the node's `findings.fundamentals`):
sustained ROIC ≳15%, high/expanding gross margin, and share stability support the
claim; erosion undercuts it.

**Verdict:** `rating` ∈ {wide, narrow, none} + `trend` ∈ {widening, stable,
eroding} + biggest threat + 3–5 sentence justification. Stored on the primary
node under `findings.relationship.moat` and in `data/relationships.json`.

## Graph reasoning (handed to synthesis)

- **Centrality** (`graph_centrality`): high-centrality peers are systemic — shocks
  propagate through them.
- **Risk propagation**: if a `dependency` target has deteriorating fundamentals/
  sentiment, flag transmitted risk to the dependent (weight × source severity).
- **Clusters/blocs**: dense `competition` subgraphs = rivalrous blocs; dense
  `symbiosis`/`collaboration` = alliances/ecosystems.
