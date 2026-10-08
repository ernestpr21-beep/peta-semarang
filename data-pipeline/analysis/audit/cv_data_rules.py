"""Uji aturan data (koreksi penanda teks, buang pencilan, dedup, penyesuaian waktu) dengan validasi silang blok spasial.
Semua koefisien/aturan diestimasi HANYA dari lipatan latih."""
import json, math, os, statistics, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv_experiments as C
from common_audit import KnnEstimator, xy, AUDIT_OUT

rows, T, model = C.rows, C.T, C.model
FL = ['f_bu', 'f_dev', 'f_sawah', 'f_hook', 'f_raya']

def loo_resid(pool, params):
    est = KnnEstimator(pool, pool, model, value_key='pv', **params); out = []
    for r in pool:
        if r['loc_level'] != 'titik': continue
        p = est.predict(r['lat'], r['lng'], r['kelurahan'], r['kecamatan'], exclude_id=r['id'], area=r['area_m2'])
        out.append((r, math.log(r['pv']) - p['mu']))
    return out

def fit_flags(pool, params):
    """Koefisien penanda teks dari residu LOO di pool latih (regresi median sederhana via OLS pada residu terpotong)."""
    res = loo_resid(pool, params)
    X = np.array([[1] + [r[k] for k in FL] for r, _ in res], float); y = np.clip(np.array([e for _, e in res]), -1, 1)
    b = np.linalg.lstsq(X, y, rcond=None)[0][1:]
    return dict(zip(FL, b))

def run(name, flags=False, outlier=None, dedup=False, trend_extra=0.0, params=None):
    params = params or {}
    pred = {}; sig = {}; coefs = []
    for f in range(5):
        pool = [dict(r) for r in rows if r['fold'] != f]
        for r in pool: r['pv'] = r['pn'] * math.exp(trend_extra * r['age_y'])
        if dedup:  # iklan kembar lintas portal / ulang tayang: luas sama, harga/m² ±2 %, jarak < 400 m → simpan satu
            P = xy([r['lat'] for r in pool], [r['lng'] for r in pool]); keep = [True] * len(pool)
            from scipy.spatial import cKDTree
            tr = cKDTree(P)
            for i, j in sorted(tr.query_pairs(400)):
                if keep[i] and keep[j] and abs(pool[i]['area_m2'] - pool[j]['area_m2']) < 1 and abs(math.log(pool[i]['ppm'] / pool[j]['ppm'])) < 0.02:
                    keep[j] = False
            pool = [r for r, k in zip(pool, keep) if k]
        if outlier:
            kl = {}
            for r in pool:
                if r['loc_level'] != 'kecamatan': kl.setdefault(r['kelurahan'], []).append(math.log(r['pv']))
            def z(r):
                v = kl.get(r['kelurahan'], [])
                if len(v) < 6: return 0
                m = statistics.median(v); s = 1.4826 * statistics.median([abs(x - m) for x in v]) or 0.3
                return (math.log(r['pv']) - m) / max(s, 0.2)
            pool = [r for r in pool if abs(z(r)) <= outlier]
        cf = {}
        if flags:
            cf = fit_flags(pool, params); coefs.append(cf)
            for r in pool: r['pv'] = r['pv'] * math.exp(-sum(cf[k] * r[k] for k in FL))
        est = KnnEstimator(pool, pool, model, value_key='pv', **params)
        for r in T:
            if r['fold'] != f: continue
            p = est.predict(r['lat'], r['lng'], r['kelurahan'], r['kecamatan'], area=r['area_m2'])
            pred[r['id']] = p['mu'] + r['lnorm'] - trend_extra * r['age_y'] + sum(cf.get(k, 0) * r[k] for k in FL); sig[r['id']] = p['sig']
    o, e = C.evaluate(pred, sig, name)
    if coefs: o['flagCoefs'] = {k: round(float(np.mean([c[k] for c in coefs])), 3) for k in FL}
    # juga: error untuk iklan "biasa" (tanpa penanda) — yang paling mirip yang ditampilkan peta
    plain = {r['id'] for r in T if not any(r[k] for k in FL)}
    o2, _ = C.evaluate({k: v for k, v in pred.items() if k in plain}, None, name + ' [iklan biasa]')
    o['plain'] = {k: o2[k] for k in ('n', 'mdae', 'medianBias', 'biasByKelLevelQuintile')}
    print(f"{name:44s} CV {o['mdae']}% bias {o['medianBias']:+.3f} slope {o['calibSlope']} cov {o['cov50']} | biasa: {o2['mdae']}% bias {o2['medianBias']:+.3f} | q {o['biasByKelLevelQuintile']} {o.get('flagCoefs','')}")
    return o, pred

if __name__ == '__main__':
    out = {}
    for args in [('baseline', {}), ('koreksi penanda teks', {'flags': True}), ('buang pencilan |z|>3 per kelurahan', {'outlier': 3.0}),
                 ('buang pencilan |z|>2.5', {'outlier': 2.5}), ('dedup iklan kembar', {'dedup': True}),
                 ('tren waktu +3 %/th tambahan', {'trend_extra': 0.03}), ('tren waktu +6 %/th tambahan', {'trend_extra': 0.06}),
                 ('tanpa bobot umur', {'params': {'half_life': 0}}),
                 ('gabungan: teks+pencilan3+dedup', {'flags': True, 'outlier': 3.0, 'dedup': True}),
                 ('gabungan + tren +3 %', {'flags': True, 'outlier': 3.0, 'dedup': True, 'trend_extra': 0.03}),
                 ('gabungan + tanpa bobot umur', {'flags': True, 'outlier': 3.0, 'dedup': True, 'params': {'half_life': 0}})]:
        o, _ = run(args[0], **args[1]); out[args[0]] = o
    json.dump(out, open(os.path.join(AUDIT_OUT, 'cv_data_rules.json'), 'w'), indent=1, ensure_ascii=False)
