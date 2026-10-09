"""Muka jalan arteri di luar pusat kota: apakah harga iklan di tepi jalan utama (menurut kelas jalan OSM) lebih tinggi daripada estimasi?
Termasuk iklan yang dibuang sebagai 'outlier' (uji jujur: aturan outlier per kelurahan bisa membuang justru iklan muka jalan)."""
import csv, json, math, os, sys, glob, statistics, collections, datetime
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import ROOT, AUDIT_OUT, KnnEstimator, load_rows, xy, campus_dist
csv.field_size_limit(10 ** 9)
rows, ds = load_rows(); model = ds['model']
D = json.load(open(os.path.join(ROOT, 'public/data/dataset.json')))
kelstat = {(s['name'], s['kec']): s for s in D['kelurahan']}; kecstat = {s['name']: s for s in D['kecamatan']}

# --- jalan utama: segmen + kelas ---
segs = []
for f in glob.glob(os.path.join(ROOT, 'public/data/roads/*.json')):
    for r in json.load(open(f)):
        if r['c'] == 'utama':
            g = r['g']
            for i in range(0, len(g) - 2, 2): segs.append((g[i], g[i + 1], g[i + 2], g[i + 3], r['hw'].replace('_link', ''), r.get('n') or ''))
KX = 110500; KY = 110574
mid = np.array([[(a[1] + a[3]) / 2 * KX, (a[0] + a[2]) / 2 * KY] for a in segs]); tree = cKDTree(mid)
def nearest_main(lat, lng):
    p = np.array([lng * KX, lat * KY]); best = (9e9, None, None)
    for i in tree.query_ball_point(p, 400):
        a = segs[i]; x1, y1, x2, y2 = a[1] * KX, a[0] * KY, a[3] * KX, a[2] * KY
        dx, dy = x2 - x1, y2 - y1; t = max(0, min(1, ((p[0] - x1) * dx + (p[1] - y1) * dy) / (dx * dx + dy * dy or 1)))
        d = math.hypot(p[0] - x1 - t * dx, p[1] - y1 - t * dy)
        if d < best[0]: best = (d, a[4], a[5])
    return best
CLS = {'trunk': 'arteri (trunk/primary)', 'primary': 'arteri (trunk/primary)', 'secondary': 'kolektor (secondary)', 'tertiary': 'tersier'}

# --- normalisasi seperti pipeline, tetapi untuk iklan apa pun (juga outlier) ---
sc = model['sizeCurve']
def size_factor(a, z):
    a = max(30, min(50000, a)); la = math.log(a); ks = sc['knots']; xs = [math.log(k['area']) for k in ks]
    def at(key):
        if la <= xs[0]: return ks[0].get(key, 0)
        if la >= xs[-1]: return ks[-1].get(key, 0)
        for i in range(len(xs) - 1):
            if xs[i] <= la <= xs[i + 1]: return ks[i].get(key, 0) + (ks[i + 1].get(key, 0) - ks[i].get(key, 0)) * (la - xs[i]) / (xs[i + 1] - xs[i])
    return math.exp(at('coef') + at('slope') * z)
def campus_f(d):
    for b in model['campus']['bands']:
        if b['minM'] <= d < b['maxM']: return math.exp(b['coef'])
    return 1.0
asof = datetime.date.fromisoformat(model['asOf'] + '-01')
def lnorm_any(r, d_campus):
    ks = kelstat.get((r['kelurahan'], r['kecamatan'])); lvl = ks['medianRaw'] if ks and ks['n'] >= 3 else (kecstat.get(r['kecamatan']) or {}).get('medianRaw')
    z = max(sc['zMin'], min(sc['zMax'], math.log(lvl / sc['levelCenter']))) if lvl else 0
    dt = datetime.date.fromisoformat(r['date'][:10]); age = max(0, (asof - dt).days / 365.25)
    # faktor akses netral (1): residu diukur relatif terhadap 'tanpa faktor akses'
    return math.log(size_factor(float(r['area_m2']), z) * campus_f(d_campus)) - model['trendPerYear'] * age - math.log(model['sourceAdj'][r['source']])

allr = [r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_all.csv'))) if r['loc_level'] == 'titik' and r['lat'] and (r['flags'] == '' or r['flags'].startswith('outlier'))]
dc = campus_dist([float(r['lat']) for r in allr], [float(r['lng']) for r in allr])
CBD = (-6.990464, 110.422918)
est = KnnEstimator(rows, rows, model)
out = []
for r, dcam in zip(allr, dc):
    i = f"{r['source']}:{r['source_id']}"; lat, lng = float(r['lat']), float(r['lng'])
    p = est.predict(lat, lng, r['kelurahan'], r['kecamatan'], exclude_id=i, area=float(r['area_m2']))
    y = math.log(float(r['ppm'])) - (p['mu'] + lnorm_any(r, dcam))  # + = iklan di atas estimasi netral
    dm, hw, nm = nearest_main(lat, lng)
    dcbd = math.hypot((lat - CBD[0]) * KY, (lng - CBD[1]) * KX)
    out.append({'id': i, 'lat': lat, 'lng': lng, 'kel': r['kelurahan'], 'kec': r['kecamatan'], 'y': round(y, 4), 'outlier': r['flags'] != '', 'flag': r['flags'][:40],
                'txtUtama': r['access_tier'] == 'utama', 'txtTier': r['access_tier'], 'dMain': round(dm), 'hw': hw, 'road': nm, 'dCbd': round(dcbd), 'area': float(r['area_m2']), 'ppm': float(r['ppm']),
                'neutral': round(math.exp(p['mu'] + lnorm_any(r, dcam))), 'title': r['title'][:80]})
json.dump(out, open(os.path.join(AUDIT_OUT, 'arterial_resid.json'), 'w'), ensure_ascii=False)

def summ(sel, label):
    v = [o['y'] for o in sel]
    if len(v) < 5: print(f"  {label:60s} n={len(v)}"); return
    b = np.random.default_rng(0); bs = [np.median(b.choice(v, len(v))) for _ in range(800)]
    print(f"  {label:60s} n={len(v):4d} median {np.median(v):+.3f} (×{math.exp(np.median(v)):.2f}) CI90 [{np.quantile(bs,.05):+.2f},{np.quantile(bs,.95):+.2f}]")
for incl in (False, True):
    S = [o for o in out if incl or not o['outlier']]
    print('\n== termasuk outlier' if incl else '== hanya iklan model (tanpa outlier)')
    summ([o for o in S if o['dMain'] > 60 and not o['txtUtama']], 'kontrol: > 60 m dari jalan utama, teks tidak menyebut')
    for cls in ('arteri (trunk/primary)', 'kolektor (secondary)', 'tersier'):
        for ring, cond in (('< 4 km CBD', lambda o: o['dCbd'] < 4000), ('≥ 4 km CBD', lambda o: o['dCbd'] >= 4000)):
            summ([o for o in S if CLS.get(o['hw']) == cls and o['dMain'] <= 30 and cond(o)], f'pin ≤ 30 m dari {cls}, {ring}')
            summ([o for o in S if CLS.get(o['hw']) == cls and o['dMain'] <= 30 and o['txtUtama'] and cond(o)], f'   … dan teks menyebut jalan utama')
    summ([o for o in S if o['txtUtama'] and o['dCbd'] >= 4000], 'teks menyebut jalan utama, ≥ 4 km CBD (semua pin)')
