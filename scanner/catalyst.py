"""Live catalyst context (all free, point-in-time sources).
 - FINRA short interest (bi-monthly): days-to-cover and change, applied to every eligible stock
 - Dolt earnings calendar + EPS history: next report date, last EPS surprise, applied to every eligible stock
 - SEC EDGAR: recent 8-K items, 13D/G, offering and merger filings, and Form 4 open-market insider trades, for ALERTED names only
Every fetch fails soft: missing data just means a missing tag."""
import datetime as dt, io, re, threading, time, xml.etree.ElementTree as ET
import numpy as np, pandas as pd, requests

import os
def _ua():
    # SEC fair-access policy needs a declared contact. Set repo variable/secret SEC_CONTACT (your email); without it SEC lookups are skipped.
    c = os.environ.get('SEC_CONTACT', '').strip()
    return {'User-Agent': f'ExplosiveScanner research contact {c}', 'Accept-Encoding': 'gzip'} if c else None
UA = {'User-Agent': 'ExplosiveScanner research', 'Accept-Encoding': 'gzip'}   # FINRA / Dolt
DOLT = 'https://www.dolthub.com/api/v1alpha1/post-no-preference/earnings/master'
_lock = threading.Lock(); _last = [0.0]

def _sec_get(url, as_json=True):
    h = _ua()
    if h is None: return None
    for a in range(3):
        with _lock:
            w = 0.12 - (time.time() - _last[0])
            if w > 0: time.sleep(w)
            _last[0] = time.time()
        try:
            r = requests.get(url, headers=h, timeout=45)
            if r.status_code == 200: return r.json() if as_json else r.content
            if r.status_code == 404: return None
        except Exception: pass
        time.sleep(2 * (a + 1))
    return None

# ---------------------------------------------------------------- short interest
def short_interest(asof):
    """Latest FINRA file whose publication (settlement + 11 days) is <= asof. Returns DataFrame indexed by symbol."""
    asof = pd.Timestamp(asof).date()
    cands = []
    for back in range(0, 50):
        d = asof - dt.timedelta(days=back)
        if d.weekday() < 5: cands.append(d)
    for d in cands:
        if (asof - d).days < 11: continue            # not yet published point-in-time
        try:
            r = requests.get(f'https://cdn.finra.org/equity/otcmarket/biweekly/shrt{d:%Y%m%d}.csv', headers=UA, timeout=60)
        except Exception: continue
        if r.status_code == 200 and len(r.content) > 10000:
            x = pd.read_csv(io.StringIO(r.text), sep='|')
            x = x.rename(columns={'symbolCode': 'symbol', 'daysToCoverQuantity': 'si_dtc', 'changePercent': 'si_chg', 'settlementDate': 'si_settle'})
            x = x.drop_duplicates('symbol').set_index('symbol')[['si_dtc', 'si_chg', 'si_settle']]
            return x
    return pd.DataFrame(columns=['si_dtc', 'si_chg', 'si_settle'])

# ---------------------------------------------------------------- earnings (Dolt)
def _dolt(sql, tries=4):
    for a in range(tries):
        try:
            d = requests.get(DOLT, params={'q': sql}, timeout=90).json()
            if d.get('query_execution_status') == 'Success': return d['rows']
        except Exception: pass
        time.sleep(2 * (a + 1))
    return []

def _paged(base, order, chunk=1000, maxpages=40):
    out = []
    for p in range(maxpages):
        rows = _dolt(f'{base} order by {order} limit {chunk} offset {p * chunk}')
        out += rows
        if len(rows) < chunk: break
    return out

def earnings_table(asof):
    """Per symbol: days to next report (calendar), days since last report, last EPS surprise (PIT: reports on/before asof)."""
    asof = pd.Timestamp(asof)
    a, b = (asof - pd.Timedelta(days=200)).date(), (asof + pd.Timedelta(days=100)).date()
    cal = pd.DataFrame(_paged(f"select act_symbol,date from earnings_calendar where date between '{a}' and '{b}'", 'act_symbol,date'))
    eps = pd.DataFrame(_paged(f"select act_symbol,period_end_date,reported,estimate from eps_history where period_end_date between '{(asof - pd.Timedelta(days=260)).date()}' and '{asof.date()}'", 'act_symbol,period_end_date'))
    if cal.empty: return pd.DataFrame(columns=['days_to_next', 'days_since_rep', 'sur_last'])
    cal['date'] = pd.to_datetime(cal['date']); cal = cal.rename(columns={'act_symbol': 'symbol'})
    out = pd.DataFrame(index=sorted(cal.symbol.unique())); out.index.name = 'symbol'
    nxt = cal[cal.date > asof].groupby('symbol').date.min(); out['days_to_next'] = (nxt - asof).dt.days
    past = cal[cal.date <= asof].groupby('symbol').date.max(); out['days_since_rep'] = (asof - past).dt.days
    if not eps.empty:
        eps['period_end_date'] = pd.to_datetime(eps.period_end_date); eps = eps.rename(columns={'act_symbol': 'symbol'})
        eps['reported'] = pd.to_numeric(eps.reported); eps['estimate'] = pd.to_numeric(eps.estimate)
        m = eps.merge(cal, on='symbol'); m = m[(m.date > m.period_end_date + pd.Timedelta(days=5)) & (m.date <= m.period_end_date + pd.Timedelta(days=130)) & (m.date <= asof)]
        rep = m.sort_values('date').groupby(['symbol', 'period_end_date'], as_index=False).first().sort_values(['symbol', 'date'])
        rep['sur'] = ((rep.reported - rep.estimate) / np.maximum(rep.estimate.abs(), 0.10)).clip(-5, 5)
        last = rep.groupby('symbol').tail(1).set_index('symbol')
        out['sur_last'] = last.sur; out['days_since_rep_eps'] = (asof - last.date).dt.days
    return out

# ---------------------------------------------------------------- SEC (alerted names only)
_cik_map = {}
def cik_for(symbol):
    if not _cik_map:
        j = _sec_get('https://www.sec.gov/files/company_tickers.json') or {}
        for v in j.values(): _cik_map[v['ticker'].upper()] = str(int(v['cik_str'])).zfill(10)
    return _cik_map.get(symbol)

def _form4_trades(cik, sub, asof, days=90, max_filings=12):
    f = sub['filings']['recent']; out = []
    cutoff = (asof - pd.Timedelta(days=days)).strftime('%Y-%m-%d'); n = 0
    for i, form in enumerate(f['form']):
        if form != '4' or f['filingDate'][i] < cutoff or f['filingDate'][i] > asof.strftime('%Y-%m-%d'): continue
        n += 1
        if n > max_filings: break
        acc = f['accessionNumber'][i].replace('-', ''); doc = re.sub(r'^xsl[^/]*/', '', f['primaryDocument'][i])
        raw = _sec_get(f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}', as_json=False)
        if not raw: continue
        try:
            root = ET.fromstring(raw)
            rel = root.find('.//reportingOwnerRelationship'); isoff = False
            if rel is not None: isoff = any((rel.findtext(t) or '0').strip() in ('1', 'true') for t in ('isOfficer', 'isDirector'))
            for t in root.findall('.//nonDerivativeTransaction'):
                code = t.findtext('.//transactionCode'); sh = float(t.findtext('.//transactionShares/value') or 0); px = float(t.findtext('.//transactionPricePerShare/value') or 0)
                if code in ('P', 'S'): out.append((f['filingDate'][i], code, sh * px, isoff))
        except Exception: continue
    return out

def sec_context(symbol, asof):
    asof = pd.Timestamp(asof)
    if _ua() is None: return None
    cik = cik_for(symbol)
    res = {'sec_8k_items': '', 'sec_8k_30d': 0, 'sec_13d_90d': 0, 'sec_offering_90d': 0, 'sec_merger_90d': 0, 'ins_buys_90d': 0, 'ins_buy_usd_90d': 0.0, 'ins_sells_90d': 0}
    if not cik: return None            # unknown / unavailable: caller shows no SEC tags (never a false 'no filings')
    sub = _sec_get(f'https://data.sec.gov/submissions/CIK{cik}.json')
    if not sub: return None
    f = sub['filings']['recent']; items = {}
    for i, form in enumerate(f['form']):
        fd = f['filingDate'][i]; age = (asof - pd.Timestamp(fd)).days
        if age < 0: continue
        if form.startswith('8-K') and age <= 30:
            res['sec_8k_30d'] += 1
            for it in (f['items'][i] or '').split(','):
                if it.strip(): items[it.strip()] = min(items.get(it.strip(), 99), age)
        if ('13D' in form or '13G' in form) and age <= 90: res['sec_13d_90d'] += 1
        if re.match(r'^(S-1|S-3|F-1|F-3|424B)', form) and age <= 90: res['sec_offering_90d'] += 1
        if re.match(r'^(SC TO|DEFM14A|PREM14A)', form) and age <= 90: res['sec_merger_90d'] += 1
    res['sec_8k_items'] = ' '.join(f'{k}({v}d)' for k, v in sorted(items.items(), key=lambda kv: kv[1])[:5])
    tr = _form4_trades(cik, sub, asof)
    buys = [t for t in tr if t[1] == 'P' and t[3] and t[2] >= 10000]
    res['ins_buys_90d'] = len(buys); res['ins_buy_usd_90d'] = float(sum(t[2] for t in buys)); res['ins_sells_90d'] = sum(1 for t in tr if t[1] == 'S' and t[2] >= 50000)
    return res

def tags(r):
    """Compact human-readable context line from a row with the fields above (missing fields are skipped)."""
    out = []
    g = lambda k: r.get(k) if hasattr(r, 'get') else None
    v = g('si_dtc')
    if v is not None and pd.notna(v): out.append(f"SI {v:.1f}d to cover" + (f" ({g('si_chg'):+.0f}%)" if pd.notna(g('si_chg')) else ''))
    v = g('days_to_next')
    if v is not None and pd.notna(v): out.append(f"earnings in {int(v)}d")
    v = g('sur_last')
    if v is not None and pd.notna(v) and pd.notna(g('days_since_rep_eps')) and g('days_since_rep_eps') <= 90: out.append(f"last EPS {v*100:+.0f}% vs est ({int(g('days_since_rep_eps'))}d ago)")
    if (g('ins_buys_90d') or 0) > 0: out.append(f"insider buys {int(g('ins_buys_90d'))} (${g('ins_buy_usd_90d')/1e3:,.0f}k/90d)")
    if (g('ins_sells_90d') or 0) >= 3: out.append(f"insider sells {int(g('ins_sells_90d'))}")
    if g('sec_8k_items'): out.append('8-K ' + g('sec_8k_items'))
    if (g('sec_13d_90d') or 0) > 0: out.append('13D/G filed')
    if (g('sec_offering_90d') or 0) > 0: out.append('⚠ offering filing')
    if (g('sec_merger_90d') or 0) > 0: out.append('⚠ merger/tender filing')
    return ' · '.join(out)
