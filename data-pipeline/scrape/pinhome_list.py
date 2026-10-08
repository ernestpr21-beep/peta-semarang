"""Scrape Pinhome 'Tanah dijual di Kota Semarang' search result pages (public HTML).
Stores only listing-level fields (no agent contact data)."""
import re, html, json, time, random, sys, requests
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
KEC = sys.argv[1]
BASE = "https://www.pinhome.id/jual/tanah/jawa-tengah/semarang/" + KEC
out = open('raw/pinhome/list-kec.jsonl', 'a')
s = requests.Session(); s.headers['User-Agent'] = UA
def unwrap(v):
    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
        t, x = v
        if t == 0: return unwrap(x) if isinstance(x, (dict, list)) else x
        if t == 1: return [unwrap(i) for i in x]
        return x
    if isinstance(v, dict): return {k: unwrap(x) for k, x in v.items()}
    if isinstance(v, list): return [unwrap(i) for i in v]
    return v
start = 1
total_pages = None
page = start
while True:
    url = BASE if page == 1 else f"{BASE}?page={page}"
    for attempt in range(4):
        try:
            r = s.get(url, timeout=40)
            if r.status_code == 200: break
            print('status', r.status_code, page, flush=True)
        except Exception as e:
            print('err', e, flush=True)
        time.sleep(10 * (attempt + 1))
    h = r.text
    m = re.search(r'dari\s+([\d.]+)', h)
    if m and total_pages is None:
        total = int(m.group(1).replace('.', '')); total_pages = (total + 39) // 40
        print('total listings', total, 'pages', total_pages, flush=True)
    n = 0
    for p in re.findall(r'<astro-island[^>]*?props="([^"]*)"', h):
        try: u = unwrap(json.loads(html.unescape(p)))
        except Exception: continue
        pd = u.get('propertyData') if isinstance(u, dict) else None
        if not pd: continue
        for k in ('images', 'agentsData', 'wishlistGUID'): pd.pop(k, None)
        pd['_page'] = page; pd['_kecSlug'] = KEC; pd['_scrapedAt'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        out.write(json.dumps(pd, ensure_ascii=False) + '\n'); n += 1
    out.flush()
    print('page', page, 'items', n, flush=True)
    if n == 0 or (total_pages and page >= total_pages): break
    page += 1
    time.sleep(1.5 + random.random())
