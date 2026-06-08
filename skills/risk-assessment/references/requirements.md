# Product Requirements — Market Risk Assessment Agent

**Version:** 1.0 · **Date:** 2026-07-12 · **Status:** Approved; v1 core built.
**Companion:** [service-recommendation-sheet.md](service-recommendation-sheet.md) (data-stack pricing).

> This is a requirements document (PRD). It specifies **what** the product must do
> and the qualities it must have — not how it is implemented. Consolidates the prior
> R&D plan, data-source validation, and build plan.

---

## 1. Purpose & vision

A **market risk-assessment agent** that presents rigorous, quantitative,
cross-verified sentiment and risk indicators to **advise trading of US equity
benchmarks**. It informs a human or downstream system about the *current state of
market risk* and how comparable states have historically resolved — it does not
make trading decisions. The core value is **trustworthy signal**: every headline
reading is confirmed across independent sources, contextualized against its own
history, and fully traceable.

## 2. Scope

- **Benchmarks (fixed):** S&P 500 (SPX/SPY), NASDAQ-100 (NDX/QQQ), and the
  semiconductor complex (SMH / SOX). Semiconductors are a **first-class** benchmark:
  the high-beta engine of NDX and a leading tell for broad risk appetite.
- **Assessment cadence:** a **full assessment once daily**, with per-indicator
  refresh granularity tiered by signal volatility (FR-6).
- **Analytical lenses:** macro, sector/industry, and market/microstructure, plus a
  dedicated fear & complacency sub-system.

## 3. Users & primary use case

A trader/analyst (or an automated downstream consumer) who wants a **daily,
defensible read on risk conditions** for SPX/NDX/SMH before making their own
decisions. They need to know not just a number but *how confident* it is (do sources
agree?), *how extreme* it is (vs. history), and *what has followed* similar readings.

---

## 4. Functional requirements

**FR-1 — Non-directional advisory output.** The product presents indicators, their
state, their historical analogues, and cross-channel agreement/disagreement. It
**must not** issue buy/sell/size/timing decisions, directional calls ("go long",
"hedge now"), price targets, or a single blended buy/sell rating. The decision is
left to the human/downstream system.

**FR-2 — Three-lens indicator coverage.** The agent must score three layers, each
answering a distinct question:
- **Macro** (regime backdrop): yield curve / recession odds, financial-conditions &
  stress, rates & liquidity, growth & labour, inflation trend.
- **Sector / industry** (is risk appetite broad or narrow?): sector relative
  strength and offense-vs-defense leadership; the semiconductor complex vs. SPX and
  NDX as an early-warning divergence; style/size risk appetite; sector/industry
  valuation multiples vs. their own history.
- **Market / microstructure** (the tape): trend & momentum vs. key moving averages,
  breadth, the volatility surface (level and term structure), and positioning.

**FR-3 — Multi-channel cross-verification (the core differentiator).** Every
headline signal must be confirmed in **≥2 independent data channels** before it is
surfaced with full confidence. When channels agree within tolerance the signal is
high-confidence; when they disagree beyond tolerance the product must raise an
explicit **divergence** flag and lower confidence; a signal available from only one
source must be labelled **provisional**.

**FR-4 — Fear & complacency sub-system.** The agent must distinguish
**complacency** indicators (contrarian; tend to lead corrections — e.g. very low
volatility, crowded long positioning, deep contango) from **fear** indicators
(coincident/lagging; mark corrections underway and precede recoveries — e.g.
volatility spikes, widening credit spreads, breadth washouts). Extremes must be
identified and their contrarian nature flagged.

**FR-5 — Historical calibration & analogues.** Extreme readings must be contextualized
empirically, not asserted:
- Label historical **correction episodes** (≥5% and ≥10% drawdowns of the
  benchmarks) and **recovery episodes**.
- For each indicator, report the **conditional forward-return distribution** (with a
  win/negative rate) given the current reading's historical bucket.
- Backtested relationships must be **independently reproduced** from primary history,
  never inherited from a third-party's published backtest.
- Output is a distribution and confidence, **never a point forecast**.

**FR-6 — Tiered refresh cadence & staleness.** Refresh frequency is tiered by signal
nature, not uniform: fear/complacency & microstructure signals **daily**; slower
sentiment & valuation multiples **weekly**; macro releases **monthly / on release**.
A daily run re-pulls only what is due, reuses fresh cached values otherwise, and
must flag any indicator whose data is **stale** beyond its refresh tolerance.

**FR-7 — Provenance & auditability.** Every reading must carry provenance (source,
series identity, timestamp, and the transform applied). Every derived number must be
reproducible and reviewable from its inputs.

**FR-8 — Composite state.** The agent must produce per-layer sub-scores and an
overall reading on a single, clearly-defined risk axis, plus an **agreement metric**
(the share of indicators whose channels concur). Composite weighting for v1 is
**equal-weight** (confidence-scaled); calibration-derived weighting is deferred to
avoid overfitting. The composite is a **state description**, never a directive.

**FR-9 — Outputs.** Each run must produce (a) a machine-readable dashboard summary
and (b) a human-readable report that surfaces: per-indicator state + percentile +
contributing channels, cross-channel agreement / divergence flags,
historical-analogue distributions, contrarian extremes, and a data-quality /
provenance footer.

---

## 5. Non-functional requirements

**NFR-1 — Determinism & reproducibility.** Given the same input readings, the
product must yield byte-identical results. Re-running an assessment on stored inputs
must reproduce the same numbers.

**NFR-2 — Numerical rigor.** Every quantitative figure must be *computed* by a
deterministic, tested calculation path — never estimated, approximated, or asserted
by a language model. Language-model output is confined to narrative interpretation.

**NFR-3 — Data-source resilience & graceful degradation.** A single source outage
must not sink a run: an unavailable channel degrades its indicator to
provisional/missing (with the reason recorded), and the run completes with the
remaining evidence. Calibration history must not depend on live third-party calls.

**NFR-4 — Cost & rate-limit compliance.** The product must operate within the free /
as-provisioned data budget where possible and must respect hard source limits (e.g.
a 25-requests/day cap on one provider) as designed constraints, not incidental
failures. Any paid escalation path is documented in the service sheet.

**NFR-5 — Independence.** The agent is architecturally independent of the existing
equity-research subagents and single-stock investment model. It may reuse shared
auditable-arithmetic and scheduling primitives, but defines its own indicator set,
data dependencies, and outputs.

**NFR-6 — Enforced non-directionality.** FR-1 must be enforced automatically: the
build/release of a report must fail if directive or recommendation language appears.
The boundary is a testable gate, not a stylistic guideline.

**NFR-7 — Maintainability / extensibility.** The indicator set must be extensible by
declaration (adding or retiring an indicator, its channels, transform, and direction)
without bespoke rework of the assessment logic.

**NFR-8 — Security.** No secrets or API keys are committed; credentials are never
exposed in provenance, logs, or outputs.

**NFR-9 — Robustness of statistics.** Percentile / z-score context must degrade
sensibly when history is short (reduced confidence rather than false precision), and
guard against non-finite or nonsensical values.

---

## 6. Data-source requirements

The product depends on external data providers to satisfy FR-2/3/4. Requirements at
the capability level (availability validated 2026-07-11; pricing and vendor
trade-offs in [service-recommendation-sheet.md](service-recommendation-sheet.md)):

| Capability required | Must provide | Cross-check role |
|---|---|---|
| Authoritative macro & stress series | Yield curve, financial-conditions/stress indices, HY credit spread, inflation, VIX reference | Reference channel for macro & volatility |
| Sector/industry valuation | Native sector & industry P/E vs. history | Satisfies the weekly valuation lens |
| Full treasury curve | Daily curve to derive 2s10s / 3m10y | Independent yield-curve channel |
| Futures positioning | Speculator net positioning on S&P 500, Nasdaq-100, and VIX futures | New fear/positioning channel |
| Market & microstructure | Index/ETF prices, breadth inputs, options & skew | Primary market channel |
| Fear composite (convenience) | Composite fear/greed, VIX term structure | Tertiary confirmation only — never a sole dependency |
| Retail sentiment | Bull/bear survey | Best-effort weekly cross-check |

**Requirement:** each headline signal must have its **≥2 independent channels**
identified and available; no signal may depend solely on an undocumented/unofficial
source.

---

## 7. Boundaries & out of scope

- No trade execution, order sizing, position management, or portfolio construction.
- No single-name equity research (that is the separate equity-research workflow).
- No point forecasts or price predictions; only state and conditional distributions.
- No dependency on bot-protected/unavailable sources for any required signal.

## 8. Assumptions & constraints

- Benchmarks are fixed to SPX, NDX, SMH; semis positioning may be **proxied** where
  no direct semis futures positioning series exists (to be confirmed in calibration).
- Paid data is acceptable but not required; the as-provisioned stack is the baseline.
- Indicator relationships are non-stationary — the product must use rolling windows
  and periodic recalibration rather than fixed thresholds.
- "Correlation ≠ timing": complacency can persist; the non-directional framing is the
  honest response to this limitation.

## 9. Acceptance criteria

1. A daily run produces both output artifacts for SPX/NDX/SMH across all four
   analytical layers. *(FR-2, FR-9)*
2. Every headline signal is shown with ≥2 channels or an explicit provisional flag;
   channel disagreement raises a divergence flag. *(FR-3)*
3. Fear vs. complacency indicators are distinguished and extremes flagged. *(FR-4)*
4. Extreme readings are accompanied by conditional historical-analogue distributions
   derived from independently reproduced episode calibration. *(FR-5)*
5. Refresh honors the tiered cadence and flags stale data. *(FR-6)*
6. Every number is reproducible from provenance; identical inputs reproduce identical
   outputs. *(FR-7, NFR-1, NFR-2)*
7. A report containing directive/recommendation language fails the release gate.
   *(FR-1, NFR-6)*
8. A single source outage yields a completed, degraded run, not a failure. *(NFR-3)*
