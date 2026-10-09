"""Premi muka jalan utama LOKAL: untuk tier utama, estimasi × exp(median berbobot residu iklan muka jalan di sekitar), disusutkan ke 0.
Diuji leave-one-out & CV blok spasial pada iklan muka jalan (teks 'jalan utama' atau pin ≤ 30 m dari jalan trunk/primary/secondary),
termasuk iklan yang dibuang sebagai outlier per kelurahan (aturan outlier lama tidak memperhitungkan akses)."""
import json, math, os, sys, statistics
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import AUDIT_OUT, KnnEstimator, load_rows, spatial_folds, wq
import arterial as A   # memuat iklan + residu netral (out) & normalisasi
rows, model = A.rows, A.model
tiers = model['tiers']; unk = model['unknownTierFactor']; aa = model['autoAccess']
def cbdf(d): c = model['cbdFrontage']; return math.exp(c['coef'] * math.exp(-d / c['scaleM']))
byid = {o['id']: o for o in A.out}
rowid = {r['id']: r for r in rows}
MAINCLS = ('trunk', 'primary', 'secondary')
def is_front(o): return o['txtUtama'] or (o['dMain'] <= 30 and o['hw'] in MAINCLS)
T = [o for o in A.out if is_front(o)]
print('frontage test listings', len(T), '| of which outlier-flagged', sum(o['outlier'] for o in T), '| text utama', sum(o['txtUtama'] for o in T))
def dupkey(o): return (round(o['area']), round(math.log(o['ppm']), 2))
KX, KY = 110500, 110574

def run(mode, k_prior, bw, keep_front_outliers, block=2000):
    # mode: 'loo' or 'cv'
    folds = {o['id']: f for o, f in zip(A.out, spatial_folds([{'lat': o['lat'], 'lng': o['lng']} for o in A.out], block_m=block, k=5))}
    for r, f in zip(rows, spatial_folds(rows, block_m=block, k=5)): r['_f'] = f
    preds = {}
    for f in (range(5) if mode == 'cv' else [None]):
        pool = [r for r in rows if mode == 'loo' or r['_f'] != f]
        est = KnnEstimator(pool, pool, model)
        # anggota premi: iklan muka jalan di pool (+ outlier muka jalan bila dipertahankan), residu thd estimasi netral tanpa dirinya
        U = [o for o in T if (mode == 'loo' or folds[o['id']] != f) and (not o['outlier'] or keep_front_outliers)]
        res = []
        for o in U:
            r = rowid.get(o['id'])
            p = est.predict(o['lat'], o['lng'], o['kel'], o['kec'], exclude_id=o['id'], area=o['area'])
            # residu thd prediksi utama 'manual' saat ini: y − log(faktor utama × cbd)
            res.append(o['y'] - math.log(tiers['utama']['factor'] * cbdf(o['dCbd'])) + (p['mu'] - p['mu']))
        # catatan: o['y'] dihitung thd estimator semua-data; untuk CV hitung ulang y thd pool lipatan
        if mode == 'cv':
            res = []
            for o in U:
                p = est.predict(o['lat'], o['lng'], o['kel'], o['kec'], exclude_id=o['id'], area=o['area'])
                yy = math.log(o['ppm']) - (p['mu'] + (math.log(o['neutral']) - A_mu[o['id']]))
                res.append(yy - math.log(tiers['utama']['factor'] * cbdf(o['dCbd'])))
        P = np.array([[o['lng'] * KX, o['lat'] * KY] for o in U]); tr = cKDTree(P) if len(U) else None; R = np.array(res)
        W0 = np.array([1.0 if o['id'] in rowid and rowid[o['id']]['loc_level'] == 'titik' or o['outlier'] else 0.5 for o in U])
        for o in T:
            if mode == 'cv' and folds[o['id']] != f: continue
            p = est.predict(o['lat'], o['lng'], o['kel'], o['kec'], exclude_id=o['id'], area=o['area'])
            neutral = p['mu'] + (math.log(o['neutral']) - A_mu[o['id']])
            prem = 0.0
            if k_prior is not None and tr is not None:
                idx = [i for i in tr.query_ball_point([o['lng'] * KX, o['lat'] * KY], 3 * bw) if U[i]['id'] != o['id'] and dupkey(U[i]) != dupkey(o)]
                if idx:
                    d = np.hypot(*(P[idx] - [o['lng'] * KX, o['lat'] * KY]).T); w = np.exp(-0.5 * (d / bw) ** 2) * W0[idx]
                    neff = w.sum() ** 2 / (w * w).sum(); m = float(wq(R[idx], w, 0.5))
                    prem = neff * m / (neff + k_prior)
            manual = neutral + math.log(tiers['utama']['factor'] * cbdf(o['dCbd'])) + prem
            auto = neutral + math.log(aa['factors']['utama'] * cbdf(o['dCbd']) ** aa['cbdScale']) + prem
            preds[o['id']] = (manual - math.log(o['ppm']), auto - math.log(o['ppm']), prem)
    return preds

# mu estimator penuh per iklan (untuk mengurai o['neutral'] = exp(mu_full + lnorm))
est_full = KnnEstimator(rows, rows, model)
A_mu = {o['id']: est_full.predict(o['lat'], o['lng'], o['kel'], o['kec'], exclude_id=o['id'], area=o['area'])['mu'] for o in T}

def stats(preds, which, sel=None):
    e = np.array([v[which] for k, v in preds.items() if sel is None or sel(byid[k])])
    return len(e), round((math.exp(float(np.median(np.abs(e)))) - 1) * 100, 1), round(float(np.median(e)), 3), round(100 * float((np.abs(e) <= math.log(1.25)).mean()), 1)
results = {}
configs = [('sekarang (tanpa premi lokal)', None, 700, False)] + [(f'premi lokal k={k}, bw={bw} m{", +outlier muka jalan" if ko else ""}', k, bw, ko) for k in (2, 4, 8) for bw in (500, 1000) for ko in (False, True)]
for mode in ('loo', 'cv'):
    print(f'\n== {mode.upper()} — galat pada iklan muka jalan (n, galat%, bias log, ±25%) [manual utama | auto/klik]')
    for name, k, bw, ko in configs:
        pr = run(mode, k, bw, ko)
        a = stats(pr, 0); b = stats(pr, 1); c = stats(pr, 1, lambda o: o['dCbd'] >= 4000); d = stats(pr, 1, lambda o: not o['outlier'])
        results[(mode, name)] = {'manual': a, 'auto': b, 'auto_outsideCBD': c, 'auto_modelListingsOnly': d}
        print(f"  {name:42s} manual {a[1]:5.1f}% {a[2]:+.3f} {a[3]:4.1f} | auto {b[1]:5.1f}% {b[2]:+.3f} {b[3]:4.1f} | auto ≥4km {c[1]:5.1f}% {c[2]:+.3f} | auto non-outlier {d[1]:5.1f}% {d[2]:+.3f}")
json.dump({f'{m}|{n}': v for (m, n), v in results.items()}, open(os.path.join(AUDIT_OUT, 'frontage_premium_cv.json'), 'w'), indent=1, ensure_ascii=False)
