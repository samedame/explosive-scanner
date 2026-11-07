"""Run: python -m pytest -q   (or python tests/test_core.py)"""
import sys, math, numpy as np, pandas as pd
sys.path.insert(0, '.')
from scanner import features, score

def synth(n=420, seed=1):
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0005, 0.02, size=(n, 3))
    c = 20 * np.exp(np.cumsum(ret, axis=0))
    h = c * (1 + rng.uniform(0, .02, c.shape)); l = c * (1 - rng.uniform(0, .02, c.shape)); o = (h + l) / 2
    v = rng.integers(2e5, 2e6, size=c.shape).astype(float)
    idx = pd.bdate_range('2025-01-01', periods=n); cols = ['AAA', 'BBB', 'CCC']
    return [pd.DataFrame(x, index=idx, columns=cols) for x in (o, h, l, c, v)]

def test_features_match_plain_loops():
    O, H, L, C, V = synth()
    f = features.compute_features(O, H, L, C, V)
    i = len(C) - 1
    for k, s in enumerate(C.columns):
        c = C[s].values; h = H[s].values; v = V[s].values
        assert math.isclose(f['sma50'][s].iloc[i], sum(c[i-49:i+1]) / 50, rel_tol=1e-9)
        assert math.isclose(f['hi252'][s].iloc[i], max(h[i-251:i+1]), rel_tol=1e-12)
        assert math.isclose(f['hi252p'][s].iloc[i], max(h[i-252:i]), rel_tol=1e-12)
        assert math.isclose(f['vrat'][s].iloc[i], v[i] / (sum(v[i-50:i]) / 50), rel_tol=1e-9)
        assert math.isclose(f['dv50p'][s].iloc[i], sum(c[j] * v[j] for j in range(i-50, i)) / 50, rel_tol=1e-9)
        assert math.isclose(f['ret252_21'][s].iloc[i], c[i-21] / c[i-252] - 1, rel_tol=1e-9)
        bbw = [4 * np.std(c[j-19:j+1]) / np.mean(c[j-19:j+1]) for j in range(i-251, i+1)]
        assert math.isclose(f['sq'][s].iloc[i], bbw[-1] / min(bbw), rel_tol=1e-9)

def test_no_lookahead():
    O, H, L, C, V = synth(seed=3)
    full = features.compute_features(O, H, L, C, V)
    cut = 380
    part = features.compute_features(*[x.iloc[:cut + 1] for x in (O, H, L, C, V)])
    for k in ['sma50', 'sq', 'hi252', 'vrat', 'ret252_21', 'vol60', 'dv50p']:
        a = full[k].iloc[cut].values; b = part[k].iloc[cut].values
        assert np.allclose(a, b, equal_nan=True), k

def test_rulex_cases():
    o = np.array([10, 10, 12, 14, 9, 9, 9.]); c = np.array([10, 11, 13, 15, 10, 9, 9.])
    r, held = score.rulex(o, c, 0)        # entry o[1]=10; peak 15 on day 3; day4 close 10<=0.75*15 -> exit next open o[5]=9
    assert abs(r - (9 / 10 - 1)) < 1e-9 and held == 5
    o2 = np.array([10, 10, 10, 10.]); c2 = np.array([10, 10, 11, 12.])
    r, held = score.rulex(o2, c2, 0)      # never stops: last close in data
    assert abs(r - (12 / 10 - 1)) < 1e-9 and held == 3

if __name__ == '__main__':
    test_features_match_plain_loops(); test_no_lookahead(); test_rulex_cases(); print('all tests passed')


def test_catalyst_tags_and_failsoft():
    import numpy as np
    from scanner import catalyst
    t = catalyst.tags({'si_dtc': 8.2, 'si_chg': 12.0, 'days_to_next': 9, 'sur_last': .4, 'days_since_rep_eps': 30,
                       'ins_buys_90d': 2, 'ins_buy_usd_90d': 55000, 'sec_8k_items': '2.02(3d)', 'sec_offering_90d': 1, 'sec_merger_90d': 1})
    assert 'SI 8.2d' in t and 'earnings in 9d' in t and 'last EPS +40%' in t and 'insider buys 2' in t and 'offering' in t and 'MERGER' in t
    assert catalyst.tags({'si_dtc': np.nan, 'days_to_next': np.nan}) == ''          # missing data -> no tag, no crash
    import os; os.environ.pop('SEC_CONTACT', None)
    assert catalyst.sec_context('AAPL', '2026-11-06') is None                       # no contact -> unavailable, never a false "no filings"


def test_confidence_score_rules():
    from scanner import confidence as C
    base = dict(c=20.0, dv50p=3e7, n_signal=1)
    r = C.score_alert(base); assert r['score'] == 100 and r['tier'] == 'A' and r['setup_scored'] is False
    # setup weight is frozen at 0: more screens must not change the score
    assert C.score_alert({**base, 'n_signal': 4})['score'] == r['score']
    # execution falls with liquidity and with a sub-$5 price
    assert C.score_alert({**base, 'dv50p': 3e6})['score'] < C.score_alert({**base, 'dv50p': 6e6})['score'] < r['score']
    assert C.score_alert({**base, 'c': 3.5})['score'] < r['score']
    # caps: stale data -> tier D, merger/tender -> at most tier C
    assert C.score_alert(base, fresh=False)['tier'] == 'D' and C.score_alert(base, fresh=False)['score'] <= 49
    m = C.score_alert(base, merger=True); assert m['score'] == 69 and m['tier'] == 'C' and m['warnings']
    # offering / equity sale are warnings without a cap
    assert C.score_alert(base, offering=True, equity_sale=True)['score'] == 100
    # odds line uses the multi-screen bucket for n>=2 and mentions the recent regime
    assert 'Odds:' in C.line(C.score_alert({**base, 'n_signal': 2})) and C.score_alert({**base, 'n_signal': 2})['odds_p'] > r['odds_p']


def test_embeds_are_chunked_not_truncated(monkeypatch):
    from scanner import notify
    sent = []
    monkeypatch.setattr(notify, 'embed', lambda title, d, **k: sent.append((title, d)) or True)
    notify.embeds_chunked('T', ['x' * 900] * 10, more='more')
    assert len(sent) >= 3 and all(len(d) <= 3900 for _, d in sent) and sum(d.count('x') for _, d in sent) == 9000
    assert sent[-1][1].endswith('more')
