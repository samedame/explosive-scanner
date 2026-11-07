# Pre-explosion stock scanner: verdict (2026-11-06)

## Bottom line
**I could not prove that a scan finds stocks before they explode. Verdict: NO-GO for real money.** I built the scanner and tested it under rules fixed in advance. Nothing passed the discovery gate, so the validation and sealed final segments (2022-01 onward) were never opened. Opening them would have meant testing rules that had already failed.

What the data does support: several simple screens (strong 12-1 momentum, near the 52-week high, a trend template, or "already extended but not top-ranked") raise the chance of a +50% move within 63 days by about **1.25-1.35x** versus stocks with the same volatility, price tier, size tier and date. That tilt is statistically visible but small. After realistic costs it is worth about +1% to +4% per trade, and nothing here clears the frozen bar of at least 1.3x lift with t of at least 2 and positive results in both halves.

## What was built
- **Point-in-time panel, 1997 to 2026-11-05.** HuggingFace/Yahoo prices (survivors only) plus delisted names pulled from DoltHub from 2018-10. About 14.6k symbols, 38.5M rows. Traded (unadjusted) prices come from DoltHub raw data.
- **Frozen event definition:** "explosion" = max close within 63 days of next-open entry is at least +50% (E50) or +100% (E100). Trades follow Rule X: enter the next open, exit on a 25% trailing stop on closes or after 63 days.
- **Controls:** same date, same volatility decile, same price tier and same size tier. Month-clustered bootstrap (2,000 draws, seed 20261106) and month-clustered t-stats.
- **Costs:** 10 / 25 / 60 bp per side by dollar-volume tier, plus 30 bp under $5.
- **Eligibility:** 1-5 letter tickers, no ETFs, warrants or SPACs, traded price of at least $3, 50-day dollar volume of at least $2M, at least 253 rows, no gaps, and no unverified data glitches.
- **Scanner:** `scan.py` applies the same feature SQL and screens to the latest day and appends to a forward log. It is shadow-mode only.

## Results
**Round 1** (12 screens, 1997-2018, survivor-biased): NO-GO. Best L50 was 1.32 (screen A3) against the required 1.5. Exploratory ML showed large lift in cheap, illiquid, volatile names, exactly where survivorship bias is worst. That segment was therefore dropped for selection.

**Round 2** (point-in-time only; discovery 2019-01 to 2021-09; V2 and F2 unopened):

| Candidate | Episodes | Hit rate vs matched control | L50 lift (90% CI low) | Net excess/trade | t | 2x costs |
|---|---|---|---|---|---|---|
| A3 trend + RS90 + near high | 2,573 | 12.3% vs 9.2% | 1.35 (1.20) | +1.2% | 1.34 | +0.8% |
| A2 trend + RS80 + near high + squeeze | 2,411 | 5.9% vs 4.5% | 1.31 (1.09) | +1.4% | 1.63 | +1.0% |
| C1 RS90 only | 3,773 | 14.4% vs 11.4% | 1.26 (1.16) | +1.6% | 1.77 | +1.1% |
| B3 52-week breakout + volume + trend | 2,273 | 12.0% vs 9.4% | 1.27 (1.13) | +0.2% | 0.16 | -0.3% |
| Search rule: extended > SMA200 by 53%+, RS <= 80, squeeze <= 5.3 | 1,556 | 20.3% vs 16.0% | 1.27 (1.15) | +4.2% | 3.52 | +3.6% |
| Search rule: extended, bottom-30% dollar volume, lower-half price | 1,466 | 21.9% vs 17.5% | 1.25 (1.16) | +2.5% | 2.80 | +1.4% |

Base rates in that window: P(E50) was 7.6% and P(E100) 1.6% across all eligible stock-days (a 2020-21 mania-heavy period).

- **Gate D2 outcome:** 0 of 12 frozen screens and 0 of the 25 beam-search rules passed. The closest were L50 1.27 with t = 3.5. The search tested about 15,000 conjunctions, so that t-stat does not survive multiple-testing correction. The best search rules favour illiquid names (median dollar volume $3.5M-$13M), where the edge is most sensitive to execution costs.
- **Survivorship:** on the same screens, survivors-only data overstated lift by about 0.06-0.10 and excess return by about 0.3 points in 2019-21. The effect is larger before 2019, which is why 1997-2018 was not used for selection.
- **Power:** with roughly 1,500-2,500 episodes, the test resolves lifts of about 1.15-1.25x at best. A real 1.3x edge is hard to separate from noise in one three-year window.

## Engine verification
- Independent plain-loop Rule X on 20,000 random signals: 3 mismatches (0.015%), probably float32 edge cases.
- Independent SMA50, SMA200, 52-week high and volume-ratio on 3,000 rows: 0 mismatches.
- Look-ahead truncation test (60 symbols cut at 2023-06-30): 0 of 8.95M feature cells changed.

## Limitations
- The 2019-21 discovery window is dominated by a 2020 crash and a 2021 speculative peak.
- Daily bars only: no intraday fills, halts or borrow.
- Costs are assumptions, not measured fills.
- Explosive moves are mostly news-driven (FDA, M&A, earnings); price and volume can only show a footprint.
- The data-hardening steps D4 and D5 (traded-price eligibility, bad-day exclusion) were added after I saw exploratory Round 2 results. They are logged in `PREREG.md`. They were applied before V2/F2 were touched, and they change data integrity, not the gates.
- The delisted-name layer comes from DoltHub from 2018-10 and may contain stale prints. 1-2% of adjusted-vs-traded checks disagreed and were excluded.

## What to do with this
1. Treat the scanner as a **watchlist generator**, not a signal. Do not size positions on it. The 2026-11-05 watchlist is included (363 flagged names out of 3,208 eligible).
2. Run it daily in shadow mode. `forward_log.csv` accumulates true out-of-sample hit rates, so another year of data can test the 1.25-1.35x tilt cleanly.
3. A stronger edge probably needs information this data lacks: catalysts, earnings and estimate revisions, short interest, float and options flow. A pre-registered Round 3 on those data is the sensible next step.

Files: `scan.py`, `features2.py`, `allowed_symbols.parquet`, `watchlist_2026-11-05.csv`, result CSVs, `PREREG.md`, `ROUND2_PREREG.md`, `screens.py`, `HASHES.txt`.
