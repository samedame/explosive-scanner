# Catalyst context: what was tested and what the bot shows

Question: why do stocks explode, and can that information make the scanner more accurate?

Data collected (all free, point-in-time, 2020-02..2023-09 for testing): FINRA short interest (11-day publication lag), Dolt earnings calendar + EPS actual vs estimate, SEC Form 4 open-market insider trades, SEC 8-K item types, 13D/G, offering and merger/tender filings.

Findings (frozen discovery window 2020-02..2021-09, then one-time test on unseen 2022-01..2023-09):
* About 70% of explosive jumps have no earnings date or 8-K near them. Windows that end in +50% look the same as ones that do not on catalyst mix.
* Standalone lift of earnings timing, filings, and insider buying is about 1.0x (no information).
* Short interest (DTC >= 8) and a big EPS beat gave small gains in discovery. On the unseen window both **failed**: DTC>=8 lift 1.00x (CI low 0.71, excess return -1.7%), EPS beat lift 0.95x (CI low 0.70). Even the base screens weakened in 2022-23 (lift 1.12x, CI low 0.94).
* Decision rule fixed beforehand: failed -> catalyst fields are shown as **context tags only** and are not used to rank or filter alerts.

What the bot adds to each alert (second line): short interest days-to-cover and change, days to the next earnings report, last EPS surprise, recent 8-K items, 13D/G, offering and merger/tender filing warnings, insider buys/sells. SEC fields need the repo secret `SEC_CONTACT` (your email, SEC fair-access rule); without it they are simply omitted. Every source fails soft (missing data = missing tag, never a false "none").

The daily snapshots now also store the market-wide short-interest and earnings fields, so the forward scorecard can test them out of sample properly instead of trusting the backtest.
