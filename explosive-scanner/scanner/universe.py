"""US common-stock universe from the Nasdaq Trader symbol directory (free, official)."""
import io, re, requests, pandas as pd
URLS = ['https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt',
        'https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt']
BAD = re.compile(r'warrant|right|unit|preferred|depositary|\bnotes?\b|\betf\b|\betn\b|\bfund\b|\btrust\b|acquisition|spac|'
                 r'beneficial interest|limited partner|ordinary shares? \(|subordinate', re.I)
def _read(url):
    t = requests.get(url, timeout=60, headers={'User-Agent': 'explosive-scanner/1.0'}).text
    lines = [l for l in t.splitlines() if not l.startswith('File Creation')]
    return pd.read_csv(io.StringIO('\n'.join(lines)), sep='|', dtype=str)
def load_universe():
    a = _read(URLS[0]).rename(columns={'Symbol': 'symbol', 'Security Name': 'name'})
    a = a[(a['Test Issue'] == 'N') & (a['ETF'] == 'N')]
    b = _read(URLS[1]).rename(columns={'ACT Symbol': 'symbol', 'Security Name': 'name'})
    b = b[(b['Test Issue'] == 'N') & (b['ETF'] == 'N')]
    u = pd.concat([a[['symbol', 'name']], b[['symbol', 'name']]]).dropna()
    u = u[u.symbol.str.fullmatch(r'[A-Z]{1,5}') & ~u.name.str.contains(BAD)]
    return sorted(u.symbol.unique())
