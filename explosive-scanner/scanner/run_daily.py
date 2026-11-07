"""Daily scan: download -> features -> snapshot -> alert on NEW signal episodes -> update state.
Usage: python -m scanner.run_daily [--asof YYYY-MM-DD] [--dry-run] [--max-symbols N] [--force]"""
import argparse, json, os, sys, datetime as dt, traceback
import numpy as np, pandas as pd
from . import features, universe, data, notify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'state', 'state.json')
SNAPDIR = os.path.join(ROOT, 'data', 'snapshots')
ALERTS = os.path.join(ROOT, 'data', 'alerts.csv')
COOLDOWN = 20          # sessions between alerts on the same symbol (= backtest episode cooldown)
MAX_LISTED = 20
MIN_ELIGIBLE = 1500    # below this the data pull is considered broken
FOOT = 'UNVALIDATED research alert: no screen passed the pre-registered backtest gate (best lift 1.25-1.35x). Not a buy signal. Size accordingly.'

def load_state():
    try: return json.load(open(STATE))
    except Exception: return {'last_asof': None, 'last_alert': {}}
def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, 'w'), indent=1, sort_keys=True)

def new_episodes(snap, dates, state, asof):
    pos = {d: i for i, d in enumerate(dates)}
    cur = pos[asof]
    keep = []
    for sym in snap.index[snap.n_signal > 0]:
        last = state['last_alert'].get(sym)
        if last is not None:
            lp = pos.get(pd.Timestamp(last))
            if lp is not None and cur - lp < COOLDOWN: continue
            if lp is None and (asof - pd.Timestamp(last)).days < 28: continue
        keep.append(sym)
    return snap.loc[keep].sort_values(['n_signal', 'dv50p'], ascending=[False, False])

def fmt(sym, r):
    flags = ' '.join(s for s in features.SIGNAL_SCREENS if r[s])
    return (f"**[{sym}](https://finance.yahoo.com/chart/{sym})** ${r.c:,.2f} · ${r.dv50p/1e6:,.1f}M/day · RS {r.rs*100:.0f} · "
            f"{r.dhi*100:+.0f}% vs 52w high · {r.d200*100:+.0f}% vs SMA200 · `{flags}`")

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--asof'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--force', action='store_true')
    ap.add_argument('--max-symbols', type=int)
    a = ap.parse_args(argv)
    if a.dry_run: os.environ.pop('DISCORD_WEBHOOK_URL', None)
    state = load_state()
    try:
        tickers = universe.load_universe()
        if a.max_symbols: tickers = tickers[:a.max_symbols]
        print('universe', len(tickers))
        start = (dt.date.today() - dt.timedelta(days=620)).isoformat()
        O, H, L, C, V = data.clean(*data.download(tickers, start))
        if a.asof:
            O, H, L, C, V = [x[x.index <= pd.Timestamp(a.asof)] for x in (O, H, L, C, V)]
        asof = C.index[-1]
        print('asof', asof.date(), 'symbols with data', int(C.iloc[-1].notna().sum()))
        if not a.force and state.get('last_asof') == str(asof.date()):
            print('already processed this session; nothing to do'); return 0
        f = features.compute_features(O, H, L, C, V)
        snap = features.snapshot(f, asof)
        print('eligible', len(snap), {s: int(snap[s].sum()) for s in features.ALL_SCREENS})
        if len(snap) < MIN_ELIGIBLE:
            notify.text(f'⚠️ Explosive-Scanner: only {len(snap)} eligible stocks on {asof.date()} (expected 2,500+). Data pull looks broken; no alerts sent.')
            return 1
        os.makedirs(SNAPDIR, exist_ok=True)
        cols = ['c', 'dv50p', 'rs', 'vdec', 'dhi', 'd200', 'sq', 'vrat'] + features.ALL_SCREENS
        out = snap[cols].copy(); out[features.ALL_SCREENS] = out[features.ALL_SCREENS].astype(int)
        out.round(5).to_csv(os.path.join(SNAPDIR, f'{asof.date()}.csv.gz'))
        new = new_episodes(snap, list(C.index), state, asof)
        print('new episodes', len(new))
        if len(new):
            lines = [fmt(s, r) for s, r in new.head(MAX_LISTED).iterrows()]
            more = f'\n…and {len(new) - MAX_LISTED} more in data/alerts.csv' if len(new) > MAX_LISTED else ''
            legend = '\n'.join(f'`{k}` {v}' for k, v in features.SCREEN_TEXT.items() if k in features.SIGNAL_SCREENS)
            notify.embed(f'🔭 Explosive-Scanner · {asof.date()} · {len(new)} new', '\n'.join(lines) + more,
                         footer=FOOT, fields=[{'name': 'Screens', 'value': legend[:1000]}])
            rows = new[['c', 'dv50p', 'rs', 'dhi', 'd200'] + features.SIGNAL_SCREENS].copy()
            rows.insert(0, 'date', str(asof.date())); rows[features.SIGNAL_SCREENS] = rows[features.SIGNAL_SCREENS].astype(int)
            rows.round(4).to_csv(ALERTS, mode='a', header=not os.path.exists(ALERTS))
            for s in new.index: state['last_alert'][s] = str(asof.date())
        else:
            print('no new episodes; staying quiet')
        state['last_asof'] = str(asof.date())
        # prune old cooldown entries
        state['last_alert'] = {k: v for k, v in state['last_alert'].items() if (asof - pd.Timestamp(v)).days < 60}
        if not a.dry_run: save_state(state)
        return 0
    except Exception:
        tb = traceback.format_exc(); print(tb)
        notify.text('❌ Explosive-Scanner crashed:\n```' + tb[-1500:] + '```')
        return 2

if __name__ == '__main__':
    sys.exit(main())
