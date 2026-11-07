# Explosive-Scanner

Daily alert bot for stocks whose price/volume footprint has historically preceded a **+50% move within 63 trading days** more often than comparable stocks. It runs after the US close, posts **new** hits to Discord, logs every day's eligible universe, and then scores itself against what actually happened.

> **Status: UNVALIDATED research tool.** In the pre-registered backtest (2019-21, point-in-time data incl. delisted names) no screen cleared the bar (best lift 1.25-1.35x; required >= 1.3x with t >= 2 in both halves). The 2022+ periods were never opened. This bot's forward log is the out-of-sample test. See `docs/VERDICT.md`.

## What it does
1. **Universe:** US common stocks from the Nasdaq Trader symbol directory (no ETFs/ETNs/warrants/units/preferreds/SPACs).
2. **Eligibility (frozen):** last close >= $3, 50-day dollar volume >= $2M, 252-day low >= $1, >= 253 sessions of history with <= 2 gaps, not a SPAC-like $10 price, no >5x one-day jump in 252 days.
3. **Screens** (`scanner/features.py`, same definitions as the backtest):
   | Screen | Meaning | Backtest lift (2019-21) |
   |---|---|---|
   | A3 | Minervini-style trend template + RS >= 90 + within 5% of 52w high | 1.35x |
   | A2 | trend + RS >= 80 + within 15% of high + Bollinger squeeze | 1.31x |
   | B3 | 52w-high breakout, volume >= 1.5x, strong close, trend, RS >= 80 | 1.27x |
   | R2a | >= 53% above SMA200, RS <= 80, squeeze ratio <= 5.3 | 1.27x |
   | R2b | >= 37% above SMA200, bottom-30% dollar volume, lower-half price rank | 1.25x |
   | C1 | RS >= 90 (logged only, never alerted) | 1.26x |
4. **Alerts:** one Discord embed per day listing names that **newly** hit any alert screen (20-session cooldown per symbol, same as the backtest's episode definition). No hits -> silent.
5. **Forward log:** `data/snapshots/YYYY-MM-DD.csv.gz` (every eligible stock with its flags and volatility decile), `data/alerts.csv`.
6. **Forward scorecard** (Saturdays): snapshots >= 100 days old are scored: max close in the 63 sessions after next-open entry, E50/E100 hit rate, Rule X (25% trailing stop) net return, each versus same-date same-volatility-decile controls, with month-bootstrap CIs. Result in `data/scorecard.md` and Discord. A screen "passes" only if n >= 150 episodes, L50 >= 1.3, CI low > 1, net excess > 0.

## Setup (5 minutes)
1. Create a **private** GitHub repo (suggested name `Explosive-Scanner`) and push this folder.
2. Settings -> Secrets and variables -> Actions -> New secret: `DISCORD_WEBHOOK_URL` (your Discord channel webhook).
3. Settings -> Actions -> General -> Workflow permissions: **Read and write**.
4. Actions tab -> `daily-scan` -> **Run workflow** once to test (takes ~20-30 min: it downloads ~4,800 tickers from Yahoo).
5. It then runs Mon-Fri 22:30 UTC automatically. The scorecard runs Saturdays.

**Quiet runs are never silent.** Every run that posts no alerts still posts one status line to Discord (`✅ ... ran OK ... 0 new` or `session already scanned`). If a run produces *nothing at all* in Discord, something is wrong before the scan starts: the job fails red in the Actions tab, and (if the webhook secret exists) posts a `❌ job FAILED` message with a link. A missing/empty `DISCORD_WEBHOOK_URL` secret fails the job with an explicit error. Set repo variable-free opt-out with env `HEARTBEAT=0` in the workflow if the daily line is too chatty.

**Re-posting alerts:** Actions -> `daily-scan` -> Run workflow -> tick **resend**. It re-posts the latest session's alerts (ignoring the 20-session cooldown) and writes no state, so it is safe to use for testing. A normal manual run on an already-scanned session only posts the status line, by design (the alert dedupe stops double-posting).

Local dry run (prints instead of posting): `pip install -r requirements.txt && python -m scanner.run_daily --dry-run`

## Known limitations
- Prices come from Yahoo via `yfinance` (split-adjusted, not dividend-adjusted). The backtest used a dividend-adjusted HuggingFace/Yahoo set plus DoltHub raw prices; features agree to rounding on identical data (`tests/equivalence_vs_backtest.py`), but live values can differ slightly.
- Traded-price tests (price >= $3, low >= $1) use the latest close and split-adjusted history; a recent reverse split can misclassify a name.
- Daily bars only; the alert says nothing about news, halts, offerings or borrow. Explosive moves are mostly catalyst-driven.
- Alerts are research flags, **not** trade instructions. Backtest net edge was +1% to +4% per trade before any execution slippage on illiquid names.

## Tests
`python tests/test_core.py` (features vs plain loops, no look-ahead, Rule X cases).

## Catalyst context (new)
Each alert carries a second line with short interest, earnings timing/surprise, recent SEC filings and insider trades. These are **context only**: they failed the pre-registered out-of-sample test (see `docs/CATALYSTS.md`). To enable the SEC part add a repository secret `SEC_CONTACT` (your email) under Settings > Secrets and variables > Actions.

## Alert score (new)
Each alert prints historical odds and a Tradeability score (A-D). Tradeability measures cost and data quality only and was validated as *not* predicting explosions (see `docs/CONFIDENCE.md`). Merger/tender filings cap the tier at C. Long alert lists are now split across several Discord messages instead of being cut off.
