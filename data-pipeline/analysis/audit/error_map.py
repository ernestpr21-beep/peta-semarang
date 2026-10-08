"""1. Peta galat sistematis: leave-one-out pada iklan berpin tepat (model terpasang 2026-10-3).
bias = log(estimasi / harga iklan) dalam ruang ternormalisasi (+ = estimasi terlalu tinggi)."""
import json, math, os, statistics, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import load_rows, KnnEstimator, AUDIT_OUT, mdae

rows, ds = load_rows(); m = ds['model']
est = KnnEstimator(rows, rows, m)
T = [r for r in rows if r['loc_level'] == 'titik']
for r in T:
    p = est.predict(r['lat'], r['lng'], r['kelurahan'], r['kecamatan'], exclude_id=r['id'], area=r['area_m2'])
    r['mu_hat'] = p['mu']; r['b'] = p['mu'] - math.log(r['pn']); r['sig_hat'] = p['sig']; r['neff'] = p['neff']; r['radius'] = p['radius']; r['prior'] = p['prior']; r['muLocal'] = p['muLocal']
b_all = np.array([r['b'] for r in T])
print('LOO pin tepat n', len(T), 'galat', mdae(b_all), '% bias median', round(float(np.median(b_all)), 3))

def grp(name, keyf, min_n=8):
    g = {}
    for r in T:
        k = keyf(r)
        if k is None: continue
        g.setdefault(k, []).append(r['b'])
    out = []
    for k, v in g.items():
        v = np.array(v)
        if len(v) < min_n: continue
        se = float(v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else 9
        out.append({'group': str(k), 'n': len(v), 'meanBias': round(float(v.mean()), 3), 'medianBias': round(float(np.median(v)), 3), 'se': round(se, 3),
                    't': round(float(v.mean()) / se, 2) if se else 0, 'mdae': mdae(v)})
    return out

def band(v, edges, fmt=lambda a, b: f'{a}–{b}'):
    for a, b in zip(edges, edges[1:]):
        if a <= v < b: return fmt(a, b)
    return None
INF = float('inf')
res = {}
res['kecamatan'] = grp('kecamatan', lambda r: r['kecamatan'])
res['kelurahan'] = grp('kelurahan', lambda r: f"{r['kelurahan']} ({r['kecamatan']})", min_n=6)
res['accessTierText'] = grp('tier', lambda r: r['access_tier'] or '(tidak disebut)')
res['osmTier'] = grp('osm', lambda r: r['osm_tier'])
res['mainRoadDist'] = grp('main', lambda r: band(r['osm_main_m'], [0, 30, 100, 300, 1000, INF], lambda a, b: f'{a}–{b} m'))
res['sizeBand'] = grp('size', lambda r: band(r['area_m2'], [0, 75, 100, 150, 250, 500, 1000, 3000, INF], lambda a, b: f'{a}–{b} m²'))
res['cbdRing'] = grp('cbd', lambda r: band(r['d_cbd'] / 1000, [0, 2, 4, 6, 8, 12, INF], lambda a, b: f'{a}–{b} km'))
res['campusBand'] = grp('campus', lambda r: band(r['d_campus'], [0, 500, 1000, 2000, 4000, INF], lambda a, b: f'{a}–{b} m'))
res['year'] = grp('year', lambda r: r['year'])
res['source'] = grp('source', lambda r: r['source'])
res['dateSource'] = grp('ds', lambda r: r['date_source'])
res['subtype'] = grp('sub', lambda r: r['subtype'] or '-')
# tingkat harga: menurut prediksi (uji kalibrasi tanpa bias regresi-ke-rata-rata mekanis)
mu = np.array([r['mu_hat'] for r in T]); y = np.log([r['pn'] for r in T])
A = np.column_stack([np.ones_like(mu), mu - mu.mean()]); coef, *_ = np.linalg.lstsq(A, y, rcond=None)
res['calibrationSlope'] = {'slope_y_on_pred': round(float(coef[1]), 3), 'note': 'kemiringan log(harga iklan) terhadap log(estimasi); > 1 = estimasi terlalu rata (wilayah mahal di-bawah-kan, murah di-atas-kan)'}
qs = np.quantile(mu, [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1])
res['byPredDecile'] = []
for i in range(10):
    sel = (mu >= qs[i]) & (mu <= qs[i + 1] if i == 9 else mu < qs[i + 1])
    v = b_all[sel]
    res['byPredDecile'].append({'decile': i + 1, 'predJt': round(math.exp(float(np.median(mu[sel]))) / 1e6, 2), 'n': int(sel.sum()), 'meanBias': round(float(v.mean()), 3), 'medianBias': round(float(np.median(v)), 3), 'mdae': mdae(v)})
# menurut tingkat harga kelurahan (median iklan lain di kelurahan itu)
kl = {}
for r in rows:
    if r['loc_level'] != 'kecamatan': kl.setdefault(r['kelurahan'], []).append(r)
def kel_level(r):
    o = [x['pn'] for x in kl.get(r['kelurahan'], []) if x['id'] != r['id']]
    return statistics.median(o) if len(o) >= 3 else None
lv = [(kel_level(r), r['b']) for r in T]; lv = [(a, b) for a, b in lv if a]
la = np.log([a for a, _ in lv]); lb = np.array([b for _, b in lv]); q = np.quantile(la, [0, .2, .4, .6, .8, 1])
res['byKelurahanLevelQuintile'] = [{'quintile': i + 1, 'kelMedianJt': round(math.exp(float(np.median(la[(la >= q[i]) & (la <= q[i + 1])]))) / 1e6, 2),
                                    'n': int(((la >= q[i]) & (la <= q[i + 1])).sum()), 'meanBias': round(float(lb[(la >= q[i]) & (la <= q[i + 1])].mean()), 3)} for i in range(5)]
# kelurahan dengan bias bermakna (Benjamini–Hochberg, q = 0,1)
from scipy import stats
kels = [k for k in res['kelurahan']]
for k in kels: k['p'] = float(2 * stats.t.sf(abs(k['t']), k['n'] - 1))
kels.sort(key=lambda k: k['p'])
M = len(kels); flagged = []
for i, k in enumerate(kels):
    if k['p'] <= 0.10 * (i + 1) / M: flagged = kels[:i + 1]
res['kelurahanFlagged'] = sorted(flagged, key=lambda k: -abs(k['meanBias']))
res['kelurahanFlaggedRule'] = 'n ≥ 6, uji-t rata-rata bias ≠ 0, koreksi Benjamini–Hochberg q=0,10'
res['overall'] = {'n': len(T), 'mdae': mdae(b_all), 'medianBias': round(float(np.median(b_all)), 3), 'meanBias': round(float(b_all.mean()), 3)}
json.dump(res, open(os.path.join(AUDIT_OUT, 'error_map.json'), 'w'), indent=1, ensure_ascii=False)
# simpan per iklan untuk peta bias
json.dump([{'id': r['id'], 'lat': r['lat'], 'lng': r['lng'], 'kel': r['kelurahan'], 'kec': r['kecamatan'], 'b': round(r['b'], 4), 'pn': round(r['pn']), 'est': round(math.exp(r['mu_hat'])), 'neff': round(r['neff'], 1), 'radius': r['radius'], 'area': r['area_m2'], 'tier': r['access_tier'], 'src': r['source'], 'year': r['year']} for r in T],
          open(os.path.join(AUDIT_OUT, 'loo_points.json'), 'w'))
def show(k, keyname='group'):
    print('\n==', k)
    for x in res[k]: print('  ', {kk: x[kk] for kk in x if kk not in ('p',)})
for k in ['kecamatan', 'accessTierText', 'osmTier', 'mainRoadDist', 'sizeBand', 'cbdRing', 'campusBand', 'year', 'source', 'dateSource', 'subtype', 'byPredDecile', 'byKelurahanLevelQuintile', 'kelurahanFlagged']: show(k)
print(res['calibrationSlope'])
