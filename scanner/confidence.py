"""Per-alert confidence for the Explosive-Scanner, in the same shape as the rest of the fleet: setup + execution, tiers A-D.

READ THIS FIRST (validated 2026-11-06, see docs/CONFIDENCE.md):
* SETUP (how many screens fired) did NOT validate: AUC for a +50% move was 0.515 (95% CI 0.497-0.532) in 2019-21 and 0.536 (0.511-0.568) in 2022-23.
  The pre-registered rule needed both lower bounds above 0.5, so SETUP_WEIGHT is 0 and the score is execution-only.
* EXECUTION is mechanical (cost tier, price level, data freshness). It is NOT a forecast of an explosion: it is anti-correlated with one
  (AUC 0.37 for +50%, because small illiquid names explode more), and weakly positive for NET-of-cost outcomes (AUC 0.53-0.56).
* The honest odds are the separate 'history' line: ~10% of single-screen alerts (18% of multi-screen) gained +50% within 63 sessions, 5.4% in 2022-23.
"""
import datetime as dt

SETUP_WEIGHT = 0.0          # frozen by the V1 gate; do not raise without a new pre-registered test that passes
EXEC_WEIGHT = 1.0 - SETUP_WEIGHT
# pooled 2019-01..2023-09 episode hit rates for max close >= +50% within 63 sessions (docs/confidence_v5_hit_rates.csv)
ODDS = {1: dict(p=0.103, n=4153, recent=0.054), 2: dict(p=0.181, n=227, recent=0.152)}   # bucket 2 = two or more screens

def _liq(dv): return 1.0 if dv >= 2e7 else 0.75 if dv >= 5e6 else 0.5
def _px(c): return 1.0 if c >= 5 else 0.6

def tier(score):
    return 'A' if score >= 85 else 'B' if score >= 70 else 'C' if score >= 50 else 'D'

def score_alert(row, fresh=True, merger=False, offering=False, equity_sale=False):
    """row: dict-like with c (close), dv50p (50d avg dollar volume), n_signal (screens firing)."""
    n = int(row['n_signal']); dv = float(row['dv50p']); c = float(row['c'])
    liq, px, fr = _liq(dv), _px(c), 1.0 if fresh else 0.0
    execution = 100.0 * (liq + px + fr) / 3.0
    setup = min(100.0, 25.0 * n)
    score = SETUP_WEIGHT * setup + EXEC_WEIGHT * execution
    caps = []
    if not fresh: score = min(score, 49.0); caps.append('stale data')
    if merger: score = min(score, 69.0); caps.append('merger/tender filing')
    score = round(score)
    b = ODDS[1 if n <= 1 else 2]
    drag = min([('liquidity', liq), ('price under $5', px), ('data freshness', fr)], key=lambda kv: kv[1])
    warns = []
    if merger: warns.append('MERGER/TENDER filing: pending deals pin the price (history: 2 percent hit rate)')
    if offering: warns.append('offering filing (dilution risk; history mixed)')
    if equity_sale: warns.append('8-K 3.02 equity sale (history: too few cases)')
    return dict(score=score, tier=tier(score), setup=round(setup), execution=round(execution), setup_scored=SETUP_WEIGHT > 0,
                caps=caps, odds_p=b['p'], odds_n=b['n'], odds_recent=b['recent'], drag=None if drag[1] >= 1.0 else drag[0], warnings=warns)

def line(r):
    """Odds first (that is the real information), then tradeability. 'Tradeability' not 'confidence': the score measures cost and data quality only."""
    o = (f"Odds: {r['odds_p']*100:.0f}% of alerts like this gained +50% within 63 sessions ({r['odds_recent']*100:.0f}% in 2022-23, n={r['odds_n']:,}); most do not")
    t = (f"Tradeability {r['score']}/100 tier {r['tier']} (cost and data quality only; says nothing about odds)"
         + (f" · capped: {', '.join(r['caps'])}" if r['caps'] else '') + (f" · drag: {r['drag']}" if r['drag'] else ''))
    return o + '\n　' + t
