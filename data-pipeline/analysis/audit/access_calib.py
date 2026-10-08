"""Seberapa informatif deteksi akses OSM aplikasi untuk harga? Bandingkan harga iklan (tanpa info akses di teks)
dengan estimasi netral (validasi silang blok spasial), menurut alasan deteksi."""
import json, math, os, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv_experiments as C
from common_audit import AUDIT_OUT
tiers = C.model['tiers']; unk = C.model['unknownTierFactor']; cbd = C.model['cbdFrontage']
acc = {a['id']: a for a in json.load(open(os.path.join(AUDIT_OUT, 'listing_access.json')))}
pc, _ = C.knn_preds({}, 'cv')
rng = np.random.default_rng(1)
def ci(v):
    v = np.array(v); b = [np.median(rng.choice(v, len(v))) for _ in range(1000)]
    return {'n': len(v), 'median': round(float(np.median(v)), 3), 'ci90': [round(float(np.quantile(b, .05)), 3), round(float(np.quantile(b, .95)), 3)]}
def cbdf(r):
    return math.exp(cbd['coef'] * math.exp(-r['d_cbd'] / cbd['scaleM']))
g = collections.defaultdict(list); gt = collections.defaultdict(list); app = collections.defaultdict(list); cbdg = collections.defaultdict(list)
for r in C.T:
    a = acc[r['id']]
    ft = tiers[r['access_tier']]['factor'] if r['access_tier'] else unk
    # lnorm memuat faktor tier teks dan (untuk utama) premi CBD; estimasi netral = tier "tidak diketahui"
    ftx = ft * (cbdf(r) if r['access_tier'] == 'utama' else 1)
    neutral = pc[r['id']] - math.log(ftx) + math.log(unk)
    y = math.log(r['ppm']) - neutral
    fd = tiers[a['tier']]['factor'] * (cbdf(r) if a['tier'] == 'utama' else 1)
    disp = neutral - math.log(unk) + math.log(fd)  # yang tampil di aplikasi bila pengguna klik titik ini (tier hasil deteksi)
    if not r['access_tier']:
        g[a['why']].append(y); app[a['why']].append(disp - math.log(r['ppm']))
        if a['tier'] == 'utama': cbdg['<2 km' if r['d_cbd'] < 2000 else '2-4 km' if r['d_cbd'] < 4000 else '>4 km'].append(y)
    gt[r['access_tier'] or '-'].append(y)
out = {'noTextTier_vsNeutral': {k: ci(v) for k, v in g.items()}, 'appDisplayedBias_noTextTier': {k: ci(v) for k, v in app.items()},
       'textTier_vsNeutral': {k: ci(v) for k, v in gt.items()}, 'detectedUtama_byCbd_vsNeutral': {k: ci(v) for k, v in cbdg.items()},
       'note': 'y = log(harga iklan) − log(estimasi netral, CV blok spasial). + = iklan lebih mahal dari estimasi netral. appDisplayedBias = log(tampilan aplikasi) − log(harga iklan).'}
json.dump(out, open(os.path.join(AUDIT_OUT, 'access_calibration.json'), 'w'), indent=1, ensure_ascii=False)
for k, v in out.items(): print(k, json.dumps(v, ensure_ascii=False))
