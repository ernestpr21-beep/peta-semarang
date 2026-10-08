"""2. Sapuan kewajaran spasial pada kisi 250 m (lingkungan, 150 m²) + peta PNG estimasi & bias."""
import json, math, os, sys
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, TwoSlopeNorm
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import ROOT, AUDIT_OUT, KX, KY

GRID = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AUDIT_OUT, 'grid_v3.json')
TAG = sys.argv[2] if len(sys.argv) > 2 else 'v3'
g = json.load(open(GRID))
kel = json.load(open(os.path.join(ROOT, 'public/data/kelurahan.geojson')))
pts = json.load(open(os.path.join(AUDIT_OUT, os.environ.get('LOO_POINTS', 'loo_points.json'))))
lat = np.array([c['lat'] for c in g]); lng = np.array([c['lng'] for c in g]); VAL = os.environ.get('VALUE', 'ling')
v = np.array([c[VAL] for c in g], float)
step = float(os.environ.get('GRID_STEP', 250))
dLat = step / 110574; dLng = step / (111320 * math.cos(math.radians(7)))
iy = np.round((lat - lat.min()) / dLat).astype(int); ix = np.round((lng - lng.min()) / dLng).astype(int)
pos = {(a, b): i for i, (a, b) in enumerate(zip(iy, ix))}
populated = np.array([(c['nSeg'] >= 3) or (c['dLing'] is not None and c['dLing'] <= 60) for c in g])
flags = {i: [] for i in range(len(g))}
# lompatan antar tetangga
jumps = []
for i, (a, b) in enumerate(zip(iy, ix)):
    for da, db in ((0, 1), (1, 0)):
        j = pos.get((a + da, b + db))
        if j is None: continue
        r = abs(math.log(v[i] / v[j]))
        if r > math.log(1.5) and populated[i] and populated[j]:
            jumps.append((r, i, j))
for r, i, j in jumps: flags[i].append(f'lompatan ×{math.exp(r):.1f} ke tetangga'); flags[j].append(f'lompatan ×{math.exp(r):.1f} ke tetangga')
for i, c in enumerate(g):
    if c['kelMedian'] and c['kelN'] >= 5:
        r = math.log(c[VAL] / (c['kelMedian'] * c['campusF']))
        if abs(r) > math.log(1.8): flags[i].append(f'×{math.exp(r):.2f} dari median kelurahan (n={c["kelN"]})')
    if populated[i] and (c['nearestM'] > 1500 or c['nEff'] < 3): flags[i].append(f'pembanding jauh/sedikit (terdekat {c["nearestM"]} m, nEff {c["nEff"]})')
q01, q99 = np.quantile(v[populated], [0.01, 0.99])
for i in range(len(g)):
    if populated[i] and (v[i] < q01 or v[i] > q99): flags[i].append('nilai ekstrem (1% teratas/terbawah)')
# kelas akses yang meragukan: titik padat jalan tetapi 'tanpa', atau di dalam kampus
for i, c in enumerate(g):
    if c['tier'] == 'tanpa' and c['nSeg'] >= 8: flags[i].append(f'akses terdeteksi "tanpa" padahal {c["nSeg"]} ruas jalan ≤ 200 m (gang belum dipetakan?)')
    if c['campusD'] == 0: flags[i].append(f'di dalam poligon kampus ({c["campusName"]}) — bukan tanah dijual')
summary = {
    'nCells': len(g), 'nPopulated': int(populated.sum()), 'stepM': step,
    'nJumpPairs': len(jumps), 'nFarFromKelMedian': sum(1 for f in flags.values() if any('median kelurahan' in x for x in f)),
    'nFewComparables': sum(1 for i, f in flags.items() if any('pembanding' in x for x in f)),
    'nTanpaDense': sum(1 for f in flags.values() if any('tanpa' in x for x in f)), 'nInCampus': sum(1 for f in flags.values() if any('kampus' in x for x in f)),
    'tierShare': {t: int(sum(1 for i, c in enumerate(g) if populated[i] and c['tier'] == t)) for t in ('utama', 'lingkungan', 'gang', 'tanpa')},
    'quantilesPopulated': {str(q): round(float(np.quantile(v[populated], q)) / 1e6, 2) for q in (0.01, 0.1, 0.5, 0.9, 0.99)},
}
flagged = [dict(g[i], flags=f) for i, f in flags.items() if f and populated[i]]
json.dump({'summary': summary, 'flagged': flagged}, open(os.path.join(AUDIT_OUT, f'grid_flags_{TAG}.json'), 'w'), ensure_ascii=False)
print(json.dumps(summary, ensure_ascii=False))

# --- peta ---
def draw_kel(ax):
    for f in kel['features']:
        geom = f['geometry']; polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
        for poly in polys:
            ring = np.array(poly[0]); ax.plot(ring[:, 0], ring[:, 1], color='#444', lw=0.3, alpha=0.6)
H = iy.max() + 1; W = ix.max() + 1
img = np.full((H, W), np.nan)
for i in range(len(g)):
    if populated[i]: img[iy[i], ix[i]] = v[i] / 1e6
ext = (lng.min() - dLng / 2, lng.max() + dLng / 2, lat.min() - dLat / 2, lat.max() + dLat / 2)
fig, ax = plt.subplots(figsize=(13, 11), dpi=130)
im = ax.imshow(img, origin='lower', extent=ext, norm=LogNorm(vmin=0.8, vmax=25), cmap='viridis', interpolation='nearest')
draw_kel(ax); cb = fig.colorbar(im, ax=ax, shrink=0.7); cb.set_label('Rp jt/m² (jalan lingkungan, 150 m²)' if VAL == 'ling' else 'Rp jt/m² — harga utama yang tampil (tier hasil deteksi OSM, 150 m²)')
for c in flagged:
    if any('lompatan' in x for x in c['flags']): ax.plot(c['lng'], c['lat'], 's', ms=2.2, mfc='none', mec='red', mew=0.5)
ax.set_title(f'Estimasi model {TAG} — kisi {int(step)} m (sel berpenduduk); kotak merah = lompatan > ×1,5 ke sel tetangga')
ax.set_aspect(1 / math.cos(math.radians(7))); ax.set_xlabel('bujur'); ax.set_ylabel('lintang')
fig.tight_layout(); fig.savefig(os.path.join(AUDIT_OUT, f'estimate_map_{TAG}.png')); plt.close(fig)
# bias LOO: titik + permukaan dihaluskan (kernel 600 m, ≥ 5 iklan)
P = np.column_stack([np.array([p['lng'] for p in pts]) * KX, np.array([p['lat'] for p in pts]) * KY]); B = np.array([p['b'] for p in pts])
from scipy.spatial import cKDTree
tr = cKDTree(P); bimg = np.full((H, W), np.nan)
for i in range(len(g)):
    if not populated[i]: continue
    q = np.array([lng[i] * KX, lat[i] * KY]); idx = tr.query_ball_point(q, 900)
    if len(idx) < 5: continue
    d = np.linalg.norm(P[idx] - q, axis=1); w = np.exp(-(d / 600) ** 2)
    bimg[iy[i], ix[i]] = float((w * B[idx]).sum() / w.sum())
fig, ax = plt.subplots(figsize=(13, 11), dpi=130)
im = ax.imshow(bimg, origin='lower', extent=ext, norm=TwoSlopeNorm(vcenter=0, vmin=-0.6, vmax=0.6), cmap='RdBu_r', interpolation='nearest')
draw_kel(ax); cb = fig.colorbar(im, ax=ax, shrink=0.7); cb.set_label('bias log(estimasi/harga iklan), dihaluskan 600 m — merah = terlalu tinggi, biru = terlalu rendah')
ax.scatter([p['lng'] for p in pts], [p['lat'] for p in pts], c=B, s=3, cmap='RdBu_r', norm=TwoSlopeNorm(vcenter=0, vmin=-1, vmax=1), edgecolors='none', alpha=0.8)
ax.set_title(f'Bias leave-one-out model {TAG} (iklan berpin tepat)'); ax.set_aspect(1 / math.cos(math.radians(7)))
fig.tight_layout(); fig.savefig(os.path.join(AUDIT_OUT, f'bias_map_{TAG}.png')); plt.close(fig)
print('png ok')
