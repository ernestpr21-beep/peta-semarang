"""3. Kualitas data: pencilan per kelurahan, salah baca harga (total vs per m²), rumah/bangunan, kavling paket/cicilan,
harga per are/ru, duplikat lintas portal dengan pin berbeda, efek sumber & umur iklan. Memakai bias LOO dari error_map.py."""
import csv, json, math, os, re, statistics, sys
from collections import defaultdict, Counter
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import ROOT, AUDIT_OUT, KX, KY, mdae
csv.field_size_limit(10 ** 9)
allr = {f"{r['source']}:{r['source_id']}": r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_all.csv')))}
model = [r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv')))]
loo = {p['id']: p for p in json.load(open(os.path.join(AUDIT_OUT, 'loo_points.json')))}
for r in model:
    r['id'] = f"{r['source']}:{r['source_id']}"; a = allr.get(r['id'], {})
    r['text'] = ((a.get('title') or '') + ' \n ' + (a.get('description') or '')).lower(); r['title'] = (a.get('title') or '').lower()
    r['price'] = float(a.get('price') or 0); r['price_is_ppm'] = a.get('price_is_ppm') == 'True'
    for k in ('ppm', 'pn', 'area_m2', 'lat', 'lng'): r[k] = float(r[k])
PAT = {
    'rumah/bangunan disebut': r'\b(rumah|bangunan|kamar tidur|\bkt\b|\bkm\b|kost|kos-kosan|ruko|gudang|pabrik|villa|gedung)\b',
    'kavling developer/cicilan': r'\b(cicil|angsur|kpr|dp\s|uang muka|mulai|start from|promo|launching|booking fee|free shm|free biaya|bebas biaya|tanpa bunga)\b',
    'harga per are/ru/tumbak': r'(per\s*are\b|/\s*are\b|per\s*ru\b|/\s*ru\b|tumbak|per\s*bata)',
    'harga nego/BU': r'\b(bu\b|butuh uang|cepat|murah|di bawah harga|dibawah harga|bawah njop|harga miring)\b',
    'tanah sawah/kebun/tegalan': r'\b(sawah|kebun|tegalan|tegal|perkebunan|ladang)\b',
    'hook/pojok': r'\b(hook|pojok)\b',
    'pinggir jalan raya disebut': r'\b(pinggir jalan raya|tepi jalan raya|pinggir jalan besar|jalan provinsi|jalan nasional|jalan utama)\b',
}
res = {'patterns': {}}
for name, pat in PAT.items():
    rx = re.compile(pat)
    hit = [r for r in model if rx.search(r['text'])]
    b = np.array([loo[r['id']]['b'] for r in hit if r['id'] in loo])
    rest = np.array([loo[r['id']]['b'] for r in model if r['id'] in loo and not rx.search(r['text'])])
    res['patterns'][name] = {'n': len(hit), 'nLoo': len(b), 'meanBiasLoo': round(float(b.mean()), 3) if len(b) else None, 'medianBiasLoo': round(float(np.median(b)), 3) if len(b) else None,
                             'restMeanBias': round(float(rest.mean()), 3), 'mdae': mdae(b) if len(b) else None,
                             't': round(float((b.mean() - rest.mean()) / math.sqrt(b.var(ddof=1) / len(b) + rest.var(ddof=1) / len(rest))), 2) if len(b) > 5 else None}
# pencilan per kelurahan (median & MAD log pn, kelurahan ≥ 6) — aturan sekarang |z|>3; berapa yang 2,5<|z|≤3 dan biasnya
by = defaultdict(list)
for r in model:
    if r['loc_level'] != 'kecamatan': by[r['kelurahan']].append(r)
zs = []
for k, rs in by.items():
    if len(rs) < 6: continue
    lv = np.log([x['pn'] for x in rs]); med = np.median(lv); mad = 1.4826 * np.median(np.abs(lv - med)) or 0.3
    for x, l in zip(rs, lv): x['z'] = (l - med) / mad; zs.append(x)
res['kelurahanZ'] = {'n': len(zs), 'abs_z_gt2': sum(1 for x in zs if abs(x['z']) > 2), 'abs_z_gt2_5': sum(1 for x in zs if abs(x['z']) > 2.5),
                     'high_z_gt2_5': sum(1 for x in zs if x['z'] > 2.5), 'low_z_lt_-2_5': sum(1 for x in zs if x['z'] < -2.5)}
# salah baca harga: harga total sangat kecil / per m² mencurigakan
sus = []
for r in model:
    tot = r['ppm'] * r['area_m2']
    why = []
    if tot < 30e6: why.append(f'total hanya Rp{tot/1e6:.0f} jt')
    if r['price_is_ppm'] and r['ppm'] < 300e3: why.append('dibaca per m² tapi < Rp300 rb')
    if not r['price_is_ppm'] and r['area_m2'] >= 1000 and re.search(r'/\s*m2|per\s*m|/meter|per\s*meter', r['title']): why.append('judul menyebut per m² tetapi dibaca total')
    if r.get('z') is not None and abs(r['z']) > 2.5: why.append(f'z={r["z"]:.1f} di kelurahannya')
    if why:
        sus.append({'id': r['id'], 'kel': r['kelurahan'], 'kec': r['kecamatan'], 'area': r['area_m2'], 'ppmJt': round(r['ppm'] / 1e6, 2), 'priceJt': round(r['price'] / 1e6, 1), 'isPpm': r['price_is_ppm'], 'why': why,
                    'b': loo.get(r['id'], {}).get('b'), 'title': r['title'][:90]})
res['suspicious'] = {'n': len(sus), 'byReason': dict(Counter(w.split(' ')[0] for s in sus for w in s['why'])), 'examples': sorted(sus, key=lambda s: -abs(s['b'] or 0))[:40]}
# duplikat lintas portal: luas sama & harga ±2% & kecamatan sama, pin berbeda > 300 m
dups = []
idx = defaultdict(list)
for r in model: idx[(r['kecamatan'], round(r['area_m2']))].append(r)
for k, rs in idx.items():
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)):
            a, b = rs[i], rs[j]
            if a['source'] == b['source']: continue
            if abs(a['ppm'] / b['ppm'] - 1) > 0.02: continue
            d = math.hypot((a['lat'] - b['lat']) * KY, (a['lng'] - b['lng']) * KX)
            dups.append({'a': a['id'], 'b': b['id'], 'kec': k[0], 'area': k[1], 'ppmJt': round(a['ppm'] / 1e6, 2), 'distM': round(d), 'locA': a['loc_level'], 'locB': b['loc_level']})
res['crossPortalDuplicates'] = {'n': len(dups), 'nPinApartOver300m': sum(1 for d in dups if d['distM'] > 300), 'examples': sorted(dups, key=lambda d: -d['distM'])[:15]}
# klaster agen: banyak iklan dengan koordinat hampir sama (≤ 30 m) & luas berbeda → satu proyek kavling
cl = defaultdict(list)
for r in model:
    if r['loc_level'] == 'titik': cl[(round(r['lat'] * 3000), round(r['lng'] * 3000))].append(r)
big = sorted(((len(v), k, v) for k, v in cl.items() if len(v) >= 5), reverse=True)
res['pinClusters'] = {'nClustersGe5': len(big), 'nListingsInThem': sum(n for n, _, _ in big),
                      'top': [{'n': n, 'kel': v[0]['kelurahan'], 'lat': v[0]['lat'], 'lng': v[0]['lng'], 'medianPpmJt': round(statistics.median(x['ppm'] for x in v) / 1e6, 2),
                               'sources': dict(Counter(x['source'] for x in v))} for n, _, v in big[:12]]}
json.dump(res, open(os.path.join(AUDIT_OUT, 'data_quality.json'), 'w'), indent=1, ensure_ascii=False)
print(json.dumps({k: v for k, v in res.items() if k not in ('suspicious', 'crossPortalDuplicates', 'pinClusters')}, ensure_ascii=False, indent=1))
print('suspicious', res['suspicious']['n'], res['suspicious']['byReason'])
for s in res['suspicious']['examples'][:12]: print('  ', s)
print('dups', res['crossPortalDuplicates']['n'], res['crossPortalDuplicates']['nPinApartOver300m'])
print('pinClusters', res['pinClusters']['nClustersGe5'], res['pinClusters']['nListingsInThem']); [print('  ', t) for t in res['pinClusters']['top'][:8]]
