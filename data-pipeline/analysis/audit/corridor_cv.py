"""Premi koridor: hanya iklan muka jalan pada ruas BERNAMA SAMA (teks menyebut jalan itu sebagai muka/alamat, atau pin ≤ 30 m dari ruas itu)."""
import json, math, os, sys, re
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import AUDIT_OUT, KnnEstimator, spatial_folds, wq
import arterial as A
import frontage_text as FT   # nn(), ROADS (memuat ulang; lambat tapi sekali)
rows, model = A.rows, A.model; tiers = model['tiers']; aa = model['autoAccess']
def cbdf(d): c = model['cbdFrontage']; return math.exp(c['coef'] * math.exp(-d / c['scaleM']))
ft = {o['id']: o for o in json.load(open(os.path.join(AUDIT_OUT, 'frontage_text.json')))}
MAIN = {k for k in FT.ROADS}
road_of = {}
for o in A.out:
    rk = None
    if o['id'] in ft and ft[o['id']]['dRoadPin'] <= 1500: rk = ft[o['id']]['road']
    elif o['dMain'] <= 30 and o['hw'] in ('trunk', 'primary', 'secondary') and o['road']: rk = FT.nn(o['road'])
    if rk: road_of[o['id']] = rk
T = [o for o in A.out if o['id'] in road_of]
print('listings tied to a named main road', len(T), '| roads with ≥3 listings', sum(1 for r in set(road_of.values()) if list(road_of.values()).count(r) >= 3))
KX, KY = 110500, 110574
def proj(rk, lat, lng):
    pts = FT.ROADS[rk]; a = min(pts, key=lambda q: (q[0] - lat) ** 2 + ((q[1] - lng) * 0.9993) ** 2); return a
P = {o['id']: proj(road_of[o['id']], o['lat'], o['lng']) for o in T}
def dupkey(o): return (round(o['area']), round(math.log(o['ppm']), 2))
est_full = KnnEstimator(rows, rows, model)
MU = {o['id']: est_full.predict(o['lat'], o['lng'], o['kel'], o['kec'], exclude_id=o['id'], area=o['area'])['mu'] for o in T}
def run(mode, k_prior, bw, use_outliers):
    for r, f in zip(rows, spatial_folds(rows, 2000, 5)): r['_f'] = f
    fo = {o['id']: f for o, f in zip(A.out, spatial_folds([{'lat': o['lat'], 'lng': o['lng']} for o in A.out], 2000, 5))}
    pred = {}
    for f in (range(5) if mode == 'cv' else [None]):
        pool = [r for r in rows if mode == 'loo' or r['_f'] != f]
        est = KnnEstimator(pool, pool, model) if mode == 'cv' else est_full
        def resid(o):
            p = est.predict(o['lat'], o['lng'], o['kel'], o['kec'], exclude_id=o['id'], area=o['area'])
            neu = p['mu'] + (math.log(o['neutral']) - MU[o['id']])
            return neu, math.log(o['ppm']) - neu - math.log(tiers['utama']['factor'] * cbdf(o['dCbd']))
        U = [o for o in T if (mode == 'loo' or fo[o['id']] != f) and (use_outliers or not o['outlier'])]
        RU = {o['id']: resid(o)[1] for o in U}
        for o in T:
            if mode == 'cv' and fo[o['id']] != f: continue
            neu, _ = resid(o)
            prem = 0.0
            if k_prior is not None:
                same = [u for u in U if road_of[u['id']] == road_of[o['id']] and u['id'] != o['id'] and dupkey(u) != dupkey(o)]
                if same:
                    d = np.array([math.hypot((P[u['id']][0] - P[o['id']][0]) * KY, (P[u['id']][1] - P[o['id']][1]) * KX) for u in same])
                    w = np.exp(-0.5 * (d / bw) ** 2); keep = w > 0.01
                    if keep.any():
                        w = w[keep]; v = np.array([RU[u['id']] for u, k in zip(same, keep) if k])
                        neff = w.sum() ** 2 / (w * w).sum(); prem = neff * float(wq(v, w, 0.5)) / (neff + k_prior)
            pred[o['id']] = (neu + math.log(tiers['utama']['factor'] * cbdf(o['dCbd'])) + prem - math.log(o['ppm']),
                             neu + math.log(aa['factors']['utama'] * cbdf(o['dCbd']) ** aa['cbdScale']) + prem - math.log(o['ppm']), prem)
    return pred
byid = {o['id']: o for o in T}
def st(pr, j, sel=lambda o: True):
    e = np.array([v[j] for k, v in pr.items() if sel(byid[k])]); return len(e), round((math.exp(float(np.median(np.abs(e)))) - 1) * 100, 1), round(float(np.median(e)), 3)
res = {}
for mode in ('loo', 'cv'):
    print(f'\n== {mode}  [manual utama | auto | auto non-outlier | Majapahit/Sudiarto]')
    for k in (None, 2, 4, 8):
        for bw in ((1500,) if k is None else (800, 1500, 3000)):
            for uo in ((False,) if k is None else (False, True)):
                pr = run(mode, k, bw, uo); name = 'sekarang' if k is None else f'koridor k={k} bw={bw}{" +outlier" if uo else ""}'
                a, b, c, m = st(pr, 0), st(pr, 1), st(pr, 1, lambda o: not o['outlier']), st(pr, 1, lambda o: road_of[o['id']] in ('majapahit', 'brigjen sudiarto'))
                res[f'{mode}|{name}'] = {'manual': a, 'auto': b, 'autoNonOutlier': c, 'majapahit': m}
                print(f"  {name:34s} manual {a[1]:5.1f}% {a[2]:+.3f} | auto {b[1]:5.1f}% {b[2]:+.3f} | non-outl {c[1]:5.1f}% {c[2]:+.3f} | Majapahit n={m[0]} {m[1]:5.1f}% {m[2]:+.3f}")
json.dump(res, open(os.path.join(AUDIT_OUT, 'corridor_cv.json'), 'w'), indent=1)
