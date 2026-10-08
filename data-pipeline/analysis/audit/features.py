"""Fitur tambahan per iklan untuk eksperimen model: ketinggian & lereng (Copernicus GLO-30), penanda teks iklan."""
import csv, json, math, os, re, sys
import numpy as np, rasterio
from rasterio.merge import merge
from numpy.lib.stride_tricks import sliding_window_view
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import ROOT, AUDIT_OUT
csv.field_size_limit(10 ** 9)
D = os.path.join(ROOT, 'data-pipeline/.cache/dem')
arr, tr = merge([rasterio.open(os.path.join(D, t + '.tif')) for t in ['S07_00_E110_00', 'S08_00_E110_00']], bounds=(110.25, -7.16, 110.52, -6.90))
z = arr[0].astype(float)
dx = tr.a * 111320 * math.cos(math.radians(-7.03)); dy = -tr.e * 110574
gy, gx = np.gradient(z, dy, dx); slope = np.degrees(np.arctan(np.hypot(gx, gy)))
s90 = sliding_window_view(np.pad(slope, 1, mode='edge'), (3, 3)).mean(axis=(2, 3))
z90 = sliding_window_view(np.pad(z, 1, mode='edge'), (3, 3)).mean(axis=(2, 3))
np.savez_compressed(os.path.join(ROOT, 'data-pipeline/.cache/terrain_grid.npz'), slope=s90.astype(np.float32), elev=z90.astype(np.float32), transform=np.array([tr.a, tr.b, tr.c, tr.d, tr.e, tr.f]))
def at(a, lat, lng): return float(a[int((lat - tr.f) / tr.e), int((lng - tr.c) / tr.a)])
allr = {f"{r['source']}:{r['source_id']}": r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_all.csv')))}
FLAGS = {
    'f_bu': r'\b(bu\b|butuh uang|dijual cepat|jual cepat|cepat laku|di bawah harga|dibawah harga|bawah njop|harga miring|murah meriah)\b',
    'f_dev': r'\b(cicil|angsur|kpr|uang muka|start from|promo|launching|booking fee|free shm|free biaya|bebas biaya|tanpa bunga)\b',
    'f_sawah': r'\b(sawah|kebun|tegalan|perkebunan|ladang)\b',
    'f_hook': r'\b(hook|pojok)\b',
    'f_raya': r'\b(pinggir jalan raya|tepi jalan raya|pinggir jalan besar|jalan provinsi|jalan nasional|pinggir jalan utama|depan jalan raya)\b',
    'f_kos': r'\b(kost|kos-kosan|kos kosan|area kos|lingkungan kos)\b',
}
out = csv.writer(open(os.path.join(AUDIT_OUT, 'features.csv'), 'w', newline=''))
out.writerow(['id', 'elev', 'slope'] + list(FLAGS))
for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv'))):
    i = f"{r['source']}:{r['source_id']}"; a = allr.get(i, {}); t = ((a.get('title') or '') + ' ' + (a.get('description') or '')).lower()
    la, ln = float(r['lat']), float(r['lng'])
    out.writerow([i, round(at(z90, la, ln), 1), round(at(s90, la, ln), 2)] + [1 if re.search(p, t) else 0 for p in FLAGS.values()])
print('ok')
