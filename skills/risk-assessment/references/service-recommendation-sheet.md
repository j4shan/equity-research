# Service Recommendation Sheet — Paid Data Stack

_Companion to [requirements.md](requirements.md). Prepared 2026-07-11, refreshed 2026-07-12. Prices
are list prices gathered from vendor/aggregator pages this month and **must be re-confirmed at
procurement** — Polygon/Massive in particular was mid-rebrand. Currency as published (USD unless
noted €)._

> **STATUS 2026-07-12 — the agent is BUILT and running on Tier 0 (as-provisioned, ~$0 marginal).**
> The v1 core operates on the three connected claude.ai connectors (**FMP, Massive, Alpha Vantage**)
> plus **FRED**. **FMP** is confirmed at **Premium-or-higher** (the Premium-gated COT endpoint
> returned data), which single-handedly covers the paid fundamentals/valuation line: native
> sector/industry P/E, full treasury curve, COT positioning (ES/NQ/VX), and technical indicators —
> all at **$0 marginal cost**. The only outstanding action is a **free FRED API key** (without it the
> FRED macro channels degrade gracefully to *provisional*, confirmed in the built fetch layer — the
> run still completes). The paid stacks below are retained for procurement/renewal/fallback
> reference; the **operative recommendation remains "Tier 0" (§3).**

## 1. What the agent actually needs to buy

The agent's data needs map to four buckets. Only two of them justify paid spend; the other two are
already covered for free.

| Need | Refresh | Free coverage today | Paid needed? |
|---|---|---|---|
| Macro series (yield curve, NFCI, credit OAS, CPI, payrolls, VIXCLS ref) | daily–monthly | **FRED (free, authoritative)** | ❌ No |
| Fear/complacency (VIX + VIX3M term structure, credit ETFs, breadth, put/call) | **daily** | FearGreedChart (unofficial), Massive/AV in-repo | ✅ **Yes** — to remove single-source-unofficial risk & AV's 25/day cap |
| Index/ETF/options market data (SPX, NDX, SMH, options skew, breadth) | daily | Massive MCP (in-repo, tier unknown) | ✅ **Yes** — confirm a real-time/aggregates tier |
| Sector/industry **P/E & P/S** valuation multiples | weekly/monthly | thin on free tiers | ✅ **Yes** — a fundamentals feed |

## 2. Vendor comparison

| Vendor | Relevant tier & price | What it delivers for us | Rate limit | Best-fit role |
|---|---|---|---|---|
| **FRED** | **Free** (API key) | Macro spine + authoritative VIX (`VIXCLS`) & HY OAS (`BAMLH0A0HYM2`) cross-check | ~120/min | **Keep — macro backbone (no spend)** |
| **Polygon / Massive** | Indices/Stocks **Starter ~$29/mo**; Developer ~$79; Advanced ~$199 (per asset class; re-confirm post-rebrand) | Real-time+historical **indices (VIX, SPX, NDX), ETFs (SMH), options** incl. Greeks; 20ms latency; S3 flat files; SQL workspace already wired via MCP | per-tier | **Primary market/microstructure feed** — already integrated |
| **Alpha Vantage** | Free (5/min, **25/day**) → **$49.99/mo** (75/min, no daily cap) → up to $249.99 (1,200/min) | Treasury yields, **put/call ratio**, macro, news sentiment | per-minute only above free | **$49.99 tier** *only if* we keep leaning on its put/call & news; else drop |
| **EODHD** | **All-in-One €99.99/mo** (~$108); Fundamentals €59.99; EOD €19.99 | Historical + fundamentals + intraday + news bundled; **sector/industry fundamentals** | generous | **Fundamentals + valuation multiples** (sector P/E, P/S) — standalone bundle |
| **Financial Modeling Prep** | Starter **$15–29/mo**; Premium **$99/mo**; Ultimate higher | Financial ratios, **sector P/E**, DCF, 13F, transcripts; 30+ yr history | bandwidth-tiered | Cheapest route to **sector/industry multiples** if not using EODHD |
| **Tiingo** | Power **$30/mo** | EOD + IEX real-time + fundamentals + news, flat rate | flat | Low-cost **backup price/fundamentals** channel |
| **Cboe DataShop / LiveVol** | **$1k+/mo** (options tick); **VIX index history = FREE CSV** on cboe.com | Definitive VIX & granular options tick | n/a | **Skip the paid tier**; use the free VIX index CSV as an authoritative cross-check |

## 3. Recommended stacks

**Tier 0 — As-provisioned (~$0 marginal). NOW THE OPERATIVE RECOMMENDATION.**
- **FMP (Premium+, already connected)** + **Massive (already connected)** + **Alpha Vantage
  (already connected)** + **FRED (free key)**, with FearGreedChart as a no-key convenience channel.
- Covers every required lens with ≥2 independent channels — sector P/E, treasury curve, and COT
  positioning all from FMP; conditions/stress from FRED; options skew from Massive.
- **No new spend.** Only action: register a free FRED key. Re-confirm FMP plan tier at renewal
  (COT + technicalIndicators depend on Premium/Starter respectively).

**Tier A — Lean paid fallback (~$45–65/mo), if the connectors are ever unavailable.**
- FRED (free) + **Massive/Polygon Starter (~$29)** + **FMP Starter (~$15–29)** for sector multiples.
- Free VIX index CSV from Cboe as the authoritative VIX cross-check; FearGreedChart demoted to a
  convenience/tertiary channel. Drop paid Alpha Vantage (use free tier for occasional put/call, or
  source put/call from Massive options).
- **Covers all three required lenses + fear module with ≥2 independent paid/authoritative channels
  per headline signal, and zero dependence on any single unofficial source.**

**Tier B — Fundamentals-consolidated (~$110–140/mo).**
- FRED (free) + Massive Starter (~$29) + **EODHD All-in-One (€99.99)** for fundamentals/valuation +
  news in one bill.
- Best if we want sector/industry fundamentals, news, and intraday under one vendor. Note: the
  existing equity-research skill standardized on **Massive + Alpha Vantage** connectors and
  **removed** its EODHD tooling — so EODHD here is a fresh, standalone add, not a reuse. If vendor
  consolidation with the rest of the repo matters more than the bundle, prefer FMP (Tier A) for
  multiples and keep the stack on Massive + AV.

**Tier C — Depth (~$250–350/mo).**
- FRED + **Massive Advanced (~$199, real-time indices+options)** + **AV $49.99** (put/call + news) +
  FMP/EODHD fundamentals. Adds real-time options skew and higher throughput.
- Only if intraday options-surface reads become part of the daily fear module.

## 4. Recommendation

**Run on Tier 0 (as-provisioned) — and the built v1 already does.** The FMP + Massive + Alpha
Vantage connectors plus a free FRED key satisfy the hard requirement (every headline signal
cross-verified across ≥2 independent channels) at **no new spend**, with no reliance on the
unofficial CNN/FearGreedChart path for any required signal. Tier A is only a **fallback** should the
connectors become unavailable; escalate to Tier C paid options data only if intraday options skew is
promoted into the daily fear module. **Action items:** (1) **register a free FRED API key** — the one
remaining gap (channels degrade to *provisional* without it, so this is a quality, not availability,
issue); (2) confirm the FMP plan tier at renewal (COT needs Premium+, technicalIndicators needs
Starter+); (3) re-confirm any fallback prices at procurement.

_Sources: polygon.io/pricing, alphavantage.co/premium, eodhd.com/pricing,
site.financialmodelingprep.com/pricing-plans, tiingo.com/pricing, datashop.cboe.com,
fred.stlouisfed.org/docs/api — all accessed 2026-07-11._
