"""Gradient boosting (LightGBM, objektif L1) vs estimator pembanding-terdekat, validasi silang blok spasial."""
import json, math, os, sys, time
import numpy as np, lightgbm as lgb
sys.path.insert(0, os.path.dirname(__file__))
import cv_experiments as C
from common_audit import KnnEstimator, spatial_folds, AUDIT_OUT, xy

rows, T, model = C.rows, C.T, C.model
TIER = {'utama': 3, 'lingkungan': 2, 'gang': 1, 'tanpa': 0, '': -1}
FLAGS = ['f_bu', 'f_dev', 'f_sawah', 'f_hook', 'f_raya', 'f_kos']
def feats(r, extra):
    P = xy([r['lat']], [r['lng']])[0]
    f = {'x': P[0], 'y': P[1], 'xr1': P[0] + P[1], 'xr2': P[0] - P[1],
         'ld_cbd': math.log(r['d_cbd'] + 100), 'ld_campus': math.log(min(r['d_campus'], 8000) + 100),
         'ld_main': math.log(min(r['osm_main_m'], 3000) + 10), 'ld_drive': math.log(min(r['osm_drive_m'], 1000) + 5),
         'osm_tier': TIER.get(r['osm_tier'], -1), 'txt_tier': TIER.get(r['access_tier'], -1),
         'larea': math.log(r['area_m2']), 'lamudi': 1 if r['source'] == 'lamudi' else 0, 'age': r['age_y'],
         'komersial': 1 if r['subtype'] == 'komersial' else 0, 'elev': r['elev'], 'slope': r['slope']}
    for k in FLAGS: f[k] = r[k]
    f.update(extra); return f

def knn_oof(train, params={}, k=4, seed=11):
    """Fitur kNN di luar-lipatan untuk baris latih (blok spasial bagian dalam) agar boosting tidak terlalu percaya kNN."""
    fo = spatial_folds(train, block_m=2000, k=k, seed=seed); out = {}
    for f in range(k):
        pool = [r for r, g in zip(train, fo) if g != f]
        est = KnnEstimator(pool, pool, model, **params)
        for r, g in zip(train, fo):
            if g == f:
                p = est.predict(r['lat'], r['lng'], r['kelurahan'], r['kecamatan'], area=r['area_m2'])
                out[r['id']] = (p['mu'], p['muLocal'] if p['muLocal'] is not None else p['mu'], math.log(p['neff'] + 1))
    return out

def run(variant, use_knn, target='raw', kel_rows=True, params=None):
    params = params or dict(objective='l1', learning_rate=0.03, num_leaves=15, min_data_in_leaf=25, feature_fraction=0.8,
                            bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=3)
    pred = {}
    for f in range(5):
        train = [r for r in rows if r['fold'] != f and r['loc_level'] != 'kecamatan' and (kel_rows or r['loc_level'] == 'titik')]
        test = [r for r in T if r['fold'] == f]
        ex_tr = {}; ex_te = {}
        if use_knn:
            oo = knn_oof(train)
            pool = [r for r in rows if r['fold'] != f]
            est = KnnEstimator(pool, pool, model)
            for r in train: ex_tr[r['id']] = dict(zip(['knn', 'knn_local', 'lneff'], oo[r['id']]))
            for r in test:
                p = est.predict(r['lat'], r['lng'], r['kelurahan'], r['kecamatan'], area=r['area_m2'])
                ex_te[r['id']] = {'knn': p['mu'], 'knn_local': p['muLocal'] if p['muLocal'] is not None else p['mu'], 'lneff': math.log(p['neff'] + 1)}
        Xtr = [feats(r, ex_tr.get(r['id'], {})) for r in train]; cols = list(Xtr[0])
        A = np.array([[x[c] for c in cols] for x in Xtr])
        off_tr = np.array([r['lnorm'] for r in train]) if target == 'pn' else 0
        y = np.log([r['ppm'] for r in train]) - off_tr
        if use_knn == 'residual':
            base = np.array([ex_tr[r['id']]['knn'] + r['lnorm'] for r in train]); y = np.log([r['ppm'] for r in train]) - base
        w = np.array([1.0 if r['loc_level'] == 'titik' else 0.5 for r in train])
        m = lgb.train(params, lgb.Dataset(A, y, weight=w), num_boost_round=700)
        B = np.array([[feats(r, ex_te.get(r['id'], {}))[c] for c in cols] for r in test])
        p = m.predict(B)
        for r, pp in zip(test, p):
            if use_knn == 'residual': pp = pp + ex_te[r['id']]['knn'] + r['lnorm']
            elif target == 'pn': pp = pp + r['lnorm']
            pred[r['id']] = pp
    return pred, m, cols

if __name__ == '__main__':
    res = {}
    base, _ = C.knn_preds({}, 'cv'); o, eb = C.evaluate(base, None, 'kNN terpasang'); res['kNN terpasang'] = o
    print(f"{'kNN terpasang':40s} CV {o['mdae']}% bias {o['medianBias']} slope {o['calibSlope']} w25 {o['within25']} q {o['biasByKelLevelQuintile']}")
    runs = [('GBM fitur lokasi saja (target mentah)', False, 'raw'), ('GBM fitur lokasi (target ternormalisasi)', False, 'pn'),
            ('GBM + fitur kNN (stacking)', True, 'raw'), ('kNN + koreksi residu GBM', 'residual', 'raw')]
    preds = {'kNN terpasang': base}
    for name, uk, tg in runs:
        t0 = time.time(); p, m, cols = run(name, uk, tg); preds[name] = p
        o, _ = C.evaluate(p, None, name); res[name] = o
        imp = sorted(zip(cols, m.feature_importance('gain')), key=lambda t: -t[1])[:8]
        o['topFeatures'] = [(c, round(float(g))) for c, g in imp]
        print(f"{name:40s} CV {o['mdae']}% bias {o['medianBias']} slope {o['calibSlope']} w25 {o['within25']} q {o['biasByKelLevelQuintile']} ({time.time()-t0:.0f}s)")
        print('   top', [c for c, _ in imp])
    # rata-rata kNN & GBM stacking
    a = {k: 0.5 * base[k] + 0.5 * preds['GBM + fitur kNN (stacking)'][k] for k in base}
    o, _ = C.evaluate(a, None, 'rata-rata kNN & GBM+kNN'); res[o['name']] = o
    print(f"{o['name']:40s} CV {o['mdae']}% bias {o['medianBias']} slope {o['calibSlope']} w25 {o['within25']} q {o['biasByKelLevelQuintile']}")
    json.dump(res, open(os.path.join(AUDIT_OUT, 'cv_gbm.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump({k: {i: round(v, 4) for i, v in p.items()} for k, p in preds.items()}, open(os.path.join(AUDIT_OUT, 'cv_gbm_preds.json'), 'w'))
