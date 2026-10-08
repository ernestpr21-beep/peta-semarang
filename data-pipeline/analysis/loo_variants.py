"""Validasi leave-one-out beberapa varian estimator (port src/lib/estimate.ts). Target utama: iklan berkoordinat tepat."""
import math, statistics, sys, json, os
import numpy as np
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from campus_eval import rows, ROOT, BANDS, regress
model = json.load(open(os.path.join(ROOT, 'data/model_report.json')))
CITY_SPREAD = model['citySpreadLog']
RADII = [400, 600, 800, 1000, 1500, 2000, 3000]
xy = np.array([r['xy'] for r in rows]); N = len(rows)
D = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1)).astype(np.float32)
exact = np.array([r['exact'] for r in rows]); kec_only = np.array([r['kec_only'] for r in rows])
age = np.array([float(json.loads('0') or 0) for r in rows])
import csv
mrows = {r['source'] + r['source_id']: r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv')))}
AS_OF = model['asOf']
def age_y(d):
    if not d: return 0
    y, m = map(int, d[:7].split('-')); ya, ma = map(int, AS_OF.split('-')); return max(0, ((ya - y) * 12 + ma - m) / 12)
age = np.array([age_y(mrows[r['source'] + r['source_id']]['date']) for r in rows])
rec = 0.5 ** (age / 2)
dcamp = np.array([r['dcamp'] for r in rows])

def wq(v, w, q):
    o = np.argsort(v); c = np.cumsum(w[o]); return v[o][np.searchsorted(c, q * c[-1])]

def run(cfg):
    camp_b = cfg.get('campus')  # list of (lo,hi,coef)
    cf = np.ones(N)
    if camp_b:
        for lo, hi, b in camp_b: cf[(dcamp >= lo) & (dcamp < hi)] = math.exp(b)
    lpn = np.log(np.array([r['pn'] for r in rows]) / cf)
    use = np.ones(N, bool)
    if cfg.get('drop_kec_only'): use &= ~kec_only
    w_ap = cfg.get('w_approx', 0.5)
    qual = np.where(exact == 1, 1.0, w_ap)
    kel = defaultdict(list); kec = defaultdict(list)
    for i, r in enumerate(rows):
        if use[i]: kel[r['kelurahan']].append(i)
        kec[r['kecamatan']].append(i)
    city = float(np.median(lpn[use]))
    errs = np.full(N, np.nan); cover = np.zeros(N, bool)
    for i in range(N):
        d = D[i].copy(); d[i] = np.inf; d[~use] = np.inf
        order = np.argsort(d)
        for R in RADII:
            k = np.searchsorted(d[order], R, side='right')
            idx = order[:k]
            if qual[idx].sum() >= cfg.get('min_eff', 8): break
        if cfg.get('exact_only_if_enough') and exact[idx].sum() >= 8:
            idx = idx[exact[idx] == 1]
        idx = idx[:30]
        h = max(cfg.get('hmin', 250), R / cfg.get('hdiv', 2.5))
        w = (1 / (1 + (d[idx] / h) ** 2)) * qual[idx] * rec[idx]
        kl = [j for j in kel[rows[i]['kelurahan']] if j != i]
        kc = [j for j in kec[rows[i]['kecamatan']] if j != i and use[j]]
        prior = float(np.median(lpn[kl])) if len(kl) >= 3 else (float(np.median(lpn[kc])) if len(kc) >= 3 else city)
        if len(idx) == 0:
            mu, sig = prior, CITY_SPREAD
        else:
            v = lpn[idx]; mu_l = wq(v, w, 0.5); mad = wq(np.abs(v - mu_l), w, 0.5); neff = w.sum() ** 2 / (w ** 2).sum()
            ps = cfg.get('prior_strength', 3)
            mu = (neff * mu_l + ps * prior) / (neff + ps)
            k_ = min(1, neff / 6); sl = k_ * max(0.25, 1.4826 * mad) + (1 - k_) * CITY_SPREAD
            se = sl / math.sqrt(max(1, neff + ps / 2)); sig = math.sqrt(sl * sl + se * se)
        e = lpn[i] - mu  # = log(pn_i) - log(prediksi) (faktor kampus di kedua sisi)
        errs[i] = e; cover[i] = abs(e) <= 0.674 * sig
    return errs, cover

def summarize(name, errs, cover):
    def m(mask):
        e = np.abs(errs[mask]); return (round((math.exp(np.median(e)) - 1) * 100, 1), round(100 * cover[mask].mean(), 1), int(mask.sum()), round(float(np.median(errs[mask])), 3))
    kecT = np.array([r['kecamatan'] == 'Tembalang' for r in rows])
    undip = np.array([r['camp'].startswith('Universitas Diponegoro') and r['dcamp'] < 1500 for r in rows])
    campus = dcamp < 1000; far = dcamp >= 2000
    ex = exact == 1
    res = {'semua (n)': m(np.ones(N, bool)), 'tepat': m(ex), 'tepat Kec. Tembalang': m(ex & kecT), 'tepat ≤1,5 km Undip': m(ex & undip), 'tepat ≤1 km kampus': m(ex & campus), 'tepat > 2 km kampus': m(ex & far)}
    print(f"\n{name}")
    for k, v in res.items(): print(f"   {k:24s} galat median {v[0]:5.1f}%  cakupan50 {v[1]:5.1f}%  n={v[2]:4d}  bias(log) {v[3]:+.3f}")
    return res

if __name__ == '__main__':
    ex_rows = [r for r in rows if r['exact']]
    camp_coef = [(lo, hi, b) for (lo, hi), (b, s, n) in zip(BANDS, regress(ex_rows, 'kelurahan', BANDS))]
    V = {
        'V0 sekarang': {},
        'V1 buang iklan lokasi-kecamatan': {'drop_kec_only': True},
        'V2 V1 + bobot perkiraan 0,25': {'drop_kec_only': True, 'w_approx': 0.25},
        'V3 V2 + hanya tepat bila ≥8 tepat': {'drop_kec_only': True, 'w_approx': 0.25, 'exact_only_if_enough': True},
        'V4 V3 + kernel lebih tajam (h≥150, R/3)': {'drop_kec_only': True, 'w_approx': 0.25, 'exact_only_if_enough': True, 'hmin': 150, 'hdiv': 3},
        'V5 V3 + faktor kampus (FE kelurahan)': {'drop_kec_only': True, 'w_approx': 0.25, 'exact_only_if_enough': True, 'campus': camp_coef},
    }
    out = {}
    for name, cfg in V.items():
        out[name] = summarize(name, *run(cfg))
    json.dump({'variants': out, 'campusCoef': camp_coef}, open(os.path.join(ROOT, 'data/loo_variants.json'), 'w'), indent=1, ensure_ascii=False)
