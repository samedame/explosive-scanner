"""Dev check: score.outcomes_for reproduces the backtest's mx / E50 / Rule X on historical snapshots."""
import sys, duckdb, numpy as np, pandas as pd
sys.path.insert(0, '.')
from scanner import features, score
BT = '/home/claude/explode'
con = duckdb.connect()
dates = ['2023-03-06', '2023-03-13', '2023-03-20']
ref = con.execute(f"select symbol,d,mx,xr from '{BT}/out2/elig_feat_*.parquet' where d in ({','.join(repr(d) for d in dates)})").df()
syms = ref.symbol.unique()
p = con.execute(f"select symbol,d,o,h,l,c,v from '{BT}/out/panel_all3.parquet' where d in (select d from '{BT}/out/calendar.parquet') and d between '2022-01-01' and '2023-09-15' and symbol in ({','.join(repr(s) for s in syms)})").df()
W = {k: p.pivot(index='d', columns='symbol', values=k).sort_index() for k in 'ohlcv'}
f = features.compute_features(W['o'], W['h'], W['l'], W['c'], W['v'])
tot = []
for d in dates:
    snap = features.snapshot(f, pd.Timestamp(d))
    o = score.outcomes_for(snap, W['o'], W['c'], pd.Timestamp(d), W['c'].index)
    tot.append(o)
    r = ref[ref.d == pd.Timestamp(d)].set_index('symbol')
    m = o.set_index('symbol').join(r, how='inner', rsuffix='_bt')
    print(d, 'bot eligible', len(snap), '| scored', len(o), '| in backtest set', len(m),
          '| mx max abs diff %.2e' % (m.mx - m.mx_bt).abs().max(), '| xr max abs diff %.2e' % (m.xr - m.xr_bt).abs().max(),
          '| E50 agreement', ((m.mx >= .5) == (m.mx_bt >= .5)).mean())
allr = pd.concat(tot); allr['date'] = allr.date.astype(str)
print(score.scorecard(allr)[:900])
