"""Bandingkan estimator lama (model 2026-10-1) vs baru pada target uji yang SAMA (leave-one-out).

Target utama: iklan yang menurut data baru punya pin tepat (loc_level=titik) dan juga ada di data lama.
Galat = |log harga asli − log prediksi| (normalisasi tiap versi dibalik, jadi setara galat di harga penawaran asli).
Pemakaian: python3 compare_versions.py <listings_model_lama.csv> <dataset_lama.json>
"""
import csv, json, math, os, statistics, sys
from collections import defaultdict
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OLD_CSV, OLD_DS = sys.argv[1], sys.argv[2]
RADII = [400, 600, 800, 1000, 1500, 2000, 3000]

def load(path, model):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        for k in ('lat', 'lng', 'ppm', 'pn', 'area_m2'): r[k] = float(r[k])
        r['exact'] = int(r['exact']); r['id'] = r['source'] + ':' + r['source_id']
        r['loc_level'] = r.get('loc_level') or ('titik' if r['exact'] else 'kelurahan')
        y, m = map(int, (r['date'][:7] or model['asOf']).split('-')); ya, ma = map(int, model['asOf'].split('-'))
        r['age_y'] = max(0, ((ya - y) * 12 + (ma - m)) / 12)
    return rows

def xy(rows):
    lat0 = -7.0
    return np.array([[r['lng'] * 111320 * math.cos(math.radians(lat0)), r['lat'] * 110574] for r in rows])

def wq(v, w, q):
    o = np.argsort(v); c = np.cumsum(w[o]); return v[o][np.searchsorted(c, q * c[-1])]

class Est:
    def __init__(self, rows, model, new):
        self.new = new
        self.pool = [r for r in rows if not (new and r['loc_level'] == 'kecamatan')]
        self.P = xy(self.pool)
        self.lpn = np.log([r['pn'] for r in self.pool])
        self.locw = np.array([1.0 if (r['loc_level'] == 'titik' if new else r['exact']) else (float(os.environ.get('KELW', 0.5)) if new else 0.5) for r in self.pool])
        self.rec = np.array([0.5 ** (r['age_y'] / 2) for r in self.pool])
        self.min_eff = (int(os.environ.get('MIN_EFF', 0)) or model.get('minEffComparables', 8)) if new else 8
        self.city_spread = model['citySpreadLog']; self.city_med = math.log(model['cityMedianPn'])
        self.kel = defaultdict(list); self.kec = defaultdict(list)
        for r in self.pool: self.kel[r['kelurahan']].append(r)
        for r in rows: self.kec[r['kecamatan']].append(r)
        self.idx = {id(r): i for i, r in enumerate(self.pool)}
    def campus_adj(self):
        if not os.environ.get('CAMPUS'): return
        B = [(500, 0.151), (1000, 0.106), (2000, 0.091)]
        def band(r):
            d = dcamp(r)
            for lim, b in B:
                if d < lim: return b
            return 0.0
        self.band = band
        self.lpn = self.lpn - np.array([band(r) for r in self.pool])
    def predict(self, r0, target_pn):
        p = xy([r0])[0]
        d = np.sqrt(((self.P - p) ** 2).sum(1))
        i0 = self.idx.get(id(r0))
        if i0 is not None: d[i0] = np.inf
        order = np.argsort(d)
        for R in RADII:
            inr = order[d[order] <= R]
            rad = R
            if self.locw[inr].sum() >= self.min_eff: break
        ch = inr[:30]
        kl = [x['pn'] for x in self.kel[r0['kelurahan']] if x is not r0]
        kc = [x['pn'] for x in self.kec[r0['kecamatan']] if x is not r0]
        prior = math.log(statistics.median(kl)) if len(kl) >= 3 else (math.log(statistics.median(kc)) if len(kc) >= 3 else self.city_med)
        if len(ch) == 0: return prior, self.city_spread
        h = max(250, rad / 2.5)
        w = (1 / (1 + (d[ch] / h) ** 2)) * self.locw[ch] * self.rec[ch]
        v = self.lpn[ch]
        mu = wq(v, w, 0.5); neff = w.sum() ** 2 / (w * w).sum()
        sp = float(os.environ.get('SPW', 0.5)) if self.new else 1.0
        mad = wq(np.abs(v - mu), w ** sp, 0.5)
        k = min(1, neff / 6); sl = k * max(0.25, 1.4826 * mad) + (1 - k) * self.city_spread
        se = sl / math.sqrt(max(1, neff + 1.5))
        ps = float(os.environ.get('PRIOR', 3)) if self.new else 3
        add = self.band(r0) if (self.new and os.environ.get('CAMPUS')) else 0.0
        return (neff * mu + ps * (prior - add)) / (neff + ps) + add, math.sqrt(sl * sl + se * se)

old_model = json.load(open(OLD_DS))['model']
new_model = json.load(open(os.path.join(ROOT, 'public/data/dataset.json')))['model']
old_rows = load(OLD_CSV, old_model); new_rows = load(os.path.join(ROOT, 'data/listings_model.csv'), new_model)
E_old = Est(old_rows, old_model, False); E_new = Est(new_rows, new_model, True)
old_by = {r['id']: r for r in old_rows}

camp = json.load(open(os.path.join(ROOT, 'data/campus.json')))['campuses']
def poly(c): return unary_union([Polygon([(lng, lat) for lat, lng in ring]) for ring in c['rings'] if len(ring) >= 4])
CAMPUS = [(c['name'], poly(c)) for c in camp if c['areaHa'] >= 2 and 'kepolisian' not in c['name'].lower()]
UNDIP = [g for n, g in CAMPUS if 'Diponegoro' in n][0]
def dcamp(r, g=None):
    p = Point(r['lng'], r['lat'])
    if g is not None: return g.distance(p) * 111000
    return min(gg.distance(p) for _, gg in CAMPUS) * 111000
def dcbd(r):
    return math.hypot((r['lat'] + 6.990464) * 110574, (r['lng'] - 110.422918) * 110500)

E_new.campus_adj()
targets = [r for r in new_rows if r['loc_level'] == 'titik' and r['id'] in old_by]
res = []
for r in targets:
    ro = old_by[r['id']]
    mo, so = E_old.predict(ro, ro['pn']); mn, sn = E_new.predict(r, r['pn'])
    res.append({'r': r, 'eo': math.log(ro['pn']) - mo, 'en': math.log(r['pn']) - mn, 'so': so, 'sn': sn,
                'dU': dcamp(r, UNDIP), 'dC': dcamp(r), 'dCBD': dcbd(r)})
def stats(sub, key, skey):
    e = [abs(x[key]) for x in sub]
    return {'mdae': round((math.exp(statistics.median(e)) - 1) * 100, 1), 'sigMed': round(statistics.median([x[skey] for x in sub]), 3), 'sigP90': round(float(np.percentile([x[skey] for x in sub], 90)), 3), 'cov50': round(100 * sum(abs(x[key]) <= 0.674 * x[skey] for x in sub) / len(sub), 1),
            'bias': round(statistics.median([x[key] for x in sub]), 3), 'w25': round(100 * sum(v <= math.log(1.25) for v in e) / len(e), 1)}
SUBSETS = {
    'semua (pin tepat)': lambda x: True,
    'Kec. Tembalang': lambda x: x['r']['kecamatan'] == 'Tembalang',
    '≤ 1,5 km dari Undip': lambda x: x['dU'] <= 1500,
    '≤ 1 km dari kampus mana pun': lambda x: x['dC'] <= 1000,
    '> 2 km dari kampus': lambda x: x['dC'] > 2000,
    'pusat kota ≤ 2 km Simpang Lima': lambda x: x['dCBD'] <= 2000,
    'pusat kota 2–4 km': lambda x: 2000 < x['dCBD'] <= 4000,
    'pinggiran (Gunungpati/Mijen/Tugu/Genuk)': lambda x: x['r']['kecamatan'] in ('Gunungpati', 'Mijen', 'Tugu', 'Genuk'),
    'iklan jalan utama (teks)': lambda x: x['r']['access_tier'] == 'utama',
}
out = {}
print(f"{'kelompok':42s} {'n':>5s} | {'lama: galat':>11s} {'cak50':>6s} {'bias':>7s} | {'baru: galat':>11s} {'cak50':>6s} {'bias':>7s}")
for name, f in SUBSETS.items():
    sub = [x for x in res if f(x)]
    if len(sub) < 10: continue
    o = stats(sub, 'eo', 'so'); n = stats(sub, 'en', 'sn')
    out[name] = {'n': len(sub), 'old': o, 'new': n}
    print(f"{name:42s} {len(sub):5d} | {o['mdae']:10.1f}% {o['cov50']:5.1f}% {o['bias']:+7.3f} | {n['mdae']:10.1f}% {n['cov50']:5.1f}% {n['bias']:+7.3f}  σ med/p90 {o['sigMed']}/{o['sigP90']} → {n['sigMed']}/{n['sigP90']}")
json.dump(out, open(os.path.join(ROOT, 'data/validation_before_after.json'), 'w'), indent=1, ensure_ascii=False)
if os.environ.get('DIAG'):
    sub = [x for x in res if 2000 < x['dCBD'] <= 4000]
    from collections import Counter
    worse = sorted(sub, key=lambda x: abs(x['en']) - abs(x['eo']), reverse=True)
    print('kel di 2-4 km:', Counter(x['r']['kelurahan'] for x in sub).most_common(12))
    agg = defaultdict(lambda: [0, 0.0])
    for x in sub:
        a = agg[x['r']['kelurahan']]; a[0] += 1; a[1] += abs(x['en']) - abs(x['eo'])
    print('perubahan galat log per kelurahan:', sorted(((k, v[0], round(v[1], 2)) for k, v in agg.items()), key=lambda t: -t[2])[:10])
    for x in worse[:15]:
        r = x['r']; ro = old_by[r['id']]
        print(f"{r['kelurahan']:14s} {r['source'][:3]} pn {r['pn']/1e6:6.2f} (lama {ro['pn']/1e6:6.2f}) pred lama {math.exp(math.log(ro['pn'])-x['eo'])/1e6:6.2f} baru {math.exp(math.log(r['pn'])-x['en'])/1e6:6.2f} tier {r['access_tier'] or '-'}")
# per kecamatan
kt = {}
print(f"\n{'kecamatan':20s} {'n':>4s} {'lama':>6s} {'baru':>6s}  bias lama/baru")
for k in sorted({x['r']['kecamatan'] for x in res}):
    sub = [x for x in res if x['r']['kecamatan'] == k]
    if len(sub) < 15: continue
    o = stats(sub, 'eo', 'so'); n = stats(sub, 'en', 'sn'); kt[k] = {'n': len(sub), 'old': o, 'new': n}
    print(f"{k:20s} {len(sub):4d} {o['mdae']:5.1f}% {n['mdae']:5.1f}%  {o['bias']:+.3f}/{n['bias']:+.3f}")
out['perKecamatan'] = kt
json.dump(out, open(os.path.join(ROOT, 'data/validation_before_after.json'), 'w'), indent=1, ensure_ascii=False)
