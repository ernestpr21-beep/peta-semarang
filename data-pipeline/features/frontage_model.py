"""Premi muka jalan (tier utama) — model 2026-10-9.
log premi = a[kelas jalan] + b·(log(1+toko 250 m) − ref) + u[ruas bernama], ditaksir dari iklan yang jelas bermuka jalan:
(1) teks/pin terkait koridor arteri bernama, (2) teks menyebut jalan utama/raya, (3) pin ≤ 30 m dari jalan utama (terdeteksi tier utama) — kelompok (3) hanya untuk pengecekan, tidak untuk melatih:
iklan pin ≤ 30 m di arteri sudah wajar harganya (median residu ≈ −0,04) karena banyak yang sebenarnya bidang dalam.
Target = log harga iklan − log estimasi tier utama TANPA premi koridor (dari harness tests/validate-cv.test.ts, varian noCorridor),
di titik muka jalan (proyeksi ke as jalan bila ada, selain itu pin). Kelas & ruas disusutkan ke 0 (setara K_CLS / K_ROAD iklan).
mode 'oof' <harness.json> <variant> <eval.json> <out.json>: premi luar-lipatan (loo/cv/lko) → VAL corrOverride.
mode 'fit' <harness.json> <variant> <eval.json>: parameter produksi → data/frontage_model.json (+ data/frontage_train.csv)."""
import csv, json, math, os, sys, zlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import sampler as SP
from corridor import nn
from feature_model import fold
ALIASES = {'brigjen sudiarto': 'majapahit', 'arteri soekarno hatta': 'soekarno hatta', 'flyover ahmad yani': 'ahmad yani', 'arteri utara': 'arteri yos sudarso',
           'komdor laut yos sudarso': 'arteri yos sudarso', 'yos sudarso': 'arteri yos sudarso', 'jenderal ahmad yani': 'ahmad yani'}
def rkey(n): k = nn(n); return ALIASES.get(k, k)
CLASS_OF = {'trunk': 'arteri', 'trunk_link': 'arteri', 'primary': 'arteri', 'primary_link': 'arteri', 'secondary': 'sekunder', 'secondary_link': 'sekunder', 'tertiary': 'tersier', 'tertiary_link': 'tersier'}
CLS_LABEL = {'arteri': 'jalan arteri', 'sekunder': 'jalan kolektor', 'tersier': 'jalan kolektor kecil', 'lain': 'jalan utama'}
K_CLS, K_ROAD, LAM_SHOP, MAX_M = 2.0, 8.0, 20.0, 30.0
def wmed(v, w):
    o = np.argsort(v); c = np.cumsum(w[o]); return float(v[o][np.searchsorted(c, 0.5 * c[-1])])
def training(H, var, ev):
    E = {e['id']: e for e in ev}; out = []
    for r in H[f'{var}|loo']:
        if not r: continue
        e = E[r['id']]
        tied = e.get('corr') is not None; txt = e.get('txtTier') == 'utama'
        if r.get('proj') and r.get('uProj'): road, err, at = r['uProj'], r['eRoadMan'], r['proj']
        elif r.get('uPin') and r['uPin']['distanceM'] <= 30: road, err, at = r['uPin'], r['eManU'], [e['lat'], e['lng']]
        else: continue
        near = r.get('uPin') and r['uPin']['distanceM'] <= 30
        if not (tied or txt or (near and e.get('txtTier') not in ('lingkungan', 'gang'))): continue
        out.append({'id': r['id'], 'road': rkey(road['name']) if road.get('name') else None, 'label': road.get('name'), 'cls': CLASS_OF.get(road['highway'], 'lain'),
                    'shop': float(np.log1p(max(0.0, float(SP.raw(at[0], at[1], 'shop_250'))))), 'outlier': e['outlier'], 'kel': e['kel'], 'kec': e['kec'],
                    'fold': fold(e['lat'], e['lng']), 'group': set(e['group']) | {e['id']}, 'how': 'teks/pin koridor' if tied else 'teks jalan utama' if txt else 'pin ≤30 m'})
        # per mode: kesalahan tanpa premi juga per mode (base luar-lipatan berbeda)
    errs = {}
    for mode in ('loo', 'cv', 'lko'):
        for r in H[f'{var}|{mode}']:
            if not r: continue
            if r.get('proj') and r.get('uProj'): errs[(mode, r['id'])] = r['eRoadMan']
            elif r.get('uPin') and r['uPin']['distanceM'] <= 30: errs[(mode, r['id'])] = r['eManU']
    for t in out:
        for mode in ('loo', 'cv', 'lko'): t['t_' + mode] = -errs[(mode, t['id'])]
    return out
TRAIN_HOW = ('teks/pin koridor', 'teks jalan utama')  # pin ≤ 30 m saja = cek (sering bidang dalam; lihat laporan)
def fitp(rows, tkey):
    rows = [r for r in rows if not r['outlier'] and r['how'] in TRAIN_HOW]
    if not rows: return {'cls': {}, 'b': 0.0, 'ref': 0.0, 'u': {}}
    t = np.array([r[tkey] for r in rows]); sh = np.array([r['shop'] for r in rows]); ref = float(np.median(sh))
    a = {}; b = 0.0; u = {}
    for _ in range(6):
        res = t - b * (sh - ref) - np.array([u.get(r['road'], 0.0) for r in rows])
        # hanya kelas arteri yang mendapat premi kelas & toko: tier utama (×faktor tier) sudah dikalibrasi pada jalan kolektor,
        # dan premi kelas di kolektor memperburuk validasi keseluruhan (iklan terdeteksi utama di kolektor sudah wajar).
        m = np.array([r['cls'] == 'arteri' for r in rows])
        a = {'arteri': wmed(res[m], np.ones(m.sum())) * m.sum() / (m.sum() + K_CLS) if m.any() else 0.0}
        res = t - np.array([a.get(r['cls'], 0.0) for r in rows]) - np.array([u.get(r['road'], 0.0) for r in rows]); x = (sh - ref) * m
        b = float((x * res).sum() / ((x * x).sum() + LAM_SHOP)); b = max(0.0, b)  # toko sepanjang jalan tidak menurunkan premi
        res = t - np.array([a.get(r['cls'], 0.0) for r in rows]) - b * x
        u = {}
        for k in set(r['road'] for r in rows if r['road']):
            m = np.array([r['road'] == k for r in rows]); u[k] = wmed(res[m], np.ones(m.sum())) * m.sum() / (m.sum() + K_ROAD)
    return {'cls': a, 'b': b, 'ref': ref, 'u': u, 'n': {k: int(sum(r['road'] == k for r in rows)) for k in u}}
def prem(p, road, shop):
    if not road or road['distanceM'] > MAX_M: return 0.0
    c = CLASS_OF.get(road['highway'], 'lain'); k = rkey(road['name']) if road.get('name') else None
    return p['cls'].get(c, 0.0) + (p['b'] * (shop - p['ref']) if c == 'arteri' else 0.0) + p['u'].get(k, 0.0)
if __name__ == '__main__':
    mode, hpath, var, epath = sys.argv[1:5]
    H = json.load(open(hpath)); ev = json.load(open(epath)); E = {e['id']: e for e in ev}
    T = training(H, var, ev); print('iklan latih muka jalan', len(T), {h: sum(t['how'] == h for t in T) for h in ('teks/pin koridor', 'teks jalan utama', 'pin ≤30 m')})
    shop_at = lambda lat, lng: float(np.log1p(max(0.0, float(SP.raw(lat, lng, 'shop_250')))))
    if mode == 'oof':
        kfold = lambda e: zlib.crc32(f"{e['kel']}|{e['kec']}".encode()) % 20
        res = {}
        for m in ('loo', 'cv', 'lko'):
            res[m] = {'F': {}}; cache = {}
            for r in H[f'{var}|{m}']:
                if not r: continue
                e = E[r['id']]; g = set(e['group']) | {e['id']}
                key = ('loo', tuple(sorted(g))) if m == 'loo' else ('cv', fold(e['lat'], e['lng'])) if m == 'cv' else ('lko', e['kel'], e['kec'])
                if m == 'loo': tr = [t for t in T if not (t['group'] & g)]
                elif m == 'cv': tr = [t for t in T if t['fold'] != key[1]]
                else: tr = [t for t in T if not (t['kel'] == e['kel'] and t['kec'] == e['kec'])]
                if m != 'loo' and key in cache: p = cache[key]
                else: p = fitp(tr, 't_' + m); cache[key] = p
                pin = prem(p, r.get('uPin'), shop_at(e['lat'], e['lng'])) if r.get('uPin') else 0.0
                pj = prem(p, r.get('uProj'), shop_at(*r['proj'])) if r.get('proj') and r.get('uProj') else None
                res[m]['F'][r['id']] = {'pin': pin, 'proj': pj}
            print(m, 'done', flush=True)
        json.dump(res, open(sys.argv[5], 'w'))
    else:
        p = fitp(T, 't_loo')
        with open(os.path.join(ROOT, 'data/frontage_train.csv'), 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['id', 'road', 'cls', 'shop', 'how', 'outlier', 'target_loo', 'target_cv', 'target_lko'])
            for t in T: w.writerow([t['id'], t['road'] or '', t['cls'], round(t['shop'], 4), t['how'], int(t['outlier']), round(t['t_loo'], 4), round(t['t_cv'], 4), round(t['t_lko'], 4)])
        lab = {}
        for t in T:
            if t['road'] and t['label']: lab.setdefault(t['road'], t['label'].replace('Jalan ', 'Jl. '))
        out = {'maxRoadM': MAX_M, 'classOf': CLASS_OF, 'cls': {k: round(v, 4) for k, v in p['cls'].items()}, 'clsLabel': CLS_LABEL, 'shopCoef': round(p['b'], 4), 'shopRef': round(p['ref'], 4),
               'k': K_ROAD, 'aliases': ALIASES, 'roads': {k: {'label': lab.get(k, k.title()), 'n': p['n'][k], 'u': round(v, 4)} for k, v in sorted(p['u'].items())},
               'nTrain': len(T), 'note': 'Premi log tier jalan utama = a[kelas jalan OSM] + b·(log(1+toko/usaha 250 m) − ref) + u[ruas bernama]; kelas disusutkan setara %d iklan, ruas setara %d iklan. Dilatih dari iklan bermuka jalan (teks/pin koridor, teks "jalan utama/raya", pin ≤ 30 m dari jalan utama). Hanya berlaku bila tier jalan utama terdeteksi/dipilih.' % (K_CLS, K_ROAD)}
        json.dump(out, open(os.path.join(ROOT, 'data/frontage_model.json'), 'w'), ensure_ascii=False, indent=1)
        print(json.dumps({k: out[k] for k in ('cls', 'shopCoef', 'shopRef', 'nTrain')}), {k: (v['n'], v['u']) for k, v in out['roads'].items() if v['n'] >= 2})
