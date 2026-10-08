"""Fetch Pinhome listing detail pages for coordinates, kelurahan, createdAt and description.
Stores only listing fields needed for price analysis (no agent/owner contact data, no certificate data)."""
import re, json, time, random, glob, requests, threading, queue, os
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
OUT = 'raw/pinhome/detail.jsonl'
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        try: done.add(json.loads(l)['href'])
        except Exception: pass
hrefs = []
seen = set()
for f in sorted(glob.glob('raw/pinhome/list*.jsonl')):
    for l in open(f):
        d = json.loads(l); h = d.get('href')
        if h and h not in seen: seen.add(h); hrefs.append(h)
todo = [h for h in hrefs if h not in done]
print('total', len(hrefs), 'todo', len(todo), flush=True)
q = queue.Queue(); [q.put(h) for h in todo]
lock = threading.Lock(); out = open(OUT, 'a'); cnt = [0]
def worker():
    s = requests.Session(); s.headers['User-Agent'] = UA
    while True:
        try: h = q.get_nowait()
        except queue.Empty: return
        rec = {'href': h}
        for attempt in range(3):
            try:
                r = s.get('https://www.pinhome.id' + h, timeout=40); r.encoding = 'utf-8'
                rec['status'] = r.status_code
                if r.status_code == 200:
                    m = re.search(r'<script id="__UNIT_DETAIL__" type="application/json">(.*?)</script>', r.text, re.S)
                    if m:
                        d = json.loads(m.group(1))
                        rec.update({
                            'id': d.get('id'), 'slug': d.get('slug'), 'title': d.get('title') or d.get('name'),
                            'address': d.get('address'), 'coordinate': d.get('coordinate'),
                            'kecamatan': (d.get('district') or {}).get('title'), 'kelurahan': (d.get('subDistrict') or {}).get('title'),
                            'city': (d.get('city') or {}).get('title'), 'createdAt': d.get('createdAt'),
                            'minPrice': d.get('minPrice'), 'maxPrice': d.get('maxPrice'), 'subPriceStr': d.get('subPriceStr'), 'subPriceUnit': d.get('subPriceUnit'),
                            'surfaceArea': (d.get('specs') or {}).get('surfaceArea'), 'buildingType': d.get('buildingType'), 'propertyType': d.get('propertyType'),
                            'pricingType': next((x.get('value') for x in d.get('specsAndFacilities') or [] if x.get('localeKey') == 'specifications.pricing_type'), None),
                            'specs': [{k: x.get(k) for k in ('localeKey', 'value')} for x in d.get('specsAndFacilities') or [] if 'certificate' not in (x.get('localeKey') or '')],
                            'description': d.get('description'), 'onMarket': d.get('onMarket'), 'status': d.get('status'),
                        })
                    break
                if r.status_code == 404: break
            except Exception as e:
                rec['error'] = str(e)[:100]
            time.sleep(5 * (attempt + 1))
        rec['fetchedAt'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        with lock:
            out.write(json.dumps(rec, ensure_ascii=False) + '\n'); out.flush(); cnt[0] += 1
            if cnt[0] % 100 == 0: print('done', cnt[0], flush=True)
        time.sleep(0.8 + random.random() * 0.8)
ts = [threading.Thread(target=worker) for _ in range(6)]
[t.start() for t in ts]; [t.join() for t in ts]
print('finished', cnt[0], flush=True)
