"""Alat bersama audit model (Okt 2026): memuat iklan + fitur, port estimator src/lib/estimate.ts (Python, numpy),
dan pembagian validasi silang blok spasial. Hanya analisis; tidak mengubah keluaran aplikasi."""
import csv, json, math, os, statistics
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
AUDIT_OUT = os.environ.get('AUDIT_OUT', '/workspace/semarang-ref/audit')
os.makedirs(AUDIT_OUT, exist_ok=True)
CBD = (-6.990464, 110.422918)
LAT0 = -7.0
KX = 111320 * math.cos(math.radians(LAT0)); KY = 110574

def xy(lat, lng):
    return np.column_stack([np.asarray(lng) * KX, np.asarray(lat) * KY])

def load_model():
    return json.load(open(os.path.join(ROOT, 'public/data/dataset.json')))

_camp = None
def campus_dist(lats, lngs):
    global _camp
    if _camp is None:
        cs = json.load(open(os.path.join(ROOT, 'data/campus.json')))['campuses']
        cs = [c for c in cs if c['areaHa'] >= 2 and 'kepolisian' not in c['name'].lower()]
        _camp = unary_union([Polygon([(lng, lat) for lat, lng in r]) for c in cs for r in c['rings'] if len(r) >= 4])
    out = []
    for la, ln in zip(lats, lngs):
        p = Point(ln, la)
        out.append(0.0 if _camp.contains(p) else _camp.distance(p) * 110500)
    return np.array(out)

def load_rows():
    """Iklan model (data/listings_model.csv) + fitur turunan. pn = harga ternormalisasi model terpasang."""
    ds = load_model(); m = ds['model']
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv'))))
    ya, ma = map(int, m['asOf'].split('-'))
    for r in rows:
        for k in ('lat', 'lng', 'ppm', 'pn', 'area_m2'): r[k] = float(r[k])
        r['exact'] = int(r['exact']); r['id'] = f"{r['source']}:{r['source_id']}"
        d = r['date'][:7] or m['asOf']; y, mo = map(int, d.split('-'))
        r['age_y'] = max(0, ((ya - y) * 12 + (ma - mo)) / 12); r['year'] = y
        r['osm_main_m'] = float(r['osm_main_m']) if r['osm_main_m'] not in ('', 'None') else 9999.0
        r['osm_drive_m'] = float(r['osm_drive_m']) if r['osm_drive_m'] not in ('', 'None') else 9999.0
        r['d_cbd'] = math.hypot((r['lat'] - CBD[0]) * KY, (r['lng'] - CBD[1]) * KX)
    dc = campus_dist([r['lat'] for r in rows], [r['lng'] for r in rows])
    for r, d in zip(rows, dc): r['d_campus'] = float(d)
    return rows, ds

RADII = [400, 600, 800, 1000, 1500, 2000, 3000]

def wq(v, w, q):
    o = np.argsort(v); c = np.cumsum(w[o]); return v[o][min(len(v) - 1, np.searchsorted(c, q * c[-1]))]

class KnnEstimator:
    """Port estimator aplikasi (pembanding terdekat + penyusutan ke median wilayah). Parameter bisa diubah untuk uji."""
    def __init__(self, pool, all_rows, model, min_eff=10, max_n=30, prior_strength=3.0, h_min=250, h_div=2.5,
                 kel_weight=0.5, half_life=2.0, spread_floor=0.25, use_prior=True, radii=RADII, value_key='pn'):
        self.pool = [r for r in pool if r['loc_level'] != 'kecamatan']
        self.P = xy([r['lat'] for r in self.pool], [r['lng'] for r in self.pool])
        self.tree = cKDTree(self.P)
        self.v = np.log([r[value_key] for r in self.pool])
        self.locw = np.array([1.0 if r['loc_level'] == 'titik' else kel_weight for r in self.pool])
        self.rec = np.array([0.5 ** (r['age_y'] / half_life) if half_life else 1.0 for r in self.pool])
        self.ids = {r['id']: i for i, r in enumerate(self.pool)}
        self.min_eff, self.max_n, self.ps, self.h_min, self.h_div = min_eff, max_n, prior_strength, h_min, h_div
        self.floor = spread_floor; self.use_prior = use_prior; self.radii = radii
        kel = defaultdict(list); kec = defaultdict(list)
        for r in self.pool: kel[r['kelurahan']].append(r)
        for r in all_rows: kec[r['kecamatan']].append(r)  # median kecamatan memakai semua iklan (termasuk setingkat kecamatan) di pool
        self.kel, self.kec = kel, kec
        vals = [r[value_key] for r in all_rows]
        self.city_med = math.log(statistics.median(vals)); self.city_spread = model['citySpreadLog']; self.vk = value_key
        self.spread_cls = (model.get('spreadBySize') or {}).get('classes') or []

    def prior(self, kel, kec, exclude_id=None):
        kl = [x[self.vk] for x in self.kel.get(kel, []) if x['id'] != exclude_id]
        if len(kl) >= 3: return math.log(statistics.median(kl)), 'kelurahan'
        kc = [x[self.vk] for x in self.kec.get(kec, []) if x['id'] != exclude_id]
        if len(kc) >= 3: return math.log(statistics.median(kc)), 'kecamatan'
        return self.city_med, 'kota'

    def predict(self, lat, lng, kel=None, kec=None, exclude_id=None, area=150.0):
        p = xy([lat], [lng])[0]
        k = min(len(self.pool), 400)
        d, idx = self.tree.query(p, k=k)
        if exclude_id is not None and exclude_id in self.ids:
            keep = idx != self.ids[exclude_id]; d, idx = d[keep], idx[keep]
        rad = self.radii[-1]; sel = None
        for R in self.radii:
            m = d <= R
            if self.locw[idx[m]].sum() >= self.min_eff:
                rad = R; sel = m; break
        if sel is None: sel = d <= self.radii[-1]
        sel = sel & (self.locw[idx] > 0)
        ii = idx[sel][:self.max_n]; dd = d[sel][:self.max_n]
        pr, plevel = self.prior(kel, kec, exclude_id) if self.use_prior else (self.city_med, 'kota')
        if len(ii) == 0:
            return {'mu': pr, 'sig': self.city_spread, 'neff': 0, 'n': 0, 'radius': rad, 'muLocal': None, 'prior': pr, 'nearest': float(d[0]) if len(d) else 9e9}
        h = max(self.h_min, rad / self.h_div)
        w = (1 / (1 + (dd / h) ** 2)) * self.locw[ii] * self.rec[ii]
        v = self.v[ii]
        mu = wq(v, w, 0.5); neff = w.sum() ** 2 / (w * w).sum()
        mad = wq(np.abs(v - mu), np.sqrt(w), 0.5)
        kk = min(1, neff / 6); sl = kk * max(self.floor, 1.4826 * mad) + (1 - kk) * self.city_spread
        se = sl / math.sqrt(max(1, neff + self.ps * 0.5)); sig = math.sqrt(sl * sl + se * se)
        sc = next((c['scale'] for c in self.spread_cls if area >= c['minM2'] and (c['maxM2'] is None or area < c['maxM2'])), 1.0)
        muf = (neff * mu + self.ps * pr) / (neff + self.ps) if self.use_prior else mu
        return {'mu': muf, 'sig': sig * sc, 'neff': neff, 'n': len(ii), 'radius': rad, 'muLocal': mu, 'prior': pr, 'priorLevel': plevel, 'nearest': float(dd[0])}

def spatial_folds(rows, block_m=2000, k=5, seed=7):
    """Blok spasial persegi (block_m) dibagi acak ke k lipatan — seluruh blok keluar bersama saat diuji."""
    rng = np.random.default_rng(seed)
    blocks = {}
    for r in rows:
        b = (int(r['lng'] * KX // block_m), int(r['lat'] * KY // block_m))
        blocks.setdefault(b, None)
    keys = list(blocks); rng.shuffle(keys)
    fold_of = {b: i % k for i, b in enumerate(keys)}
    return [fold_of[(int(r['lng'] * KX // block_m), int(r['lat'] * KY // block_m))] for r in rows]

def mdae(e): return round((math.exp(float(np.median(np.abs(e)))) - 1) * 100, 1)
def bias(e): return round(float(np.median(e)), 3)
