"""Feature + screen engine. Pure pandas, operates on wide frames (index=dates, columns=symbols).
Definitions mirror the backtest SQL (features2.py) so live flags match what was tested.
All features at date t use data through close t only."""
import numpy as np, pandas as pd

SIGNAL_SCREENS = ['A3', 'A2', 'B3', 'R2a', 'R2b']   # alert-eligible screens
CONTEXT_SCREENS = ['C1']                            # recorded in snapshots, not alerted
ALL_SCREENS = SIGNAL_SCREENS + CONTEXT_SCREENS
SCREEN_TEXT = {
    'A3': 'Trend template + RS>=90 + within 5% of 52w high',
    'A2': 'Trend template + RS>=80 + within 15% of 52w high + Bollinger squeeze',
    'B3': '52w-high breakout + volume>=1.5x + strong close + trend + RS>=80',
    'R2a': 'Extended (>=53% above SMA200) + RS<=80 + squeeze ratio<=5.3',
    'R2b': 'Extended (>=37% above SMA200) + bottom-30% dollar volume + lower-half price rank',
    'C1': 'RS>=90 (context only)',
}

def _mp(w):  # tolerate a couple of missing sessions per window (the eligibility rule caps gaps at 2 per 252 anyway)
    return max(1, w - max(1, w // 15))

def _r(x, w):
    return x.rolling(w, min_periods=_mp(w))

def compute_features(O, H, L, C, V):
    """Return dict of wide frames for the LAST row only plus the helpers needed (cheap: full rolling then slice)."""
    Cf = C.ffill(limit=5)
    pc = Cf.shift(1)
    r1 = C / pc - 1
    sma20 = _r(C, 20).mean(); sd20 = _r(C, 20).std(ddof=0)
    sma50 = _r(C, 50).mean(); sma150 = _r(C, 150).mean(); sma200 = _r(C, 200).mean()
    bbw = 4 * sd20 / sma20
    bbmin = _r(bbw, 252).min()
    sq = bbw / bbmin
    sqr = _r((sq <= 1.30).astype(float).where(sq.notna()), 10).max()
    f = {
        'c': C, 'sma50': sma50, 'sma150': sma150, 'sma200': sma200, 'sma200_21': sma200.shift(21),
        'hi252': _r(H, 252).max(),
        'hi252p': _r(H, 252).max().shift(1),
        'lo252': _r(L, 252).min(),
        'sq': sq, 'sqr': sqr,
        'vrat': V / _r(V, 50).mean().shift(1),
        'clv': (C - L) / (H - L).replace(0, np.nan),
        'dv50p': _r(C * V, 50).mean().shift(1),
        'ret252_21': Cf.shift(21) / Cf.shift(252) - 1,
        'vol60': _r(r1, 60).std(ddof=1),
        'cmin120': _r(C, 120).min(), 'cmax120': _r(C, 120).max(),
        'maxjump': np.log(C / pc).abs().rolling(252, min_periods=1).max(),
        'nvalid252': C.notna().astype(float).rolling(252, min_periods=1).sum(),
        'nrows': C.notna().astype(float).cumsum(),
    }
    return f

def snapshot(f, asof):
    """Cross-section at `asof` -> DataFrame with eligibility, ranks and screen flags."""
    d = pd.DataFrame({k: v.loc[asof] for k, v in f.items()})
    d.index.name = 'symbol'
    # ---- eligibility (frozen E-rules; traded price = last close, split-adjusted history is a proxy for lows) ----
    el = (d.c >= 3.0) & (d.dv50p >= 2e6) & (d.lo252 >= 1.0) & (d.nrows >= 253) & (d.nvalid252 >= 250) \
         & ~((d.cmin120 >= 9.0) & (d.cmax120 <= 11.2)) & (d.maxjump <= np.log(5)) & d.sma200_21.notna() & d.sq.notna()
    d = d[el].copy()
    d['rs'] = d.ret252_21.rank(pct=True)
    d['lvolk'] = d.vol60.rank(pct=True)
    d['vdec'] = (d.lvolk * 10).clip(upper=9.999).astype(int)
    d['ldvk'] = d.dv50p.rank(pct=True)
    d['lpk'] = d.c.rank(pct=True)
    d['d200'] = d.c / d.sma200 - 1
    d['dhi'] = d.c / d.hi252 - 1
    T = (d.c > d.sma50) & (d.sma50 > d.sma150) & (d.sma150 > d.sma200) & (d.sma200 > d.sma200_21)
    d['A3'] = T & (d.rs >= .90) & (d.c >= .95 * d.hi252)
    d['A2'] = T & (d.rs >= .80) & (d.c >= .85 * d.hi252) & (d.sq <= 1.30)
    d['B3'] = (d.c > d.hi252p) & (d.vrat >= 1.5) & (d.clv >= .60) & T & (d.rs >= .80)
    d['R2a'] = (d.d200 >= .53) & (d.rs <= .80) & (d.sq <= 5.3)
    d['R2b'] = (d.d200 >= .37) & (d.ldvk <= .30) & (d.lpk <= .50)
    d['C1'] = d.rs >= .90
    d['n_signal'] = d[SIGNAL_SCREENS].sum(axis=1)
    return d
