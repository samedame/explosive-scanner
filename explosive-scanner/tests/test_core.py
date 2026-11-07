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
