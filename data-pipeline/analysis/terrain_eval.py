"""Apakah kemiringan lereng memengaruhi harga tanah? (Copernicus GLO-30 DEM, gratis, AWS Open Data)
Butuh rasterio (mis. python3 -m venv .venv && .venv/bin/pip install rasterio numpy). Hanya analisis — hasilnya
data/terrain_eval.json; faktor lereng TIDAK dipakai model karena tidak didukung data (lihat Metodologi §5e).
"""
import csv, json, math, os, urllib.request
import numpy as np, rasterio
from rasterio.merge import merge
from numpy.lib.stride_tricks import sliding_window_view
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
D = os.path.join(ROOT, 'data-pipeline/.cache/dem'); os.makedirs(D, exist_ok=True)
TILES = ['S07_00_E110_00', 'S08_00_E110_00']
for t in TILES:
    f = os.path.join(D, t + '.tif')
    if not os.path.exists(f):
        urllib.request.urlretrieve(f'https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{t}_DEM/Copernicus_DSM_COG_10_{t}_DEM.tif', f)
arr, tr = merge([rasterio.open(os.path.join(D, t + '.tif')) for t in TILES], bounds=(110.25, -7.16, 110.52, -6.90))
z = arr[0].astype(float)
dx = tr.a * 111320 * math.cos(math.radians(-7.03)); dy = -tr.e * 110574
gy, gx = np.gradient(z, dy, dx)
slope = np.degrees(np.arctan(np.hypot(gx, gy)))
s90 = sliding_window_view(np.pad(slope, 1, mode='edge'), (3, 3)).mean(axis=(2, 3))  # rata-rata ~90 m
def at(a, lat, lng): return float(a[int((lat - tr.f) / tr.e), int((lng - tr.c) / tr.a)])
rows = [r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv'))) if r['loc_level'] == 'titik']
for r in rows: r['slope'] = at(s90, float(r['lat']), float(r['lng']))
BANDS = [(0, 3), (3, 6), (6, 10), (10, 15), (15, 90)]
def band(s): return next(i for i, (lo, hi) in enumerate(BANDS) if lo <= s < hi)
AE = [0, 75, 100, 125, 175, 250, 400, 700, 1500, 1e12]
def fit(fe_key):
    kels = sorted(set(r[fe_key] for r in rows)); ki = {k: i for i, k in enumerate(kels)}
    X = []; y = []
    for r in rows:
        fe = [0.0] * len(kels); fe[ki[r[fe_key]]] = 1.0
        a = float(r['area_m2']); ab = [1.0 if AE[i] <= a < AE[i + 1] else 0.0 for i in range(9)]; del ab[3]
        sb = [1.0 if band(r['slope']) == i else 0.0 for i in range(1, len(BANDS))]
        t = r['access_tier'] or 'unknown'
        X.append(fe + ab + sb + [1.0 if t == tt else 0.0 for tt in ('utama', 'gang', 'tanpa', 'unknown')] + [1.0 if r['subtype'] == 'komersial' else 0.0, 1.0 if r['source'] == 'lamudi' else 0.0])
        y.append(math.log(float(r['ppm'])))
    X = np.array(X); y = np.array(y); keep = X.any(0); X = X[:, keep]
    b = np.linalg.lstsq(X, y, rcond=None)[0]; res = y - X @ b; s2 = res @ res / (len(y) - X.shape[1]); cov = s2 * np.linalg.pinv(X.T @ X)
    j0 = len(kels) + 8
    return [{'band': f'{BANDS[i][0]}–{BANDS[i][1]}°', 'coef': round(float(b[j0 + i - 1]), 3), 'se': round(math.sqrt(cov[j0 + i - 1, j0 + i - 1]), 3),
             'n': sum(1 for r in rows if band(r['slope']) == i)} for i in range(1, len(BANDS))]
loo = {r['id']: r for r in csv.DictReader(open(os.path.join(ROOT, 'data-pipeline/.cache/loo_residuals.csv')))}
resid = []
for i, (lo, hi) in enumerate(BANDS):
    e = sorted(float(loo[f"{r['source']}:{r['source_id']}"]['e']) for r in rows if band(r['slope']) == i and f"{r['source']}:{r['source_id']}" in loo)
    resid.append({'band': f'{lo}–{hi}°', 'n': len(e), 'q25': round(e[len(e) // 4], 3), 'median': round(e[len(e) // 2], 3), 'q75': round(e[3 * len(e) // 4], 3)})
S = sorted(r['slope'] for r in rows)
out = {'dem': 'Copernicus GLO-30 (DSM 30 m), lereng dirata-rata 3×3 sel (~90 m)', 'nTitik': len(rows),
       'slopeQuantiles': {str(q): round(S[int(q * (len(S) - 1))], 1) for q in (0.25, 0.5, 0.75, 0.9, 0.97)},
       'refBand': f'{BANDS[0][0]}–{BANDS[0][1]}°', 'withinKelurahan': fit('kelurahan'), 'withinKecamatan': fit('kecamatan'), 'looResidualByBand': resid,
       'testPoint': {'name': 'Candisari Gg. V (titik uji pengguna)', 'lat': -7.010649, 'lng': 110.421304, 'slopeDeg': round(at(s90, -7.010649, 110.421304), 1), 'elevM': round(at(z, -7.010649, 110.421304), 1)},
       'decision': 'tidak dipakai: dalam kelurahan yang sama tidak ada selisih harga bermakna menurut kelas lereng'}
json.dump(out, open(os.path.join(ROOT, 'data/terrain_eval.json'), 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out, ensure_ascii=False)[:1500])
