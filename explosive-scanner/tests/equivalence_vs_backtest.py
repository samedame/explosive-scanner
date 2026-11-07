"""Dev check (needs the backtest parquet files): live feature engine == backtest SQL features on the same data."""
import sys, duckdb, numpy as np, pandas as pd
sys.path.insert(0, '.')
from scanner import features
BT = '/home/claude/explode'
asof = pd.Timestamp('2026-11-05')
con = duckdb.connect()
ref = pd.concat([pd.read_parquet(f'{BT}/out2/scan/feat_{k}.parquet') for k in range(4)])
ref = ref[ref.d == asof].set_index('symbol')
syms = list(ref.index[:1500])
p = con.execute(f"select symbol,d,o,h,l,c,v from '{BT}/out/panel_all3.parquet' where d in (select d from '{BT}/out/calendar.parquet') and d<='2026-11-05' and d>='2024-08-01' and symbol in ({','.join(repr(s) for s in syms)})").df()
W = {k: p.pivot(index='d', columns='symbol', values=k).sort_index() for k in 'ohlcv'}
f = features.compute_features(W['o'], W['h'], W['l'], W['c'], W['v'])
live = pd.DataFrame({k: v.loc[asof] for k, v in f.items()})
cmp = {'sma50': 'sma50', 'sma200': 'sma200', 'sma200_21': 'sma200_21', 'hi252': 'hi252', 'hi252p': 'hi252p', 'sq': 'sq', 'sqr': 'sqr', 'vrat': 'vrat', 'clv': 'clv',
       'dv50p': 'dv50p', 'ret252_21': 'ret252_21', 'vol60': 'vol60'}
el = ref.index[(ref.gap252 <= 0) & ref.index.isin(syms)]   # symbols with complete 252-session history (no missing days), where row-lags and calendar-lags coincide
print('symbols compared (no gaps):', len(el))
for a, b in cmp.items():
    x = live[a].reindex(el); y = ref.loc[el, b]
    m = x.notna() & y.notna()
    rel = ((x[m] - y[m]).abs() / (1e-9 + y[m].abs()))
    print(f'{a:10s} n={int(m.sum()):5d}  share within 1e-4: {(rel<1e-4).mean():.4f}  p99.9 rel diff {rel.quantile(.999):.2e}  nan-mismatch {int((x.isna()!=y.isna()).sum())}')
x = live['sq'].reindex(el); y = ref.loc[el, 'sq']; m = x.notna() & y.notna()
rel = ((x[m] - y[m]).abs() / y[m].abs()); bad = rel[rel > 1e-4]
print('sq mismatches', len(bad), 'of', int(m.sum()), '| >1%:', int((rel > .01).sum()), '| >10%:', int((rel > .1).sum()))
t = bad.index[:3]; print(pd.DataFrame({'live': x[t], 'bt': y[t], 'nrows_hist': ref.loc[t, 'n']}))
