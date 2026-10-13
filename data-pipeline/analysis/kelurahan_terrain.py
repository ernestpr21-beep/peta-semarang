"""Klasifikasi medan per kelurahan (Copernicus GLO-30 DEM) — untuk validasi berbukit vs datar/padat & kolom tabel Data zona.
Butuh rasterio + shapely. Keluaran data/kelurahan_terrain.json: elevasi median (m), lereng rata-rata ~90 m (°), kelas.
Kelas: 'berbukit' bila lereng rata-rata ≥ 5° dan elevasi median ≥ 40 m, selain itu 'datar'."""
import json, math, os, urllib.request
import numpy as np, rasterio
from rasterio.merge import merge
from numpy.lib.stride_tricks import sliding_window_view
from shapely.geometry import shape, Point
from shapely.prepared import prep
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
s90 = sliding_window_view(np.pad(np.degrees(np.arctan(np.hypot(gx, gy))), 1, mode='edge'), (3, 3)).mean(axis=(2, 3))
SLOPE_HILLY = 5.0; ELEV_HILLY = 40  # DSM ikut menangkap tepi bangunan → dataran padat bisa tampak "miring"; syarat elevasi menyaringnya
out = []
for f in json.load(open(os.path.join(ROOT, 'public/data/kelurahan.geojson')))['features']:
    g = shape(f['geometry']); pg = prep(g); x0, y0, x1, y1 = g.bounds
    el, sl = [], []
    for lat in np.arange(y0, y1, 0.0009):
        for lng in np.arange(x0, x1, 0.0009):
            if pg.contains(Point(lng, lat)):
                i, j = int((lat - tr.f) / tr.e), int((lng - tr.c) / tr.a); el.append(z[i, j]); sl.append(s90[i, j])
    if not el:
        c = g.representative_point(); i, j = int((c.y - tr.f) / tr.e), int((c.x - tr.c) / tr.a); el, sl = [z[i, j]], [s90[i, j]]
    s = float(np.mean(sl)); e = float(np.median(el))
    out.append({'name': f['properties']['name'], 'kec': f['properties']['kecamatan'], 'elevM': round(e), 'slopeDeg': round(s, 1), 'cls': 'berbukit' if s >= SLOPE_HILLY and e >= ELEV_HILLY else 'datar'})
json.dump(out, open(os.path.join(ROOT, 'data/kelurahan_terrain.json'), 'w'), indent=0, ensure_ascii=False)
from collections import Counter; print(Counter(o['cls'] for o in out))
