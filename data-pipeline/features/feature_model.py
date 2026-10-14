"""Model harga berbasis fitur wilayah (hedonik) — model 2026-10-8.
Target: log harga ternormalisasi (pn: bidang acuan 150 m², jalan lingkungan, setelah koreksi luas, akses, kampus, portal, waktu —
lihat build_app_data.py), jadi luas/akses/kampus TIDAK dimasukkan sebagai fitur (tidak dihitung dua kali).
mode 'eval': prediksi luar-lipatan (LOO≈20 lipatan acak, blok spasial 2 km 5 lipatan = sama dengan tests/validate-cv.test.ts,
leave-kelurahan-out 20 lipatan) untuk himpunan uji bersama → VAL_OVERRIDE json untuk harness TS.
mode 'fit': model penuh → grid 150 m + residu iklan (dipakai build_app_data.py)."""
import csv, json, math, os, sys, time, zlib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import SplineTransformer, StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import KFold, GroupKFold
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler as SP
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
# 2026-10-9: paparan rob = satu indeks gabungan (rob_exp, lihat build_features.py) masuk LINEAR dengan batasan monoton
# (koefisien ≤ 0: paparan hanya bisa menurunkan harga; disusutkan ridge). Lapisan pesisir lama (d_coast, rob_250, water_500) tidak
# dipakai lagi karena spline-nya memberi tanda yang menyesatkan di pesisir (mis. Mangunharjo "jauh dari pesisir +34%").
# shop_250 hanya untuk premi muka jalan (tidak dihitung dua kali di harga dasar).
EXCL = {'rob_250', 'd_coast', 'water_500', 'kel_rob_250', 'kec_rob_250', 'wet_500', 'gsw_500', 'shop_250'}
LIN = ['rob_exp', 'kel_rob_exp', 'kec_rob_exp']
FEATS = [n for n in SP.NAMES if n not in EXCL]
MONO = {'d_cbd': -1, 'poi_comm_1000': 1, 'd_art': -1, 'rob_exp': -1}
def SAMPLE(lat, lng): return SP.sample(lat, lng, FEATS)
class GAM:
    """spline kubik per fitur (kecuali LIN) + suku linear LIN dengan koefisien ≤ 0, satu ridge (alpha dipilih CV)."""
    def fit(self, X, y, w):
        self.lin = [FEATS.index(f) for f in LIN if f in FEATS]; self.spl = [j for j in range(X.shape[1]) if j not in self.lin]
        self.sc = StandardScaler().fit(X); Z = self.sc.transform(X)
        self.st = SplineTransformer(n_knots=5, degree=3).fit(Z[:, self.spl]); self.keep = list(self.lin)
        for _ in range(len(self.lin) + 1):
            self.rg = RidgeCV(alphas=np.logspace(-1, 3, 13)).fit(self._B(Z), y, sample_weight=w)
            cl = self.rg.coef_[-len(self.keep):] if self.keep else []
            bad = [j for j, c in zip(self.keep, cl) if c > 0]
            if not bad: break
            self.keep = [j for j in self.keep if j not in bad]
        self.alpha_ = self.rg.alpha_; return self
    def _B(self, Z): return np.hstack([self.st.transform(Z[:, self.spl])] + ([Z[:, self.keep]] if self.keep else []))
    def predict(self, X): return self.rg.predict(self._B(self.sc.transform(X)))
    def contrib(self, X):
        Z = self.sc.transform(X); B = self.st.transform(Z[:, self.spl]); k = B.shape[1] // len(self.spl); C = np.zeros(X.shape)
        for a, j in enumerate(self.spl): C[:, j] = B[:, a * k:(a + 1) * k] @ self.rg.coef_[a * k:(a + 1) * k]
        for b, j in enumerate(self.keep): C[:, j] = Z[:, j] * self.rg.coef_[B.shape[1] + b]
        return C
def i32(x):
    x &= 0xffffffff; return x - 2 ** 32 if x >= 2 ** 31 else x
def u32(x): return x & 0xffffffff
def fold(lat, lng):
    bx = math.floor(lng * 110500 / 2000); by = math.floor(lat * 110574 / 2000)
    h = i32(i32(bx * 73856093) ^ i32(by * 19349663)); h = i32(i32(h ^ (u32(h) >> 13)) * 0x5bd1e995)
    return abs(i32(h ^ (u32(h) >> 15))) % 5
def make(kind):
    if kind == 'hgb':
        return HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=30, l2_regularization=1.0,
                                             monotonic_cst=[MONO.get(f, 0) for f in FEATS], random_state=0)
    return GAM()
def fit(kind, X, y, w):
    m = make(kind)
    if kind == 'hgb': m.fit(X, y, sample_weight=w)
    else: m.fit(X, y, w)
    return m
def oof_resid(kind, X, y, w, seed=0):
    r = np.zeros(len(y))
    for tr, te in KFold(5, shuffle=True, random_state=seed).split(X):
        r[te] = y[te] - fit(kind, X[tr], y[tr], w[tr]).predict(X[te])
    return r
def wmed(v, w):
    o = np.argsort(v); c = np.cumsum(w[o]); return v[o][np.searchsorted(c, 0.5 * c[-1])]
def hav(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371008.8 * math.asin(min(1, math.sqrt(x)))
def load_rows():
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv'))) if r['loc_level'] in ('titik', 'kelurahan')]
    for r in rows:
        r['id'] = f"{r['source']}:{r['source_id']}"; r['lat'] = float(r['lat']); r['lng'] = float(r['lng']); r['y'] = math.log(float(r['pn']))
        r['w'] = 1.0 if r['loc_level'] == 'titik' else 0.5; r['fold'] = fold(r['lat'], r['lng'])
    return rows
def combine(F_te, te_pts, tr_rows, res, VARS):
    """F + residu kecamatan tersusut + residu kelurahan tersusut (+ residu lokal dalam kelurahan).
    VARS: daftar (mKec, mKel, mLoc); None = tingkat itu tidak dipakai. Mengembalikan dict nama varian → prediksi."""
    byk, byc = {}, {}
    for r, e in zip(tr_rows, res):
        byk.setdefault((r['kelurahan'], r['kecamatan']), []).append((r, e)); byc.setdefault(r['kecamatan'], []).append((r, e))
    out = {'F': []}
    for v in VARS: out[vname(v)] = []
    for f, (lat, lng, kel, kec) in zip(F_te, te_pts):
        out['F'].append(f)
        gc = byc.get(kec, []); gk = byk.get((kel, kec), [])
        for (mc, mk, ml) in VARS:
            off = 0.0
            if mc is not None and gc:
                v = np.array([e for _, e in gc]); w = np.array([r['w'] for r, _ in gc]); off += wmed(v, w) * w.sum() / (w.sum() + mc)
            if mk is not None and gk:
                v = np.array([e - off for _, e in gk]); w = np.array([r['w'] for r, _ in gk]); off += wmed(v, w) * w.sum() / (w.sum() + mk)
            if ml is not None and gk:
                loc = sorted(((hav(lat, lng, r['lat'], r['lng']), e - off, r['w']) for r, e in gk if r['loc_level'] == 'titik'), key=lambda x: x[0])[:15]
                if loc:
                    ws = np.array([ww / (1 + (d / 400) ** 2) for d, _, ww in loc]); lv = np.array([x[1] for x in loc]); ne = ws.sum() ** 2 / (ws ** 2).sum()
                    off += wmed(lv, ws) * ne / (ne + ml)
            out[vname((mc, mk, ml))].append(f + off)
    return out
def vname(v): return 'C%sK%sL%s' % tuple('-' if x is None else int(x) for x in v)
VARS = [(None, None, None), (10, 40, None), (10, 40, 10), (10, 40, 20), (10, 40, 40), (10, 40, 80)]
if __name__ == '__main__' and sys.argv[1] != 'fit':
    mode = sys.argv[1]
    rows = load_rows(); X = SAMPLE([r['lat'] for r in rows], [r['lng'] for r in rows]); y = np.array([r['y'] for r in rows]); w = np.array([r['w'] for r in rows])
    if mode == 'select':  # pilih jenis model: blok spasial 5 lipatan, F saja, iklan titik
        for kind in ('ridge', 'hgb'):
            p = np.zeros(len(y))
            for k in range(5):
                tr = np.array([r['fold'] != k for r in rows]); p[~tr] = fit(kind, X[tr], y[tr], w[tr]).predict(X[~tr])
            t = np.array([r['loc_level'] == 'titik' for r in rows]); a = np.abs(p - y)[t]
            print(kind, 'blok CV MdAPE %.1f%%' % ((math.exp(np.median(a)) - 1) * 100), 'bias %.3f' % np.median((p - y)[t]))
        sys.exit()
    kind = sys.argv[2]
    if mode == 'eval':
        ev = json.load(open(sys.argv[3])); out_path = sys.argv[4]
        Xe = SAMPLE([e['lat'] for e in ev], [e['lng'] for e in ev])
        rid = {r['id']: i for i, r in enumerate(rows)}
        res = {}
        rng = np.random.RandomState(1); rand_fold = rng.randint(0, 20, len(ev))
        kels = sorted({(e['kel'], e['kec']) for e in ev} | {(r['kelurahan'], r['kecamatan']) for r in rows})
        kfold = {k: i % 20 for i, k in enumerate(sorted(kels, key=lambda k: zlib.crc32(('|'.join(map(str, k))).encode())))}
        for mname, nf, test_of, train_ok in (
            ('loo', 20, lambda i, e: rand_fold[i], lambda r, k: True),
            ('cv', 5, lambda i, e: fold(e['lat'], e['lng']), lambda r, k: r['fold'] != k),
            ('lko', 20, lambda i, e: kfold[(e['kel'], e['kec'])], lambda r, k: kfold[(r['kelurahan'], r['kecamatan'])] != k)):
            t0 = time.time(); preds = {}
            for k in range(nf):
                te = [i for i, e in enumerate(ev) if test_of(i, e) == k]
                if not te: continue
                ban = set()
                for i in te: ban |= set(ev[i]['group']) | {ev[i]['id']}
                tr = [j for j, r in enumerate(rows) if train_ok(r, k) and r['id'] not in ban]
                m = fit(kind, X[tr], y[tr], w[tr]); r_oof = oof_resid(kind, X[tr], y[tr], w[tr])
                F_te = m.predict(Xe[te])
                c = combine(F_te, [(ev[i]['lat'], ev[i]['lng'], ev[i]['kel'], ev[i]['kec']) for i in te], [rows[j] for j in tr], r_oof, VARS)
                for v, ps in c.items():
                    for i, p in zip(te, ps): preds.setdefault(v, {})[ev[i]['id']] = float(p)
            res[mname] = preds; print(mname, 'done', round(time.time() - t0), 's', flush=True)
        json.dump(res, open(out_path, 'w'))

# ---------------- mode 'fit': model produksi ----------------
GROUPS = [  # (kunci, label bila keadaan "tinggi", label bila "rendah", fitur, fitur keadaan, orientasi, arah harga yang wajar)
    # label menggambarkan KEADAAN lokasi (dibanding rata-rata lokasi iklan), bukan tanda kontribusi. Bila arah harga yang wajar
    # diketahui (mis. paparan rob hanya menurunkan harga) dan tanda kontribusi bertentangan, kontribusi tidak ditampilkan.
    ('padat', 'kepadatan bangunan tinggi', 'kepadatan bangunan rendah', ['built_250', 'built_1000', 'built_2500', 'bld_250', 'roaddens_500', 'kel_built_250', 'kec_built_250', 'kel_bld_250', 'kec_bld_250', 'kel_roaddens_500', 'kec_roaddens_500'], 'built_1000', 1, 1),
    ('pusat', 'dekat pusat kota', 'jauh dari pusat kota', ['d_cbd'], 'd_cbd', -1, 1),
    ('jalan', 'dekat jalan besar/tol', 'jauh dari jalan besar/tol', ['d_art', 'd_sec', 'd_toll', 'd_drive'], 'd_art', -1, 1),
    ('belanja', 'banyak toko/pasar sekitar', 'sedikit toko/pasar sekitar', ['poi_comm_1000', 'poi_comm_3000', 'd_mall', 'd_market', 'comlu_500', 'kel_poi_comm_1000', 'kec_poi_comm_1000'], 'poi_comm_3000', 1, 1),
    ('fasilitas', 'banyak sekolah & faskes', 'sedikit sekolah & faskes', ['school_1000', 'health_1500'], 'school_1000', 1, 0),
    ('lereng', 'lereng curam', 'lahan landai', ['slope_250', 'kel_slope_250', 'kec_slope_250'], 'slope_250', 1, -1),
    ('tinggi', 'dataran lebih tinggi', 'dataran rendah', ['elev', 'kel_elev', 'kec_elev'], 'elev', 1, 0),
    ('rob', 'rawan rob / genangan pesisir', 'di luar zona rob', ['rob_exp', 'kel_rob_exp', 'kec_rob_exp'], 'rob_exp', 1, -1),
    ('sungai', 'dekat sungai', 'jauh dari sungai', ['d_river'], 'd_river', -1, 0),
    ('industri', 'dekat kawasan industri/pelabuhan', 'jauh dari kawasan industri', ['ind_500', 'kel_ind_500', 'kec_ind_500'], 'ind_500', 1, 0),
    ('hijau', 'banyak pohon/sawah sekitar', 'sedikit lahan hijau', ['tree_500', 'crop_500', 'grass_500', 'kel_tree_500', 'kec_tree_500', 'kel_crop_500', 'kec_crop_500'], 'tree_500', 1, 0),
]
def sides(Xs, Xref):
    """keadaan per kelompok (+1 'tinggi' / −1 'rendah') dibanding median lokasi iklan"""
    return np.stack([np.where((Xs[:, FEATS.index(sf)] - np.median(Xref[:, FEATS.index(sf)])) * o >= 0, 1, -1) for _, _, _, _, sf, o, _ in GROUPS], axis=1)
def audit_labels(Cgg, S):
    """tekan kontribusi yang tandanya bertentangan dengan makna keadaan; kembalikan (C tampil, jumlah ditekan per kelompok)"""
    C = Cgg.copy(); sup = {}
    for g, (k, *_r, ex) in enumerate(GROUPS):
        bad = (ex != 0) & (np.sign(C[:, g]) * S[:, g] * ex < 0) & (np.abs(C[:, g]) >= math.log(1.02))
        C[bad, g] = 0; sup[k] = int(bad.sum())
    return C, sup
M_KEC, M_KEL = 10, 40
def contributions(m, X):
    """kontribusi aditif per fitur (model spline + ridge): basis_j · koef_j, dipusatkan pada rata-rata iklan."""
    return m.contrib(X)
def fit_main(out_dir, pub_dir):
    rows = load_rows(); X = SAMPLE([r['lat'] for r in rows], [r['lng'] for r in rows]); y = np.array([r['y'] for r in rows]); w = np.array([r['w'] for r in rows])
    m = fit('ridge', X, y, w); r_oof = oof_resid('ridge', X, y, w)
    C = contributions(m, X); cmean = C.mean(axis=0)
    # offset kecamatan & kelurahan dari residu luar-lipatan (sama dengan combine() varian C10K40)
    byc, byk = {}, {}
    for r, e in zip(rows, r_oof): byc.setdefault(r['kecamatan'], []).append((r, e)); byk.setdefault((r['kelurahan'], r['kecamatan']), []).append((r, e))
    def offs(kel, kec, excl=None):
        gc = [(r, e) for r, e in byc.get(kec, []) if r is not excl]; gk = [(r, e) for r, e in byk.get((kel, kec), []) if r is not excl]
        oc = ok = 0.0; ec = ek = 0.0
        if gc:
            v = np.array([e for _, e in gc]); ww = np.array([r['w'] for r, _ in gc]); ec = ww.sum(); oc = wmed(v, ww) * ec / (ec + M_KEC)
        if gk:
            v = np.array([e - oc for _, e in gk]); ww = np.array([r['w'] for r, _ in gk]); ek = ww.sum(); ok = wmed(v, ww) * ek / (ek + M_KEL)
        return oc, ok, ec, ek, len(gk), len(gc)
    city_sd = 1.4826 * float(np.median(np.abs(r_oof - np.median(r_oof))))
    # prediksi tiap iklan (luar-lipatan F + offset tanpa iklan itu) → build_app_data.py (validasi & kalibrasi faktor)
    F_oof = y - r_oof
    with open(os.path.join(out_dir, 'feature_preds.csv'), 'w', newline='') as f:
        wr = csv.writer(f); wr.writerow(['id', 'mu', 'F', 'kecOff', 'kelOff'])
        for i, r in enumerate(rows):
            oc, ok, *_ = offs(r['kelurahan'], r['kecamatan'], r); wr.writerow([r['id'], round(F_oof[i] + oc + ok, 5), round(F_oof[i], 5), round(oc, 5), round(ok, 5)])
    # semua iklan (termasuk pencilan) berlokasi: F model penuh + offset — untuk koridor & audit
    allr = [r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_all.csv'))) if r.get('lat') and r.get('lng')]
    if allr:
        Xa = SAMPLE([float(r['lat']) for r in allr], [float(r['lng']) for r in allr]); Fa = m.predict(Xa)
        with open(os.path.join(out_dir, 'feature_preds_all.csv'), 'w', newline='') as f:
            wr = csv.writer(f); wr.writerow(['id', 'mu', 'F'])
            for r, fa in zip(allr, Fa):
                oc, ok, *_ = offs(r.get('kelurahan', ''), r.get('kecamatan', '')); wr.writerow([f"{r['source']}:{r['source_id']}", round(fa + oc + ok, 5), round(fa, 5)])
    # grid 150 m di dalam kota
    kg = json.load(open(os.path.join(pub_dir, 'kelurahan.geojson')))['features']
    lab = SP._Z['_kel_label']
    G = 150.0; dLat = G / 110574; dLng = G / (111320 * math.cos(math.radians(-7.02)))
    nx = int((SP.W + SP.NX * SP.DX - SP.W) / dLng); ny = int(SP.NY * SP.DY / dLat)
    gi, gj = np.mgrid[0:ny, 0:nx]; glat = SP.N - (gi.ravel() + 0.5) * dLat; glng = SP.W + (gj.ravel() + 0.5) * dLng
    li, lj = SP.idx(glat, glng); gl = lab[li, lj]; inside = gl > 0
    Xg = SAMPLE(glat[inside], glng[inside]); Fg = m.predict(Xg); Cg = contributions(m, Xg) - cmean
    built = SP.raw(glat[inside], glng[inside], 'built_250')
    gidx = np.nonzero(inside)[0]; glab = gl[inside]
    groups = [(k, lp, ln, [FEATS.index(f) for f in fs if f in FEATS]) for k, lp, ln, fs, *_ in GROUPS]
    Cgg = np.stack([Cg[:, ix].sum(axis=1) for _, _, _, ix in groups], axis=1)
    Sg = sides(Xg, X); Cgg, suppressed = audit_labels(Cgg, Sg)
    print('label audit — sel grid ditekan per kelompok:', suppressed, 'dari', len(Xg))
    kel_off = {}
    zones = []
    for i, f in enumerate(kg):
        nm, kc = f['properties']['name'], f['properties']['kecamatan']
        oc, ok, ec, ek, nk, ncc = offs(nm, kc); kel_off[(nm, kc)] = (oc, ok)
        sel = glab == i + 1
        if sel.any():
            vv = Fg[sel]; ww = built[sel] + 0.05; o = np.argsort(vv); cw = np.cumsum(ww[o]); fmed = float(vv[o][np.searchsorted(cw, 0.5 * cw[-1])])
            p25 = float(vv[o][np.searchsorted(cw, 0.25 * cw[-1])]); p75 = float(vv[o][np.searchsorted(cw, 0.75 * cw[-1])])
            cmed = [float(np.average(Cgg[sel][:, g], weights=ww)) for g in range(len(groups))]
            smed = [int(1 if np.average(Sg[sel][:, g], weights=ww) >= 0 else -1) for g in range(len(groups))]
            for g, (*_r, ex) in enumerate(GROUPS):
                if ex and cmed[g] * smed[g] * ex < 0: cmed[g] = 0.0
        else:
            fmed = p25 = p75 = float(np.median(y)); cmed = [0.0] * len(groups); smed = [1] * len(groups)
        gk = [e - oc for r, e in byk.get((nm, kc), [])]
        sd = city_sd if len(gk) < 3 else min(1, len(gk) / 6) * max(0.25, 1.4826 * float(np.median(np.abs(np.array(gk) - np.median(gk))))) + (1 - min(1, len(gk) / 6)) * city_sd
        zones.append({'name': nm, 'kec': kc, 'F': round(fmed, 4), 'Fp25': round(p25, 4), 'Fp75': round(p75, 4), 'kecOff': round(oc, 4), 'kelOff': round(ok, 4), 'effKec': round(ec, 1), 'effKel': round(ek, 1),
                      'n': nk, 'nKec': ncc, 'sdLog': round(sd, 3), 'contrib': [round(c, 3) for c in cmed], 'side': smed})
    grid = {'lat0': SP.N, 'lng0': SP.W, 'dLat': dLat, 'dLng': dLng, 'nx': nx, 'ny': ny,
            'groups': [{'key': k, 'pos': lp, 'neg': ln} for k, lp, ln, _ in groups],
            'idx': gidx.tolist(), 'f': np.round(Fg * 1000).astype(int).tolist(), 'c': np.round(Cgg * 1000).astype(int).T.tolist(), 's': [''.join('1' if v > 0 else '0' for v in row) for row in Sg.T]}
    json.dump(grid, open(os.path.join(pub_dir, 'feature-grid.json'), 'w'), separators=(',', ':'))
    # efek terukur: kontribusi per kelompok di antara iklan (p10–p90) & efek parsial fitur utama (p10 → p90)
    Cl = C - cmean
    eff = {'labelAudit': {'gridCells': int(len(Xg)), 'suppressed': suppressed}, 'linearMonotone': [FEATS[j] for j in m.keep], 'robCoef': [round(float(c), 4) for c in m.rg.coef_[-len(m.keep):]] if m.keep else [], 'groups': [], 'features': [], 'cityResidSd': round(city_sd, 3), 'n': len(rows), 'alpha': float(m.alpha_), 'mKec': M_KEC, 'mKel': M_KEL}
    for k, lp, ln, ix in groups:
        g = Cl[:, ix].sum(axis=1); eff['groups'].append({'key': k, 'pos': lp, 'neg': ln, 'p10Pct': round((math.exp(np.percentile(g, 10)) - 1) * 100, 1), 'p90Pct': round((math.exp(np.percentile(g, 90)) - 1) * 100, 1)})
    for j, fname in enumerate(FEATS):
        lo, hi = np.percentile(X[:, j], [10, 90]); xs = np.tile(np.median(X, axis=0), (2, 1)); xs[0, j] = lo; xs[1, j] = hi
        d = m.predict(xs); rlo, rhi = (float(SP.raw.__globals__['np'].percentile(SP.LAYERS[fname][SP.idx([r['lat'] for r in rows], [r['lng'] for r in rows])], q)) for q in (10, 90))
        eff['features'].append({'feature': fname, 'p10': round(rlo, 3), 'p90': round(rhi, 3), 'effectPct': round((math.exp(d[1] - d[0]) - 1) * 100, 1)})
    json.dump({'zones': zones, 'effects': eff}, open(os.path.join(out_dir, 'feature_model.json'), 'w'), ensure_ascii=False, indent=0)
    print('fit: n', len(rows), 'alpha', eff['alpha'], 'city sd', round(city_sd, 3), 'grid cells', len(gidx), 'zones', len(zones))
if __name__ == '__main__' and sys.argv[1] == 'fit':
    fit_main(os.path.join(ROOT, 'data'), os.path.join(ROOT, 'public/data'))
