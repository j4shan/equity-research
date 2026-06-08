# Analysis Framework

Metrics, thresholds, and scoring each analyst applies. Each analyst emits a
per-ticker **score in [-1, +1]** (bearish→bullish read *within its own
dimension*) plus structured findings.

## Synthesis (manager) — no recommendation

The manager **synthesizes across dimensions; it does not produce a composite
score, a rating, or any form of buy/sell recommendation.** Dimension scores are
presented side by side, never blended. The synthesis:

- states what each dimension independently says and how convergent/divergent they are;
- surfaces conflicts explicitly (e.g. bullish fundamentals vs bearish technicals)
  rather than resolving them into a single number;
- folds in graph-level findings (moat, dependencies, transmitted risks) as
  qualifiers on durability;
- ends with an evidence map — catalysts, risks, and what would change each
  dimension's read — leaving the investment decision to the reader.

## Numerical discipline (all agents)

Every derived number — ratios, growth rates, margins, averages, z-scores —
**must be computed via the Research Hub `calc_evaluate` tool**, never mentally.
Pass the inputs as variables so the expression is auditable, e.g.
`calc_evaluate("(rev1-rev0)/rev0", {"rev1": …, "rev0": …})`.

## Fundamentals analyst

Data tools (Alpha Vantage): `COMPANY_OVERVIEW` (profile + valuation ratios),
`INCOME_STATEMENT`, `BALANCE_SHEET`, `CASH_FLOW`, `EARNINGS`, `EARNINGS_ESTIMATES`,
`DIVIDENDS`. For the **peer set** comparison, pull bulk fundamentals via Massive
(`call_api` → `store_as` → `query_data`).

| Dimension | Metrics | Bullish signal |
|---|---|---|
| Valuation | P/E, P/S, EV/EBITDA, PEG, P/B | Below peer median / historical avg |
| Growth | Revenue & EPS YoY, fwd estimates | Accelerating, beats estimates |
| Profitability | Gross/Op/Net margin, ROE, ROIC | High & expanding vs peers |
| Financial health | Current ratio, Debt/Equity, interest coverage, FCF margin | Low leverage, positive FCF |
| Earnings quality | Surprise history, accruals, buybacks | Consistent beats, clean accruals |

Always compute **relative** metrics against the peer set (read peers from the
shared graph). Score = weighted sum of dimension z-scores vs peers, squashed to [-1,1].

## Technical analyst

Data tools (Alpha Vantage): `TIME_SERIES_DAILY_ADJUSTED` (historical OHLCV), the
indicator tools (`SMA`, `EMA`, `RSI`, `MACD`, `BBANDS`, `ADX`, `ATR`, `OBV`,
`STOCH`, `VWAP`), and `GLOBAL_QUOTE` (latest price). There is no support/resistance
tool — compute classic pivot levels from recent highs/lows/closes via `calc_evaluate`.

| Dimension | Indicator | Bullish signal |
|---|---|---|
| Trend | Price vs SMA50/SMA200, golden/death cross, ADX>25 | Price above rising MAs |
| Momentum | RSI(14), MACD histogram, STOCH | RSI 50–70 rising; MACD>signal |
| Volatility | Bollinger width, ATR | Contracting before breakout |
| Volume | OBV trend | OBV confirms price |
| Levels | Recent swing highs/lows | Holding support / breaking resistance |

Flag extremes: RSI>70 overbought, RSI<30 oversold. Emit a signal table and a
score in [-1,1] from trend+momentum alignment.

## Sentiment analyst

Data tools (Alpha Vantage): `NEWS_SENTIMENT`, `INSIDER_TRANSACTIONS`,
`INSTITUTIONAL_HOLDINGS`, `HISTORICAL_PUT_CALL_RATIO`.

| Dimension | Source | Bullish signal |
|---|---|---|
| News tone | `NEWS_SENTIMENT` polarity + article trend | Rising, net positive |
| Narrative | `NEWS_SENTIMENT` topic tags | Positive themes dominate |
| Insider flow | `INSIDER_TRANSACTIONS` buy/sell count & $ | Net buying by execs |
| Smart money | `INSTITUTIONAL_HOLDINGS` positioning trend | Rising institutional ownership |
| Options tone | `HISTORICAL_PUT_CALL_RATIO` | Falling put/call ratio |

Score in [-1,1] from the blended sentiment signals; note any divergence between
news tone, insider behavior, institutional positioning, and options sentiment.

## Macro context (optional, folded into fundamentals)

`TREASURY_YIELD`, `FEDERAL_FUNDS_RATE`, `CPI`, sector commodities — use to frame
rate sensitivity and input-cost exposure; do not override company-specific score.
