"""Uji (a) prior halus (median berbobot jarak, tanpa batas kelurahan) vs prior median kelurahan, (b) bobot umur, pada beberapa ukuran blok CV."""
import math, os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv_experiments as C
from common_audit import KnnEstimator, spatial_folds, xy, wq, AUDIT_OUT

class SmoothPrior(KnnEstimator):
    def __init__(self, *a, prior_bw=1500, **k):
        super().__init__(*a, **k); self.bw = prior_bw
    def prior(self, kel, kec, exclude_id=None, lat=None, lng=None):
        return self._sp, 'halus'
    def predict(self, lat, lng, kel=None, kec=None, exclude_id=None, area=150.0):
        p = xy([lat], [lng])[0]
        idx = self.tree.query_ball_point(p, 3 * self.bw)
        if exclude_id is not None and exclude_id in self.ids: idx = [i for i in idx if i != self.ids[exclude_id]]
        if len(idx) >= 3:
            d = np.hypot(*(self.P[idx] - p).T); w = np.exp(-0.5 * (d / self.bw) ** 2) * self.locw[idx]
            self._sp = float(wq(self.v[idx], w, 0.5))
        else:
            self._sp = self.city_med
        return super().predict(lat, lng, kel, kec, exclude_id, area)

def run(est_cls, params, block, seed=7):
    folds = spatial_folds(C.rows, block_m=block, k=5, seed=seed)
    for r, f in zip(C.rows, folds): r['_f'] = f
    pred = {}; sig = {}
    for f in range(5):
        pool = [r for r in C.rows if r['_f'] != f]
        est = est_cls(pool, pool, C.model, **params)
        for r in C.T:
            if r['_f'] != f: continue
            p = est.predict(r['lat'], r['lng'], r['kelurahan'], r['kecamatan'], area=r['area_m2'])
            pred[r['id']] = p['mu'] + r['lnorm']; sig[r['id']] = p['sig']
    return pred, sig

res = {}
V = [('baseline', KnnEstimator, {}), ('tanpa bobot umur', KnnEstimator, {'half_life': 0}), ('paruh umur 4 th', KnnEstimator, {'half_life': 4}),
     ('prior halus 1,5 km', SmoothPrior, {}), ('prior halus 1 km', SmoothPrior, {'prior_bw': 1000}), ('prior halus 1,5 km + tanpa bobot umur', SmoothPrior, {'half_life': 0})]
for block in [1000, 2000, 3000]:
    for seed in [7, 8]:
        for name, cls, p in V:
            pr, sg = run(cls, p, block, seed); o, _ = C.evaluate(pr, sg, name)
            res.setdefault(name, []).append({'block': block, 'seed': seed, 'mdae': o['mdae'], 'bias': o['medianBias'], 'slope': o['calibSlope'], 'cov50': o['cov50'], 'q': o['biasByKelLevelQuintile']})
for name, cls, p in V:
    pl, sl = C.knn_preds(p, 'loo') if cls is KnnEstimator else (None, None)
    if cls is not KnnEstimator:
        est = cls(C.rows, C.rows, C.model, **p); pl = {}; sl = {}
        for r in C.T:
            q = est.predict(r['lat'], r['lng'], r['kelurahan'], r['kecamatan'], exclude_id=r['id'], area=r['area_m2']); pl[r['id']] = q['mu'] + r['lnorm']; sl[r['id']] = q['sig']
    o, _ = C.evaluate(pl, sl, name)
    m = res[name]
    print(f"{name:40s} CV(6 runs) mean {np.mean([x['mdae'] for x in m]):.1f}% [{min(x['mdae'] for x in m)}–{max(x['mdae'] for x in m)}] cov {np.mean([x['cov50'] for x in m]):.1f} | LOO {o['mdae']}% cov {o['cov50']} slope {o['calibSlope']} q {o['biasByKelLevelQuintile']}")
    res[name] = {'cv': m, 'loo': {k: o[k] for k in ('mdae', 'medianBias', 'calibSlope', 'cov50', 'biasByKelLevelQuintile')}}
json.dump(res, open(os.path.join(AUDIT_OUT, 'cv_prior_halflife.json'), 'w'), indent=1, ensure_ascii=False)
