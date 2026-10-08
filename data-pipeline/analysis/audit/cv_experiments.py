"""4. Struktur model: varian estimator pembanding-terdekat & model gradient boosting, dinilai dengan
validasi silang blok spasial (blok 2 km, 5 lipatan — seluruh blok keluar bersama) dan leave-one-out."""
import csv, json, math, os, statistics, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import load_rows, KnnEstimator, spatial_folds, AUDIT_OUT, xy, mdae

rows, ds = load_rows(); model = ds['model']
F = {r['id']: r for r in csv.DictReader(open(os.path.join(AUDIT_OUT, 'features.csv')))}
for r in rows:
    f = F[r['id']]
    r['elev'] = float(f['elev']); r['slope'] = float(f['slope'])
    for k in f:
        if k.startswith('f_'): r[k] = int(f[k])
    r['lnorm'] = math.log(r['ppm'] / r['pn'])  # log faktor normalisasi (luas, akses, kampus, CBD, tren, sumber)
BLOCK = int(os.environ.get('BLOCK', 2000))
for r, f in zip(rows, spatial_folds(rows, block_m=BLOCK, k=5)): r['fold'] = f
T = [r for r in rows if r['loc_level'] == 'titik']
kl_all = {}
for r in rows:
    if r['loc_level'] != 'kecamatan': kl_all.setdefault(r['kelurahan'], []).append(r)
def kel_level(r):
    o = [x['pn'] for x in kl_all.get(r['kelurahan'], []) if x['id'] != r['id']]
    return statistics.median(o) if len(o) >= 3 else None
for r in T: r['kel_lvl'] = kel_level(r)
QL = np.quantile(np.log([r['kel_lvl'] for r in T if r['kel_lvl']]), [0, .2, .4, .6, .8, 1])

def evaluate(pred, sig=None, name=''):
    """pred: id -> log harga/m² mentah yang diprediksi. bias + = estimasi > harga iklan."""
    ids = [r['id'] for r in T if r['id'] in pred]
    y = np.array([math.log(r['ppm']) for r in T if r['id'] in pred]); p = np.array([pred[i] for i in ids]); e = p - y
    rr = [r for r in T if r['id'] in pred]
    A = np.column_stack([np.ones_like(p), p - p.mean()]); slope = float(np.linalg.lstsq(A, y, rcond=None)[0][1])
    out = {'name': name, 'n': len(ids), 'mdae': mdae(e), 'medianBias': round(float(np.median(e)), 3), 'within25': round(100 * float((np.abs(e) <= math.log(1.25)).mean()), 1),
           'calibSlope': round(slope, 3)}
    if sig is not None:
        s = np.array([sig[i] for i in ids]); out['cov50'] = round(100 * float((np.abs(e) <= 0.674 * s).mean()), 1)
    q = []
    for i in range(5):
        sel = np.array([r['kel_lvl'] is not None and QL[i] <= math.log(r['kel_lvl']) <= QL[i + 1] for r in rr])
        q.append(round(float(np.median(e[sel])), 3))
    out['biasByKelLevelQuintile'] = q
    kec = {}
    for r, ee in zip(rr, e): kec.setdefault(r['kecamatan'], []).append(ee)
    out['perKecamatan'] = {k: {'n': len(v), 'mdae': mdae(np.array(v)), 'bias': round(float(np.median(v)), 3)} for k, v in kec.items() if len(v) >= 10}
    return out, e

def knn_preds(params, mode='cv', value='pn'):
    pred = {}; sig = {}
    if mode == 'loo':
        est = KnnEstimator(rows, rows, model, value_key=value, **params)
        for r in T:
            p = est.predict(r['lat'], r['lng'], r['kelurahan'], r['kecamatan'], exclude_id=r['id'], area=r['area_m2'])
            pred[r['id']] = p['mu'] + (r['lnorm'] if value == 'pn' else 0); sig[r['id']] = p['sig']
        return pred, sig
    for f in range(5):
        pool = [r for r in rows if r['fold'] != f]
        est = KnnEstimator(pool, pool, model, value_key=value, **params)
        for r in T:
            if r['fold'] != f: continue
            p = est.predict(r['lat'], r['lng'], r['kelurahan'], r['kecamatan'], area=r['area_m2'])
            pred[r['id']] = p['mu'] + (r['lnorm'] if value == 'pn' else 0); sig[r['id']] = p['sig']
    return pred, sig

if __name__ == '__main__':
    VARIANTS = {
        'baseline (terpasang)': {},
        'tanpa penyusutan ke median wilayah': {'use_prior': False},
        'penyusutan lemah (setara 1)': {'prior_strength': 1.0},
        'penyusutan kuat (setara 8)': {'prior_strength': 8.0},
        'min pembanding efektif 5': {'min_eff': 5},
        'min pembanding efektif 20': {'min_eff': 20},
        'maks 15 pembanding': {'max_n': 15},
        'maks 60 pembanding': {'max_n': 60},
        'kernel sempit (h=R/5, min 150 m)': {'h_div': 5, 'h_min': 150},
        'kernel lebar (h=R/1.5)': {'h_div': 1.5},
        'tanpa bobot umur': {'half_life': 0},
        'tanpa iklan setingkat kelurahan': {'kel_weight': 0.0},
        'radius maks 1,5 km': {'radii': [400, 600, 800, 1000, 1500]},
    }
    res = {'block_m': BLOCK, 'knn': {}}
    t0 = time.time()
    for name, p in VARIANTS.items():
        pr, sg = knn_preds(p, 'cv'); o, _ = evaluate(pr, sg, name)
        pl, sl = knn_preds(p, 'loo'); ol, _ = evaluate(pl, sl, name)
        res['knn'][name] = {'spatialCV': o, 'loo': {k: ol[k] for k in ('mdae', 'medianBias', 'calibSlope', 'cov50', 'within25')}}
        print(f"{name:38s} CV {o['mdae']:5.1f}% bias {o['medianBias']:+.3f} slope {o['calibSlope']:.2f} cov {o['cov50']} | LOO {ol['mdae']:5.1f}% slope {ol['calibSlope']:.2f} cov {ol['cov50']} | kel-level bias {o['biasByKelLevelQuintile']}  ({time.time()-t0:.0f}s)")
    json.dump(res, open(os.path.join(AUDIT_OUT, f'cv_knn_block{BLOCK}.json'), 'w'), indent=1, ensure_ascii=False)
