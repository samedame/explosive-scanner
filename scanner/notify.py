import os, requests
def send(payload, webhook=None):
    url = webhook or os.environ.get('DISCORD_WEBHOOK_URL')
    if not url:
        print('[no DISCORD_WEBHOOK_URL set - printing instead]'); print(payload.get('content') or payload.get('embeds')); return False
    r = requests.post(url, json=payload, timeout=30)
    if r.status_code >= 300: print('discord error', r.status_code, r.text[:200])
    return r.status_code < 300
def text(msg): return send({'content': msg[:1900]})
def embed(title, description, color=0x2B7FFF, footer=None, fields=None):
    e = {'title': title[:250], 'description': description[:4000], 'color': color}
    if footer: e['footer'] = {'text': footer[:2000]}
    if fields: e['fields'] = fields
    return send({'embeds': [e]})

def embeds_chunked(title, blocks, more='', footer=None, fields=None, limit=3800):
    """Discord truncates embed descriptions at 4096 chars; split alert blocks across several embeds so none is silently cut."""
    chunks, cur = [], ''
    for b in blocks:
        if cur and len(cur) + len(b) + 2 > limit: chunks.append(cur); cur = ''
        cur += ('\n\n' if cur else '') + b
    if more: cur += ('\n\n' if cur else '') + more
    if cur: chunks.append(cur)
    ok = True
    for i, c in enumerate(chunks):
        last = i == len(chunks) - 1
        ok &= embed(title + (f' ({i + 1}/{len(chunks)})' if len(chunks) > 1 else ''), c, footer=footer if last else None, fields=fields if i == 0 else None)
    return ok
