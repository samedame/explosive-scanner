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
