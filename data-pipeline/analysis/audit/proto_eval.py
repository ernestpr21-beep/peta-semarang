"""Validasi 'yang tampil di aplikasi': harga di titik iklan memakai tier hasil deteksi OSM (seperti klik pengguna),
sebelum vs sesudah faktor akses-otomatis terkalibrasi. Faktor dikalibrasi HANYA dari lipatan latih (CV blok spasial)."""
import json, math, os, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv_experiments as C
from common_audit import AUDIT_OUT
tiers = C.model['tiers']; unk = C.model['unknownTierFactor']; cbd = C.model['cbdFrontage']
acc = {a['id']: a for a in json.load(open(os.path.join(AUDIT_OUT, 'listing_access.json')))}
ORDER = ['utama', 'lingkungan', 'gang', 'tanpa']
def cbdf(r): return math.exp(cbd['coef'] * math.exp(-r['d_cbd'] / cbd['scaleM']))
def grp(a):  # kelompok deteksi
    return a['tier']

def neutral_of(pred):
    out = {}
    for r in C.T:
        ft = tiers[r['access_tier']]['factor'] if r['access_tier'] else unk
        ftx = ft * (cbdf(r) if r['access_tier'] == 'utama' else 1)
        out[r['id']] = pred[r['id']] - math.log(ftx)  # log harga 'tier tak diketahui' tanpa faktor tier (faktor 1)
    return out

def pava(vals, ns):
    """Monoton turun menurut ORDER (utama ≥ lingkungan ≥ gang ≥ tanpa), pooled-adjacent-violators berbobot n."""
    blocks = [[v, n, [i]] for i, (v, n) in enumerate(zip(vals, ns))]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] < blocks[i + 1][0]:
            v = (blocks[i][0] * blocks[i][1] + blocks[i + 1][0] * blocks[i + 1][1]) / (blocks[i][1] + blocks[i + 1][1])
            blocks[i] = [v, blocks[i][1] + blocks[i + 1][1], blocks[i][2] + blocks[i + 1][2]]; del blocks[i + 1]; i = max(0, i - 1)
        else: i += 1
    out = [0] * len(vals)
    for v, n, ix in blocks:
        for j in ix: out[j] = v
    return out

def calibrate(train_ids, neu):
    """log faktor otomatis per tier deteksi (median residu thd faktor 1) + skala premi CBD untuk utama terdeteksi."""
    byid = {r['id']: r for r in C.T}
    g = collections.defaultdict(list)
    for i in train_ids:
        r = byid[i]; g[acc[i]['tier']].append(math.log(r['ppm']) - neu[i])
    med = [float(np.median(g[t])) if g[t] else 0 for t in ORDER]; ns = [len(g[t]) for t in ORDER]
    # penyusutan ke log(unk) dengan bobot n/(n+30)
    med = [(n * m + 30 * math.log(unk)) / (n + 30) for m, n in zip(med, ns)]
    mono = pava(med, ns)
    f = dict(zip(ORDER, mono))
    # premi CBD untuk utama terdeteksi: pilih s∈{0..1} yang meminimalkan |galat| median di utama terdeteksi < 4 km
    best = (9, 0)
    for s in [0, 0.25, 0.5, 0.75, 1.0]:
        e = [abs(f['utama'] + s * math.log(cbdf(byid[i])) - (math.log(byid[i]['ppm']) - neu[i])) for i in train_ids if acc[i]['tier'] == 'utama' and byid[i]['d_cbd'] < 4000]
        if e and np.median(e) < best[0]: best = (float(np.median(e)), s)
    return f, best[1]

def display(neu, f=None, s=1.0):
    out = {}
    for r in C.T:
        t = acc[r['id']]['tier']
        lf = math.log(tiers[t]['factor']) if f is None else f[t]
        if t == 'utama': lf += s * math.log(cbdf(r))
        out[r['id']] = neu[r['id']] + lf
    return out

def evaluate_display(name, pred_base):
    neu = neutral_of(pred_base)
    before = display(neu)
    after = {}; fits = []
    for k in range(5):
        tr = [r['id'] for r in C.T if r['fold'] != k]
        f, s = calibrate(tr, neu); fits.append((f, s))
        d = display(neu, f, s)
        for r in C.T:
            if r['fold'] == k: after[r['id']] = d[r['id']]
    return neu, before, after, fits

if __name__ == '__main__':
    res = {}
    pc, _ = C.knn_preds({}, 'cv'); pc0, _ = C.knn_preds({'half_life': 0}, 'cv')
    neu, before, after, fits = evaluate_display('base', pc)
    _, _, after0, fits0 = evaluate_display('hl0', pc0)
    for name, p in [('sekarang (tier deteksi × faktor penuh)', before), ('usulan: faktor akses-otomatis terkalibrasi', after),
                    ('usulan + tanpa bobot umur', after0), ('pembanding: faktor 1 untuk semua deteksi', display(neu, {t: math.log(unk) for t in ORDER}, 0))]:
        o, e = C.evaluate(p, None, name); res[name] = o
        tb = collections.defaultdict(list)
        for r, ee in zip([r for r in C.T if r['id'] in p], e): tb[acc[r['id']]['tier']].append(ee)
        o['biasByDetectedTier'] = {t: {'n': len(v), 'bias': round(float(np.median(v)), 3), 'mdae': C.mdae(np.array(v))} for t, v in tb.items()}
        print(f"{name:45s} galat {o['mdae']}% bias {o['medianBias']:+.3f} ±25%: {o['within25']}% slope {o['calibSlope']} q {o['biasByKelLevelQuintile']}")
        print('    per tier deteksi', o['biasByDetectedTier'])
    res['fittedFactorsPerFold'] = [{'factors': {t: round(math.exp(v), 3) for t, v in f.items()}, 'cbdScale': s} for f, s in fits]
    print(res['fittedFactorsPerFold'])
    # faktor final (semua data) untuk prototipe
    f, s = calibrate([r['id'] for r in C.T], neu)
    res['finalFactors'] = {'factors': {t: round(math.exp(v), 3) for t, v in f.items()}, 'cbdScale': s}
    print('final', res['finalFactors'])
    json.dump(res, open(os.path.join(AUDIT_OUT, 'proto_display_eval.json'), 'w'), indent=1, ensure_ascii=False)
