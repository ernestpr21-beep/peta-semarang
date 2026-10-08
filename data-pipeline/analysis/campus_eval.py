"""Analisis: kedekatan kampus & kualitas lokasi iklan, dan validasi leave-one-out varian estimator.
Jalankan setelah build_app_data.py (butuh data/listings_model.csv)."""
import csv, json, math, os, re, statistics, sys
from collections import Counter, defaultdict
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import transform, unary_union
from pyproj import Transformer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tf = Transformer.from_crs('EPSG:4326', 'EPSG:32749', always_xy=True).transform
camp = json.load(open(os.path.join(ROOT, 'data/campus.json')))['campuses']

def campus_set(min_ha=2.0):
    out = []
    for c in camp:
        if c['areaHa'] < min_ha or 'kepolisian' in c['name'].lower():
            continue
        polys = [Polygon([(lng, lat) for lat, lng in r]) for r in c['rings'] if len(r) >= 4]
        out.append((c['name'], transform(tf, unary_union(polys))))
    return out

rows = list(csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv'))))
meta = {r['source'] + r['source_id']: r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_all.csv')))}
KEC = set(r['kecamatan'] for r in rows)
for r in rows:
    for k in ('lat', 'lng', 'ppm', 'pn', 'area_m2'): r[k] = float(r[k])
    r['exact'] = int(r['exact'])
    m = meta[r['source'] + r['source_id']]
    r['title'] = m['title']; r['desc'] = m['description']; r['kel_text'] = m['kel_text']; r['loc_note'] = m['loc_note']
    # tingkat lokasi dari clean_listings.py (titik / kelurahan / kecamatan)
    if 'loc_level' in r:
        r['kec_only'] = r['loc_level'] == 'kecamatan'
    else:  # data lama
        r['kec_only'] = (not r['exact']) and (r['kel_text'] or '').strip().lower() in {k.lower() for k in KEC}
    r['xy'] = tf(r['lng'], r['lat'])

CAMPUS = campus_set(2.0)
# pn di dataset sudah dinormalisasi dengan faktor kampus model → kembalikan dulu agar analisis tidak sirkular
_model = json.load(open(os.path.join(ROOT, 'public/data/dataset.json')))['model']
_bands = (_model.get('campus') or {}).get('bands', [])
def _cf(d):
    for b in _bands:
        if b['minM'] <= d < b['maxM']: return math.exp(b['coef'])
    return 1.0
for r in rows:
    p = Point(r['xy'])
    d, name = min((g.distance(p), n) for n, g in CAMPUS)
    r['dcamp'] = d; r['camp'] = name
    r['pn_raw'] = r['pn'] * _cf(d)

EVID = {'text': [], 'perCampus': [], 'bands': [], 'regression': {}}

def report_text():
    pat = {
        'Undip/Tembalang inti': r'undip|diponegoro|banjarsari|sumurboto|tirto ?agung|prof\.? ?(haji )?soe?darto|ngesrep|baskoro|timoho|gondang|polines|bukit ?sari|pedalangan',
        'Unnes/Sekaran': r'unnes|sekaran|negeri semarang',
        'UIN/Unwahas Ngaliyan': r'\buin\b|walisongo|tambakaji|wahid hasyim|unwahas|ngaliyan',
        'Unika/Bendan': r'unika|soegijapranata|bendan',
        'Udinus': r'udinus|dian nuswantoro',
        'Unissula/Kaligawe': r'unissula|sultan agung',
    }
    print('\n## Harga menurut sebutan kampus di judul/deskripsi (iklan bersih, harga/m² asli, median)')
    for name, rx in pat.items():
        m = [r for r in rows if re.search(rx, (r['title'] + ' ' + r['desc']).lower())]
        kecs = Counter(r['kecamatan'] for r in m).most_common(2)
        others = [r for r in rows if r['kecamatan'] in [k for k, _ in kecs] and r not in m]
        print(f"  {name:22s} n={len(m):4d} median={statistics.median([r['ppm'] for r in m])/1e6:5.2f} jt | sisa kecamatan {[k for k,_ in kecs]} n={len(others)} median={statistics.median([r['ppm'] for r in others])/1e6:5.2f} jt")
        EVID['text'].append({'group': name, 'n': len(m), 'median': round(statistics.median([r['ppm'] for r in m])), 'restKec': [k for k, _ in kecs], 'restN': len(others), 'restMedian': round(statistics.median([r['ppm'] for r in others]))})

def report_bands():
    print('\n## Harga menurut jarak ke kampus (iklan berkoordinat tepat)')
    bands = [(0, 500), (500, 1000), (1000, 2000), (2000, 4000), (4000, 99e9)]
    ex = [r for r in rows if r['exact']]
    for a, b in bands:
        s = [r['ppm'] for r in ex if a <= r['dcamp'] < b]
        print(f"  {a:5.0f}-{b if b<1e9 else 'inf':>5} m n={len(s):4d} median={statistics.median(s)/1e6:5.2f} jt")
        EVID['bands'].append({'from': a, 'to': b if b < 1e9 else None, 'n': len(s), 'median': round(statistics.median(s))})
    print('  per kampus (≤1 km vs 1–3 km, iklan tepat):')
    by = defaultdict(lambda: ([], []))
    for r in ex:
        if r['dcamp'] < 1000: by[r['camp']][0].append(r['ppm'])
        elif r['dcamp'] < 3000: by[r['camp']][1].append(r['ppm'])
    for k, (a, b) in sorted(by.items(), key=lambda x: -len(x[1][0])):
        if len(a) >= 8 and len(b) >= 8:
            print(f"   {k[:40]:40s} ≤1km n={len(a):3d} {statistics.median(a)/1e6:5.2f} | 1–3km n={len(b):3d} {statistics.median(b)/1e6:5.2f}")
            EVID['perCampus'].append({'campus': k, 'nNear': len(a), 'near': round(statistics.median(a)), 'nFar': len(b), 'far': round(statistics.median(b))})

def regress(rows_, fe_key, bands):
    fes = sorted(set(r[fe_key] for r in rows_)); fi = {k: i for i, k in enumerate(fes)}
    X = []; y = []
    for r in rows_:
        fe = [0.0] * len(fes); fe[fi[r[fe_key]]] = 1.0
        b = [1.0 if lo <= r['dcamp'] < hi else 0.0 for lo, hi in bands]
        X.append(fe + b); y.append(math.log(r['pn_raw']))
    X = np.array(X); y = np.array(y)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta; s2 = res @ res / max(1, len(y) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.pinv(X.T @ X)))
    return [(float(beta[len(fes) + i]), float(se[len(fes) + i]), int(X[:, len(fes) + i].sum())) for i in range(len(bands))]

BANDS = [(0, 500), (500, 1000), (1000, 2000)]  # acuan: > 2 km
if __name__ == '__main__':
    print('lokasi: exact', sum(r['exact'] for r in rows), 'perkiraan kelurahan', sum(1 for r in rows if not r['exact'] and not r['kec_only']), 'hanya kecamatan', sum(r['kec_only'] for r in rows))
    print('  kec_only per teks:', Counter(r['kel_text'] for r in rows if r['kec_only']).most_common(8))
    t = [r for r in rows if r['kec_only'] and r['kel_text'] == 'Tembalang']; e = [r for r in rows if r['exact'] and r['kelurahan'] == 'Tembalang']; k = [r for r in rows if r['exact'] and r['kecamatan'] == 'Tembalang']
    print(f"  'Tembalang' kecamatan-only n={len(t)} median ppm {statistics.median([r['ppm'] for r in t])/1e6:.2f} jt, luas median {statistics.median([r['area_m2'] for r in t]):.0f} | tepat di kel. Tembalang n={len(e)} {statistics.median([r['ppm'] for r in e])/1e6:.2f} | tepat se-kec. Tembalang n={len(k)} {statistics.median([r['ppm'] for r in k])/1e6:.2f}")
    report_text(); report_bands()
    ex = [r for r in rows if r['exact']]
    for fe in ('kecamatan', 'kelurahan'):
        print(f'\n## Regresi log(harga ternormalisasi) ~ efek tetap {fe} + pita jarak kampus (iklan tepat, acuan > 2 km)')
        EVID['regression'][fe] = []
        for (lo, hi), (b, s, n) in zip(BANDS, regress(ex, fe, BANDS)):
            print(f"  {lo}-{hi} m: {b:+.3f} ± {s:.3f} (×{math.exp(b):.2f}) n={n}")
            EVID['regression'][fe].append({'from': lo, 'to': hi, 'coef': round(b, 4), 'se': round(s, 4), 'n': n})
    t = [r for r in rows if r['kec_only'] and r['kel_text'] == 'Tembalang']
    EVID['tembalangText'] = {'kecOnlyN': len(t), 'kecOnlyMedian': round(statistics.median([r['ppm'] for r in t])), 'kecOnlyArea': round(statistics.median([r['area_m2'] for r in t])),
                             'kelExactN': len(e), 'kelExactMedian': round(statistics.median([r['ppm'] for r in e])), 'kecExactN': len(k), 'kecExactMedian': round(statistics.median([r['ppm'] for r in k]))}
    json.dump(EVID, open(os.path.join(ROOT, 'data/campus_eval.json'), 'w'), indent=1, ensure_ascii=False)
