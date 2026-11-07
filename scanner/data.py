"""Price download (yfinance, split-adjusted, not dividend-adjusted) into wide frames."""
import time, datetime as dt, numpy as np, pandas as pd, yfinance as yf

def _frames(raw, tickers):
    out = {k: {} for k in ['Open', 'High', 'Low', 'Close', 'Volume']}
    if raw is None or raw.empty: return out
    if not isinstance(raw.columns, pd.MultiIndex):   # single ticker
        t = tickers[0]
        for k in out: out[k][t] = raw[k]
        return out
    lv0 = set(raw.columns.get_level_values(0))
    for t in tickers:
        if t not in lv0: continue
        sub = raw[t]
        if sub['Close'].notna().sum() == 0: continue
        for k in out: out[k][t] = sub[k]
    return out

def download(tickers, start, chunk=300, pause=1.0, log=print):
    acc = {k: [] for k in ['Open', 'High', 'Low', 'Close', 'Volume']}
    missing = []
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        raw = None
        for attempt in range(3):
            try:
                raw = yf.download(part, start=start, interval='1d', auto_adjust=False, group_by='ticker',
                                  progress=False, threads=True, timeout=30); break
            except Exception as e:
                log(f'chunk {i} attempt {attempt}: {e}'); time.sleep(3 * (attempt + 1))
        fr = _frames(raw, part)
        got = set(fr['Close'])
        missing += [t for t in part if t not in got]
        for k in acc:
            if fr[k]: acc[k].append(pd.DataFrame(fr[k]))
        log(f'downloaded {min(i + chunk, len(tickers))}/{len(tickers)}')
        time.sleep(pause)
    # second pass, single-threaded, for tickers that failed (sqlite cache lock etc.)
    retry = [t for t in missing]
    for i in range(0, len(retry), 50):
        part = retry[i:i + 50]
        try:
            raw = yf.download(part, start=start, interval='1d', auto_adjust=False, group_by='ticker',
                              progress=False, threads=False, timeout=30)
            fr = _frames(raw, part)
            for k in acc:
                if fr[k]: acc[k].append(pd.DataFrame(fr[k]))
        except Exception as e:
            log(f'retry {i}: {e}')
    if not acc['Close']: raise RuntimeError('no price data downloaded')
    wide = {k: pd.concat(v, axis=1) for k, v in acc.items()}
    wide = {k: v.loc[:, ~v.columns.duplicated()].sort_index() for k, v in wide.items()}
    return wide['Open'], wide['High'], wide['Low'], wide['Close'], wide['Volume']

def clean(O, H, L, C, V):
    """Drop dates where almost nothing traded (partial/future bars) and rows with non-positive prices."""
    ok = (C > 0) & (H >= L) & (V > 0)
    O, H, L, C, V = [x.where(ok) for x in (O, H, L, C, V)]
    cover = C.notna().sum(axis=1)
    keep = cover >= 0.5 * cover.max()
    return [x[keep] for x in (O, H, L, C, V)]
