"""Parse saved Lamudi search pages (gz HTML) → JSONL of listings (JSON-LD + card map coordinates)."""
import re, json, gzip, glob, html, datetime, sys
out = open(sys.argv[2] if len(sys.argv) > 2 else 'raw/lamudi/listings.jsonl', 'w')
seen = set(); n = 0
for f in sorted(glob.glob((sys.argv[1] if len(sys.argv) > 1 else 'raw/lamudi/semarang') + '/page-*.html.gz')):
    h = gzip.open(f, 'rt').read()
    scraped = datetime.datetime.fromtimestamp(__import__('os').path.getmtime(f)).strftime('%Y-%m-%dT%H:%M:%S')
    items = {}
    def walk(o):
        if isinstance(o, dict):
            if o.get('@type') == 'RealEstateListing': items[o.get('url') or o.get('@id')] = o
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', h, re.S):
        try: walk(json.loads(m.group(1)))
        except Exception: pass
    # card attributes: uuid + alternate id + map coords
    cards = {}
    for m in re.finditer(r'data-idanuncio="([0-9a-f-]+)"\s+data-alternateid="([^"]+)"\s+data-serp-map-hover-listing="([^"]+)"', h):
        uuid, alt, geo = m.group(1), m.group(2), json.loads(html.unescape(m.group(3)))
        cards[alt] = {'uuid': uuid, 'map': geo}
    # price text in card (for 'per m2' detection)
    for url, it in items.items():
        alt = url.rstrip('/').split('/')[-1]
        if alt in seen: continue
        seen.add(alt)
        c = cards.get(alt, {})
        uuid = c.get('uuid')
        created = None
        if uuid and uuid.replace('-', '')[12] == '7':
            ms = int(uuid.replace('-', '')[:12], 16)
            created = datetime.datetime.fromtimestamp(ms / 1000, datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
        geo = it.get('geo') or {}
        rec = {
            'id': alt, 'uuid': uuid, 'url': url, 'title': it.get('name'), 'description': it.get('description'),
            'address': (it.get('address') or {}).get('streetAddress'),
            'locality': (it.get('address') or {}).get('addressLocality'),
            'area_m2': float(it['floorSize']['value']) if (it.get('floorSize') or {}).get('value') else None,
            'price': float(it['offers']['price']) if (it.get('offers') or {}).get('price') else None,
            'ld_geo': [float(geo['latitude']), float(geo['longitude'])] if geo.get('latitude') else None,
            'map_geo': [c['map']['latitude'], c['map']['longitude']] if c.get('map') and c['map'].get('latitude') else None,
            'map_exact': (c.get('map') or {}).get('exactLocation'),
            'createdAt': created, 'page': f.split('/')[-1], 'scrapedAt': scraped,
        }
        out.write(json.dumps(rec, ensure_ascii=False) + '\n'); n += 1
print('listings', n)
