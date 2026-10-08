"""Analisis: apakah premi 'pinggir jalan utama' berbeda menurut tingkat harga kawasan / kelas jalan / pusat kota?
Jalankan setelah build_app_data.py."""
import csv, json, math, os, re, statistics
from collections import Counter, defaultdict
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
rows = [r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv'))) if r['loc_level'] != 'kecamatan']
meta = {r['source'] + r['source_id']: r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_all.csv')))}
for r in rows:
    for k in ('lat', 'lng', 'ppm', 'pn', 'area_m2'): r[k] = float(r[k])
    m = meta[r['source'] + r['source_id']]; r['text'] = (m['title'] + ' ' + m['description']).lower()
def hav(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(x))
for r in rows: r['d5'] = hav(r['lat'], r['lng'], -6.990464, 110.422918)
PROTOKOL = r'pandanaran|pemuda|gajah ?mada|ahmad yani|a\. ?yani|pahlawan|haryono|thamrin|imam bonjol|sultan agung|setia ?budi|majapahit|siliwangi|kaligawe|pierre tendean|veteran|sriwijaya|kartini|dr\.? ?cipto|brigjen sudiarto|indraprasta|soekarno.?hatta|arteri|jalan protokol|protokol'
for r in rows: r['protokol'] = bool(re.search(PROTOKOL, r['text']))
kmed = {}
g = defaultdict(list)
for r in rows: g[r['kelurahan']].append(math.log(r['pn']))
city = statistics.median([math.log(r['pn']) for r in rows])
for k, v in g.items(): kmed[k] = statistics.median(v)

def ols(rows_, feats, label):
    kels = sorted(set(r['kelurahan'] for r in rows_)); ki = {k: i for i, k in enumerate(kels)}
    X = []; y = []
    for r in rows_:
        fe = [0.0] * len(kels); fe[ki[r['kelurahan']]] = 1.0
        X.append(fe + [f(r) for _, f in feats]); y.append(math.log(r['ppm']))
    X = np.array(X); y = np.array(y)
    keep = [j for j in range(X.shape[1]) if X[:, j].any()]
    Xk = X[:, keep]
    b, *_ = np.linalg.lstsq(Xk, y, rcond=None)
    res = y - Xk @ b; s2 = res @ res / max(1, len(y) - Xk.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.pinv(Xk.T @ Xk)))
    names = [f'fe{j}' for j in range(len(kels))] + [n for n, _ in feats]
    print(f'\n## {label} (n={len(y)})')
    out = {}
    for j, bj, sj in zip(keep, b, se):
        if j >= len(kels):
            print(f'   {names[j]:28s} {bj:+.3f} ± {sj:.3f} (×{math.exp(bj):.2f})'); out[names[j]] = (float(bj), float(sj))
    return out

T = lambda t: (lambda r: 1.0 if r['access_tier'] == t else 0.0)
base = [('log_area', lambda r: math.log(r['area_m2'] / 150)), ('gang', T('gang')), ('unknown', T('')), ('komersial', lambda r: 1.0 if r['subtype'] == 'komersial' else 0.0),
        ('lamudi', lambda r: 1.0 if r['source'] == 'lamudi' else 0.0)]
res = {}
res['flat'] = ols(rows, base + [('utama', T('utama'))], 'premi utama rata (acuan)')
res['level'] = ols(rows, base + [('utama', T('utama')), ('utama×(lvl kel−kota)', lambda r: (kmed[r['kelurahan']] - city) if r['access_tier'] == 'utama' else 0.0)], 'premi utama × tingkat harga kelurahan')
res['cbd'] = ols(rows, base + [('utama', T('utama')), ('utama×(≤2km Simpang Lima)', lambda r: 1.0 if r['access_tier'] == 'utama' and r['d5'] < 2000 else 0.0)], 'premi utama di pusat kota (≤ 2 km dari Simpang Lima)')
res['prot'] = ols(rows, base + [('utama', T('utama')), ('utama×sebut jalan protokol/arteri', lambda r: 1.0 if r['access_tier'] == 'utama' and r['protokol'] else 0.0)], 'premi utama × menyebut nama jalan protokol/arteri')
print('\nIklan ≤ 2 km dari Simpang Lima per tier akses:', Counter(r['access_tier'] or '-' for r in rows if r['d5'] < 2000))
for t in ('utama', 'lingkungan', 'gang', ''):
    v = [r['ppm'] for r in rows if r['d5'] < 2000 and r['access_tier'] == t]
    if v: print(f'   {t or "tidak disebut":14s} n={len(v):3d} median {statistics.median(v)/1e6:.2f} jt')
json.dump({k: {n: [round(b, 4), round(s, 4)] for n, (b, s) in v.items()} for k, v in res.items()}, open(os.path.join(ROOT, 'data/frontage_eval.json'), 'w'), indent=1)

# pita jarak dari Simpang Lima untuk premi utama
BANDS = [(0, 1000), (1000, 2000), (2000, 3000), (3000, 5000)]
feats = base + [('utama', T('utama'))] + [(f'utama×{a/1000:g}–{b/1000:g} km', (lambda a, b: lambda r: 1.0 if r['access_tier'] == 'utama' and a <= r['d5'] < b else 0.0)(a, b)) for a, b in BANDS]
res['bands'] = ols(rows, feats, 'premi utama per pita jarak dari Simpang Lima (acuan > 5 km)')
for a, b in BANDS:
    print(f'   n utama {a}-{b}:', sum(1 for r in rows if r['access_tier'] == 'utama' and a <= r['d5'] < b))
# premi utama: menyebut jalan protokol, di luar pusat kota
res['prot_out'] = ols(rows, base + [('utama', T('utama')), ('utama×≤2km', lambda r: 1.0 if r['access_tier'] == 'utama' and r['d5'] < 2000 else 0.0),
                                    ('utama×protokol (>2km)', lambda r: 1.0 if r['access_tier'] == 'utama' and r['protokol'] and r['d5'] >= 2000 else 0.0)], 'premi utama: pusat kota + jalan protokol di luar pusat')
# eksponensial: utama × exp(-d/L)
for L in (750, 1000, 1500, 2000, 3000):
    o = ols(rows, base + [('utama', T('utama')), (f'utama×exp(-d/{L})', (lambda L: lambda r: math.exp(-r['d5'] / L) if r['access_tier'] == 'utama' else 0.0)(L))], f'peluruhan L={L} m')
json.dump({k: {n: [round(b, 4), round(s, 4)] for n, (b, s) in v.items()} for k, v in res.items()}, open(os.path.join(ROOT, 'data/frontage_eval.json'), 'w'), indent=1)
