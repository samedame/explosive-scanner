"""Forward scorer: turns the daily snapshots into the out-of-sample test the backtest could not provide.
For every snapshot at least 100 calendar days old: outcome of each flagged name vs same-date, same-volatility-decile controls.
Outcome = max close over the 63 sessions after next-open entry (E50 >= +50%, E100 >= +100%) and Rule X trade return.
Usage: python -m scanner.score"""
import glob, json, os, sys, datetime as dt
import numpy as np, pandas as pd
from . import features, data, notify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPDIR = os.path.join(ROOT, 'data', 'snapshots'); OUT = os.path.join(ROOT, 'data', 'outcomes.csv.gz')
CARD = os.path.join(ROOT, 'data', 'scorecard.md'); DONE = os.path.join(ROOT, 'state', 'scored.json')
HORIZON, MIN_AGE, COOLDOWN = 63, 100, 20

def cost2(dv, c):
    return np.where(dv >= 2e7, .001, np.where(dv >= 5e6, .0025, .006)) + np.where(c < 5, .003, 0.)

def rulex(o, c, p0, trail=0.75, cap=HORIZON):
    """o,c arrays for one symbol; signal row index p0. Returns (return, held) or None. Same rule as the backtest."""
    if p0 + 1 >= len(o): return None
    entry = o[p0 + 1]; peak = entry; last = None; lastj = 0
    for j in range(1, cap + 1):
        p = p0 + j
        if p >= len(c): break
        cj = c[p]; peak = max(peak, cj); last = cj; lastj = j
        if cj <= trail * peak and j < cap:
            return ((o[p + 1] if p + 1 < len(o) else cj) / entry - 1), j + 1
    return (last / entry - 1, lastj) if last is not None else None

def outcomes_for(snap, O, C, date, idx):
    """snap: snapshot DataFrame; O,C: wide price frames."""
    p0 = idx.get_loc(date) if date in idx else idx.searchsorted(date) - 1
    if p0 + HORIZON >= len(idx): return None            # horizon not complete yet
    rows = []
    for sym, r in snap.iterrows():
        if sym not in C.columns: continue
        o = O[sym].values; c = C[sym].values
        entry = o[p0 + 1]
        if not np.isfinite(entry) or entry <= 0: continue
        w = c[p0 + 1:p0 + 1 + HORIZON]
        w = w[np.isfinite(w)]
        if len(w) < HORIZON - 3: continue
        mx = w.max() / entry - 1
        oo = o[p0:p0 + HORIZON + 3]; cc = c[p0:p0 + HORIZON + 3]
        ok = np.isfinite(oo) & np.isfinite(cc); ok[0] = True      # compact to the symbol's own sessions (as the backtest does)
        rx = rulex(oo[ok], cc[ok], 0)
        rows.append((sym, mx, rx[0] if rx else np.nan))
    if not rows: return None
    d = pd.DataFrame(rows, columns=['symbol', 'mx', 'xr']).set_index('symbol')
    d = snap.join(d, how='inner')
    d['e50'] = (d.mx >= .5).astype(float); d['e100'] = (d.mx >= 1.0).astype(float)
    d['cost'] = cost2(d.dv50p.values, d.c.values); d['xnet'] = d.xr - 2 * d.cost
    for k in ['e50', 'e100', 'xnet']:
        d['c_' + k] = d.groupby('vdec')[k].transform('mean')
    d.insert(0, 'date', date); return d.reset_index()

def boot_ratio(num, den, g, B=2000, seed=20261106):
    t = pd.DataFrame({'a': num, 'b': den, 'g': g}).groupby('g').sum()
    rng = np.random.default_rng(seed); idx = rng.integers(0, len(t), size=(B, len(t)))
    r = t.a.values[idx].sum(1) / t.b.values[idx].sum(1)
    return np.nanpercentile(r, [5, 95])

def scorecard(allrows):
    snaps = sorted(allrows.date.unique())
    lines = ['# Forward scorecard', f'_updated {dt.date.today()} · snapshots scored: {len(snaps)} ({snaps[0][:10]} to {snaps[-1][:10]})_', '',
             '| Screen | Episodes | P(E50) | Control | Lift L50 | 90% CI | Net excess/trade | Verdict vs gate |', '|---|---|---|---|---|---|---|---|']
    for s in features.ALL_SCREENS:
        x = allrows[allrows[s] == 1].sort_values(['symbol', 'date'])
        # episodes: first flag after >= COOLDOWN snapshots of not being flagged (by snapshot index)
        idx = {d: i for i, d in enumerate(snaps)}; x = x.assign(i=x.date.map(idx))
        prev = x.groupby('symbol').i.shift(1); ep = x[prev.isna() | ((x.i - prev) > COOLDOWN)]
        n = len(ep)
        if n < 10: lines.append(f'| {s} | {n} | – | – | – | – | – | too few |'); continue
        ym = pd.to_datetime(ep.date).dt.to_period('M').astype(str)
        L = ep.e50.sum() / ep.c_e50.sum(); lo, hi = boot_ratio(ep.e50.values, ep.c_e50.values, ym.values)
        ex = (ep.xnet - ep.c_xnet).mean()
        ok = n >= 150 and L >= 1.3 and lo > 1.0 and ex > 0
        lines.append(f'| {s} | {n} | {ep.e50.mean():.3f} | {ep.c_e50.mean():.3f} | {L:.2f} | {lo:.2f}–{hi:.2f} | {ex*100:+.2f}% | ' +
                     ('**PASSES forward gate**' if ok else ('no (needs n>=150, L50>=1.3, CI low>1, excess>0)')) + ' |')
    lines += ['', 'Forward gate (suggested, mirrors the backtest bars): n>=150 episodes, L50>=1.3 with month-bootstrap 90% CI low >1, mean net excess >0.',
              'Controls are same-date, same-volatility-decile stocks from the eligible snapshot; costs 10/25/60bp (+30bp under $5), doubled round-trip.']
    return '\n'.join(lines)

def main():
    done = json.load(open(DONE)) if os.path.exists(DONE) else []
    files = sorted(glob.glob(os.path.join(SNAPDIR, '*.csv.gz')))
    today = dt.date.today()
    due = [f for f in files if os.path.basename(f)[:10] not in done and (today - dt.date.fromisoformat(os.path.basename(f)[:10])).days >= MIN_AGE]
    if due:
        syms = sorted(set().union(*[set(pd.read_csv(f, index_col=0).index) for f in due]))
        start = (pd.Timestamp(os.path.basename(due[0])[:10]) - pd.Timedelta(days=7)).date().isoformat()
        O, H, L, C, V = data.clean(*data.download(syms, start)); idx = C.index
        new = []
        for f in due:
            d = os.path.basename(f)[:10]
            r = outcomes_for(pd.read_csv(f, index_col=0), O, C, pd.Timestamp(d), idx)
            if r is not None: r['date'] = d; new.append(r); done.append(d)
        if new:
            old = pd.read_csv(OUT) if os.path.exists(OUT) else pd.DataFrame()
            pd.concat([old] + new, ignore_index=True).to_csv(OUT, index=False)
            os.makedirs(os.path.dirname(DONE), exist_ok=True); json.dump(sorted(done), open(DONE, 'w'))
    if not os.path.exists(OUT):
        print('no scorable snapshots yet (need >=100 days of history)'); return 0
    card = scorecard(pd.read_csv(OUT)); open(CARD, 'w').write(card); print(card)
    notify.embed('📊 Explosive-Scanner forward scorecard', card[:3900], color=0x888888)
    return 0
if __name__ == '__main__': sys.exit(main())
