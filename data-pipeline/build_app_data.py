"""Bangun data aplikasi dari data/listings_clean.csv:
 1. Akses OSM untuk tiap iklan (port src/lib/access.ts) — hanya informasi & analisis pendukung.
 2. Regresi hedonik (efek tetap kelurahan): log(harga/m²) ~ log(luas/acuan) + akses (teks) + komersial + sumber + tren waktu.
 3. Faktor akses akhir = gabungan bobot-presisi antara koefisien data dan prior rujukan (dicatat di model).
 3b. Premi muka jalan utama di pusat kota: utama × exp(b · exp(−d/L)), d = jarak ke Simpang Lima;
     L dipilih dari kisi lewat galat regresi, b disusutkan ke 0 (prior N(0, 0,5²)).
 3c. Kedekatan kampus (poligon OSM amenity=university/college ≥ 2 ha): pita jarak 0–500 / 500–1000 / 1000–2000 m
     vs > 2 km, diestimasi bersama efek tetap kelurahan (jadi hanya selisih DI DALAM kelurahan), disusutkan ke 0.
 4. Normalisasi tiap iklan ke bidang acuan (luas acuan, akses jalan lingkungan, per tanggal acuan).
 5. Statistik kelurahan/kecamatan, validasi leave-one-out, tulis public/data/dataset.json & data/model_report.json.
"""
import csv, json, math, os, statistics, datetime
from collections import Counter, defaultdict
import numpy as np
from common import OUT, PUB, RAW
from osm_access import detect

REF_AREA = 150
AS_OF = datetime.date.today().strftime('%Y-%m')
TIERS = ['utama', 'lingkungan', 'gang', 'tanpa']
CBD_CENTER = (-6.990464, 110.422918)  # Simpang Lima
CBD_L_GRID = [750, 1000, 1500, 2000, 3000]
CBD_PRIOR_SD = 0.5
CAMPUS_BANDS = [500, 1000, 2000]
CAMPUS_MIN_HA = 2.0
CAMPUS_PRIOR_SD = 0.3
# Kurva luas bidang: kelas luas (m²) sebagai dummy dalam regresi efek tetap kelurahan (bukan elastisitas log-linear tunggal);
# kelas acuan 125–175 m² (memuat luas acuan 150 m²). Koefisien disusutkan ke 0 (prior N(0, 0,3²)).
SIZE_EDGES = [0, 75, 100, 125, 175, 250, 400, 700, 1500, float('inf')]
SIZE_REF_BIN = 3
SIZE_PRIOR_SD = 0.3
def size_bin(a):
    for i in range(len(SIZE_EDGES) - 1):
        if SIZE_EDGES[i] <= a < SIZE_EDGES[i + 1]: return i
    return len(SIZE_EDGES) - 2
from shapely.geometry import Polygon as _Poly, Point as _Pt
from shapely.ops import unary_union as _union
_camp_all = json.load(open(os.path.join(OUT, 'campus.json')))['campuses']
CAMPUSES = [c for c in _camp_all if c['areaHa'] >= CAMPUS_MIN_HA and 'kepolisian' not in c['name'].lower()]
_camp_geom = _union([_Poly([(lng, lat) for lat, lng in ring]) for c in CAMPUSES for ring in c['rings'] if len(ring) >= 4])
def campus_dist_m(lat, lng):
    # derajat → meter (lintang ±7°: 1° bujur ≈ 110,5 km); cukup untuk pita 500 m
    g = _camp_geom
    p = _Pt(lng, lat)
    if g.contains(p): return 0.0
    from shapely.ops import nearest_points
    q = nearest_points(g, p)[0]
    return math.hypot((q.y - lat) * 110574, (q.x - lng) * 110500)
def campus_band(d):
    for i, lim in enumerate(CAMPUS_BANDS):
        if d < lim: return i
    return None
# Prior rujukan (log-normal): median & sd log. Tidak ada angka baku nasional; DJKN/BPN (Juknis Penilaian Tanah 2023)
# memperlakukan aksesibilitas & lebar jalan sebagai faktor penyesuaian yang ditetapkan dari data pasar lokal.
PRIORS = {
    'utama': (1.30, 0.20, 'Muka jalan utama/kolektor umumnya dihargai lebih tinggi (nilai komersial).'),
    'lingkungan': (1.00, 0.0, 'Acuan: jalan lingkungan yang bisa dilalui mobil.'),
    'gang': (0.80, 0.12, 'Gang sempit/akses motor: pembangunan & logistik terbatas.'),
    'tanpa': (0.55, 0.15, 'Tanah terkurung: perlu membeli/menyewa jalan keluar (KUH Perdata ps. 667 memberi hak menuntut jalan keluar dengan ganti rugi).'),
}
LABELS = {
    'utama': ('Pinggir jalan utama', 'Jalan utama', 'Bidang berbatasan langsung dengan jalan raya/arteri/kolektor (mobil & truk, nilai komersial).'),
    'lingkungan': ('Jalan lingkungan (mobil masuk)', 'Jalan lingkungan', 'Ada jalan umum yang bisa dilalui mobil, mis. jalan perumahan/kampung lebar ≥ 3 m.'),
    'gang': ('Gang sempit / akses motor', 'Gang sempit', 'Hanya gang/jalan setapak (lebar < 3 m) atau bidang dalam yang perlu jalan masuk.'),
    'tanpa': ('Tanpa akses jalan (terkurung)', 'Tanpa akses', 'Tidak ada jalan/gang umum ke bidang; harus lewat tanah orang lain.'),
}

rows = list(csv.DictReader(open(os.path.join(OUT, 'listings_clean.csv'))))
for r in rows:
    r['lat'] = float(r['lat']); r['lng'] = float(r['lng']); r['ppm'] = float(r['ppm']); r['area_m2'] = float(r['area_m2'])
    r['exact'] = int(r['exact'])
    r['kec_only'] = r['loc_level'] == 'kecamatan'
    t, ddrv, dut = detect(r['lat'], r['lng'])
    p_ = math.pi / 180
    _x = math.sin((CBD_CENTER[0] - r['lat']) * p_ / 2) ** 2 + math.cos(r['lat'] * p_) * math.cos(CBD_CENTER[0] * p_) * math.sin((CBD_CENTER[1] - r['lng']) * p_ / 2) ** 2
    r['d_cbd'] = 2 * 6371008.8 * math.asin(math.sqrt(_x))
    r['d_campus'] = campus_dist_m(r['lat'], r['lng']); r['campus_band'] = campus_band(r['d_campus'])
    r['osm_tier'] = t; r['osm_drive_m'] = ddrv; r['osm_main_m'] = dut
    d = r['date'][:7] if r['date'] else AS_OF
    y, m = map(int, d.split('-')); ya, ma = map(int, AS_OF.split('-'))
    r['age_y'] = max(0, ((ya - y) * 12 + (ma - m)) / 12)
print('rows', len(rows), Counter(r['loc_level'] for r in rows))
# Iklan yang lokasinya hanya diketahui sampai kecamatan tidak dipakai untuk efek tetap kelurahan,
# statistik kelurahan, maupun pembanding terdekat — hanya untuk statistik kecamatan & kota.
loc_rows = [r for r in rows if not r['kec_only']]
# Tingkat harga wilayah (median harga/m² mentah kelurahan; kecamatan bila kelurahan < 3 iklan) — moderator kurva luas:
# di wilayah murah bidang luas = lahan mentah (diskon), di wilayah mahal bidang luas bernilai pengembangan (premi).
_kraw = defaultdict(list); _craw = defaultdict(list)
for r in loc_rows: _kraw[r['kelurahan']].append(r['ppm'])
for r in rows: _craw[r['kecamatan']].append(r['ppm'])
def area_level(kel, kec):
    if kel and len(_kraw.get(kel, [])) >= 3: return statistics.median(_kraw[kel])
    return statistics.median(_craw[kec]) if _craw.get(kec) else None
for r in rows: r['area_level'] = area_level(r['kelurahan'] if not r['kec_only'] else '', r['kecamatan'])
_lv = sorted(math.log(r['area_level']) for r in loc_rows)
SIZE_Z0 = _lv[len(_lv) // 2]; SIZE_ZLO = _lv[int(0.05 * len(_lv))] - SIZE_Z0; # Moderasi hanya di bawah tingkat median (z ≤ 0): di wilayah mahal, premi bidang luas kemungkinan tercampur nilai komersial/muka
# jalan yang tidak teramati, jadi tidak diekstrapolasi. Varian dipilih lewat leave-one-out (analysis/size_variants.py):
# SIZE_INTERACT=0 → tanpa moderasi; SIZE_ZHI=p95 → moderasi penuh.
SIZE_INTERACT = os.environ.get('SIZE_INTERACT', '1') == '1'
_zhi = os.environ.get('SIZE_ZHI', '0')
SIZE_ZHI = (_lv[int(0.95 * len(_lv))] - SIZE_Z0) if _zhi == 'p95' else float(_zhi)
def size_z(level):
    if not SIZE_INTERACT: return 0.0
    return 0.0 if not level else max(SIZE_ZLO, min(SIZE_ZHI, math.log(level) - SIZE_Z0))
for r in rows: r['size_z'] = size_z(r['area_level'])

def regress(rows, tier_key, label, cbd_L=None, size_mode='bins'):
    kels = sorted(set(r['kelurahan'] for r in rows))
    kidx = {k: i for i, k in enumerate(kels)}
    tiers_nb = ['utama', 'gang', 'tanpa', 'unknown']
    X = []; y = []
    for r in rows:
        t = r[tier_key] or 'unknown'
        fe = [0.0] * len(kels); fe[kidx[r['kelurahan']]] = 1.0
        if size_mode == 'bins':
            sb = size_bin(r['area_m2']); xs = [1.0 if sb == i else 0.0 for i in range(len(SIZE_EDGES) - 1) if i != SIZE_REF_BIN]
            xs = xs + [v * r['size_z'] for v in xs]
        else:
            xs = [math.log(r['area_m2'] / REF_AREA)]
        x = fe + xs + [1.0 if t == tt else 0.0 for tt in tiers_nb] + [1.0 if r['subtype'] == 'komersial' else 0.0, 1.0 if r['source'] == 'lamudi' else 0.0, -r['age_y']]
        x.append(math.exp(-r['d_cbd'] / cbd_L) if (cbd_L and t == 'utama') else 0.0)
        x += [1.0 if r['campus_band'] == i else 0.0 for i in range(len(CAMPUS_BANDS))]
        X.append(x); y.append(math.log(r['ppm']))
    X = np.array(X); y = np.array(y)
    # buang kolom tier yang tidak ada datanya
    keep = [j for j in range(X.shape[1]) if X[:, j].any()]
    size_names = ([f'size:{i}' for i in range(len(SIZE_EDGES) - 1) if i != SIZE_REF_BIN] + [f'sizez:{i}' for i in range(len(SIZE_EDGES) - 1) if i != SIZE_REF_BIN]) if size_mode == 'bins' else ['log_area']
    names = [f'kel:{k}' for k in kels] + size_names + [f'tier:{t}' for t in tiers_nb] + ['komersial', 'src_lamudi', 'trend_per_year', 'utama_cbd'] + [f'campus_{lim}' for lim in CAMPUS_BANDS]
    Xk = X[:, keep]; nk = [names[j] for j in keep]
    beta, *_ = np.linalg.lstsq(Xk, y, rcond=None)
    res = y - Xk @ beta
    dof = max(1, len(y) - Xk.shape[1])
    s2 = float(res @ res) / dof
    cov = s2 * np.linalg.pinv(Xk.T @ Xk)
    se = np.sqrt(np.diag(cov))
    # R² within (setelah efek tetap)
    yk = y.copy(); grp = defaultdict(list)
    for i, r in enumerate(rows): grp[r['kelurahan']].append(i)
    yd = np.array([y[i] - np.mean([y[j] for j in grp[rows[i]['kelurahan']]]) for i in range(len(y))])
    r2w = 1 - float(res @ res) / float(yd @ yd) if float(yd @ yd) > 0 else 0
    out = {n: (float(b), float(s)) for n, b, s in zip(nk, beta, se) if not n.startswith('kel:')}
    counts = Counter(r[tier_key] or 'unknown' for r in rows)
    print(f'--- regresi {label}: n={len(y)} σ={math.sqrt(s2):.3f} R²within={r2w:.3f}')
    for k, (b, s) in out.items():
        print(f'   {k:16s} {b:+.3f} ± {s:.3f}  (×{math.exp(b):.2f})  n={counts.get(k.split(":")[1], "") if k.startswith("tier:") else ""}')
    return out, counts, len(y), r2w, math.sqrt(s2), beta, nk, float(res @ res)

# pilih L (skala peluruhan premi pusat kota) dengan jumlah kuadrat sisa terkecil
cbd_fits = {}
for L in CBD_L_GRID:
    o = regress(loc_rows, 'access_tier', f'akses teks + premi utama pusat kota L={L}', cbd_L=L)
    cbd_fits[L] = o
CBD_L = min(cbd_fits, key=lambda L: cbd_fits[L][7])
coef_txt, cnt_txt, n_reg, r2w, sigma, _, _, _ = cbd_fits[CBD_L]
cbd_b, cbd_se = coef_txt.get('utama_cbd', (0.0, 1.0))
cbd_shr = CBD_PRIOR_SD ** 2 / (CBD_PRIOR_SD ** 2 + cbd_se ** 2)
cbd_used = cbd_b * cbd_shr
n_utama_cbd = sum(1 for r in loc_rows if r['access_tier'] == 'utama' and r['d_cbd'] < 3 * CBD_L)
print(f'premi utama pusat kota: L={CBD_L} b={cbd_b:.3f}±{cbd_se:.3f} → dipakai {cbd_used:.3f} (×{math.exp(cbd_used):.2f} di Simpang Lima), n utama ≤3L={n_utama_cbd}',
      {L: round(v[7], 2) for L, v in cbd_fits.items()})
_, _, _, _, _, _, _, rss_flat = regress(loc_rows, 'access_tier', 'tanpa premi pusat kota (pembanding)')
campus_coef = []
for i, lim in enumerate(CAMPUS_BANDS):
    b, se = coef_txt.get(f'campus_{lim}', (0.0, 1.0))
    shr = CAMPUS_PRIOR_SD ** 2 / (CAMPUS_PRIOR_SD ** 2 + se ** 2)
    campus_coef.append({'maxM': lim, 'minM': CAMPUS_BANDS[i - 1] if i else 0, 'coefRaw': round(b, 4), 'se': round(se, 4), 'coef': round(b * shr, 4),
                        'n': sum(1 for r in loc_rows if r['campus_band'] == i)})
print('kampus', campus_coef)
def campus_factor(d):
    i = campus_band(d)
    return math.exp(campus_coef[i]['coef']) if i is not None else 1.0
def cbd_factor(d):
    return math.exp(cbd_used * math.exp(-d / CBD_L))
exact_rows = [r for r in rows if r['exact'] == 1]
coef_osm, cnt_osm, n_osm, r2w_osm, _, _, _, _ = regress(exact_rows, 'osm_tier', 'akses dari OSM (iklan berkoordinat tepat)')

def combine(t):
    pm, psd, why = PRIORS[t]
    if t == 'lingkungan':
        return 1.0, 1.0, 1.0, 'data', None, cnt_txt.get('lingkungan', 0)
    ev = []
    if f'tier:{t}' in coef_txt and cnt_txt.get(t, 0) >= 5:
        ev.append(coef_txt[f'tier:{t}'])
    # Catatan: koefisien akses-OSM (iklan berkoordinat tepat) TIDAK dipakai untuk faktor — pin iklan sering diletakkan
    # di jalan terdekat/titik perumahan, bukan di bidang, sehingga kelas OSM per iklan bias. Hanya dilaporkan sebagai diagnostik.
    lp = math.log(pm); wp = 1 / psd ** 2
    num = lp * wp; den = wp
    for b, s in ev:
        s = max(s, 0.05); num += b / s ** 2; den += 1 / s ** 2
    post = num / den; post_sd = math.sqrt(1 / den)
    data_share = 1 - wp / den
    basis = 'prior' if data_share < 0.25 else ('data' if data_share > 0.75 else 'campuran')
    data_factor = None
    if ev:
        dn = sum(b / max(s, 0.05) ** 2 for b, s in ev); dd = sum(1 / max(s, 0.05) ** 2 for b, s in ev)
        data_factor = round(math.exp(dn / dd), 3)
    n = cnt_txt.get(t, 0)
    return math.exp(post), math.exp(post - 1.96 * post_sd), math.exp(post + 1.96 * post_sd), basis, data_factor, n

tiers = {}
for t in TIERS:
    f, lo, hi, basis, dfac, n = combine(t)
    tiers[t] = {'label': LABELS[t][0], 'short': LABELS[t][1], 'desc': LABELS[t][2], 'factor': round(f, 3), 'lo': round(lo, 3), 'hi': round(hi, 3),
                'n': n, 'nOsm': cnt_osm.get(t, 0), 'basis': basis, 'dataFactor': dfac, 'prior': PRIORS[t][0], 'priorNote': PRIORS[t][2]}
    print('tier', t, tiers[t])

# kurva luas: titik simpul = median luas tiap kelas; koefisien kelas a + c·z (z = log tingkat harga wilayah, terpusat), disusutkan; acuan 0
size_curve = []
for i in range(len(SIZE_EDGES) - 1):
    areas = [r['area_m2'] for r in loc_rows if size_bin(r['area_m2']) == i]
    if not areas: continue
    if i == SIZE_REF_BIN:
        b, se, c, sec = 0.0, 0.0, 0.0, 0.0
    else:
        b, se = coef_txt.get(f'size:{i}', (0.0, 1.0)); c, sec = coef_txt.get(f'sizez:{i}', (0.0, 1.0))
    shr = SIZE_PRIOR_SD ** 2 / (SIZE_PRIOR_SD ** 2 + se ** 2) if se else 1.0
    shz = SIZE_PRIOR_SD ** 2 / (SIZE_PRIOR_SD ** 2 + sec ** 2) if sec else 1.0
    size_curve.append({'minM2': SIZE_EDGES[i], 'maxM2': None if SIZE_EDGES[i + 1] == float('inf') else SIZE_EDGES[i + 1],
                       'area': round(statistics.median(areas)), 'coefRaw': round(b, 4), 'se': round(se, 4), 'coef': b * shr,
                       'slopeRaw': round(c, 4), 'slopeSE': round(sec, 4), 'slope': c * shz, 'n': len(areas)})
def _interp(a, key):
    a = max(30, min(50000, a)); la = math.log(a)
    ks = [(math.log(k['area']), k[key]) for k in size_curve]
    if la <= ks[0][0]: return ks[0][1]
    if la >= ks[-1][0]: return ks[-1][1]
    for (x0, y0), (x1, y1) in zip(ks, ks[1:]):
        if x0 <= la <= x1: return y0 + (y1 - y0) * (la - x0) / (x1 - x0)
_off_a = _interp(REF_AREA, 'coef'); _off_c = _interp(REF_AREA, 'slope')
for k in size_curve:
    k['coef'] = round(k['coef'] - _off_a, 4); k['slope'] = round(k['slope'] - _off_c, 4)  # faktor(150 m²) = 1 untuk semua z
def size_factor(a, z=0.0):
    return math.exp(_interp(a, 'coef') + _interp(a, 'slope') * z)
print('kurva luas', [(k['area'], k['coef'], k['slope'], k['n']) for k in size_curve], 'z0', round(math.exp(SIZE_Z0)), 'z range', round(SIZE_ZLO, 2), round(SIZE_ZHI, 2))
# pembanding: elastisitas log-linear tunggal (model sebelumnya), hanya dilaporkan
_lin = regress(loc_rows, 'access_tier', 'luas log-linear (pembanding)', cbd_L=CBD_L, size_mode='linear')
beta_size, se_size = _lin[0]['log_area']
size_rss = {'bins': round(coef_fit_rss, 2) if (coef_fit_rss := cbd_fits[CBD_L][7]) else None, 'linear': round(_lin[7], 2)}
print('rss kurva vs linear', size_rss)
trend, se_trend = coef_txt.get('trend_per_year', (0.0, 0.0))
trend_used = max(0.0, min(0.12, trend))  # batasi: 0–12%/tahun
unknown_b = coef_txt.get('tier:unknown', (0.0, 0.0))[0]
komersial_b = coef_txt.get('komersial', (0.0, 0.0))[0]
print('size elasticity', beta_size, 'trend', trend, '→ used', trend_used)

src_b = coef_txt.get('src_lamudi', (0.0, 0.0))[0]
share_lam = sum(1 for r in loc_rows if r['source'] == 'lamudi') / len(loc_rows)
# selisih tingkat harga antarsumber di kelurahan yang sama dinetralkan ke rata-rata gabungan (bukan memilih satu sumber 'benar')
SRC_ADJ = {'lamudi': math.exp(-src_b * (1 - share_lam)), 'pinhome': math.exp(src_b * share_lam)}
print('source effect lamudi vs pinhome ×', round(math.exp(src_b), 3), 'adj', SRC_ADJ)

def normalize(r):
    t = r['access_tier']
    tf = tiers[t]['factor'] if t else math.exp(unknown_b)
    if t == 'utama':
        tf *= cbd_factor(r['d_cbd'])
    sf = size_factor(r['area_m2'], r['size_z'])
    tr = math.exp(trend_used * r['age_y'])
    return r['ppm'] / (tf * sf * campus_factor(r['d_campus'])) * tr * SRC_ADJ[r['source']]

for r in rows:
    r['pn'] = normalize(r)

# ---------- statistik wilayah ----------
def qs(v):
    v = sorted(v)
    def q(p):
        k = (len(v) - 1) * p; f = math.floor(k); c = math.ceil(k)
        return v[f] if f == c else v[f] + (v[c] - v[f]) * (k - f)
    return q(0.25), q(0.5), q(0.75)

def area_stats(key):
    g = defaultdict(list)
    for r in (loc_rows if key == 'kelurahan' else rows): g[(r[key], r['kecamatan'] if key == 'kelurahan' else r['kecamatan'])].append(r)
    out = []
    for (name, kec), rs in g.items():
        p25, med, p75 = qs([r['pn'] for r in rs])
        out.append({'name': name, 'kec': kec, 'n': len(rs), 'nExact': sum(r['exact'] for r in rs), 'median': round(med), 'p25': round(p25), 'p75': round(p75),
                    'medianRaw': round(statistics.median([r['ppm'] for r in rs])), 'dateMin': min(r['date'][:7] for r in rs), 'dateMax': max(r['date'][:7] for r in rs),
                    'sources': dict(Counter(r['source'] for r in rs))})
    return sorted(out, key=lambda s: -s['median'])

kel_stats = area_stats('kelurahan'); kec_stats = area_stats('kecamatan')
city_med = statistics.median([r['pn'] for r in rows])
kmed = {s['name']: math.log(s['median']) for s in kel_stats}
resid = [abs(math.log(r['pn']) - kmed[r['kelurahan']]) for r in loc_rows]
city_spread = 1.4826 * statistics.median(resid)
print('city median pn', round(city_med), 'local spread', round(city_spread, 3))

# ---------- validasi leave-one-out (port estimator src/lib/estimate.ts) ----------
RADII = [400, 600, 800, 1000, 1500, 2000, 3000]
SMOOTH_PRIOR_BW = 1500  # m; diuji dengan validasi silang blok spasial (analysis/audit/cv_prior_hl.py)
MIN_EFF = 10  # sama dengan src/lib/estimate.ts (dipilih lewat uji leave-one-out, lihat analysis/loo_variants.py)
def hav(a, b, c, d):
    R = 6371008.8; p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * R * math.asin(min(1, math.sqrt(x)))
def wq(vals, ws, q):
    idx = sorted(range(len(vals)), key=lambda i: vals[i]); tot = sum(ws); acc = 0
    for i in idx:
        acc += ws[i]
        if acc >= q * tot: return vals[i]
    return vals[idx[-1]]
kel_by = defaultdict(list)
for r in loc_rows: kel_by[r['kelurahan']].append(r)
kec_by = defaultdict(list)
for r in rows: kec_by[r['kecamatan']].append(r)
def predict(r0, pool):
    al = sorted(((hav(r0['lat'], r0['lng'], c['lat'], c['lng']), c) for c in pool if c is not r0), key=lambda x: x[0])
    chosen = []; rad = RADII[-1]
    for R in RADII:
        inr = [x for x in al if x[0] <= R]; eff = sum(1 if x[1]['exact'] else 0.5 for x in inr); rad = R; chosen = inr
        if eff >= MIN_EFF: break
    chosen = chosen[:30]; h = max(250, rad / 2.5)
    ws = [(1 / (1 + (d / h) ** 2)) * (1 if c['exact'] else 0.5) * 0.5 ** (c['age_y'] / 2) for d, c in chosen]
    # prior halus: median berbobot jarak (Gauss, bw SMOOTH_PRIOR_BW) dari pembanding ≤ 3·bw — tanpa lompatan di batas kelurahan
    sp = [(d, c) for d, c in al if d <= 3 * SMOOTH_PRIOR_BW]
    if len(sp) >= 3:
        prior = wq([math.log(c['pn']) for _, c in sp], [math.exp(-0.5 * (d / SMOOTH_PRIOR_BW) ** 2) * (1 if c['exact'] else 0.5) for d, c in sp], 0.5)
    else:
        kl = [x for x in kel_by[r0['kelurahan']] if x is not r0]
        kc = [x for x in kec_by[r0['kecamatan']] if x is not r0]
        prior = math.log(statistics.median([x['pn'] for x in kl])) if len(kl) >= 3 else (math.log(statistics.median([x['pn'] for x in kc])) if len(kc) >= 3 else math.log(city_med))
    if not chosen: return prior, 0, city_spread
    vals = [math.log(c['pn']) for _, c in chosen]
    mu = wq(vals, ws, 0.5); neff = sum(ws) ** 2 / sum(w * w for w in ws)
    mad = wq([abs(v - mu) for v in vals], [math.sqrt(w) for w in ws], 0.5)  # sama dengan estimate.ts
    k = min(1, neff / 6); sl = k * max(SPREAD_FLOOR, 1.4826 * mad) + (1 - k) * city_spread
    se = sl / math.sqrt(max(1, neff + 1.5)); sig = math.sqrt(sl * sl + se * se)
    return (neff * mu + 3 * prior) / (neff + 3), neff, sig
SPREAD_FLOOR = 0.25  # sama dengan src/lib/estimate.ts
kec_med_all = {k: statistics.median([x['ppm'] for x in v]) for k, v in kec_by.items()}
loo = []
for r in rows:
    if r['kec_only']:
        continue  # lokasinya tidak diketahui → tidak bisa diuji sebagai titik
    mu, neff, sig = predict(r, loc_rows)
    e = math.log(r['pn']) - mu
    kc = [x['ppm'] for x in kec_by[r['kecamatan']] if x is not r]
    ekec = abs(math.log(r['ppm']) - math.log(statistics.median(kc))) if kc else None
    kl = [x['pn'] for x in kel_by[r['kelurahan']] if x is not r]
    ekel = abs(math.log(r['pn']) - math.log(statistics.median(kl))) if kl else None
    loo.append((r, e, sig, ekel, ekec))
# ---------- kalibrasi lebar rentang menurut luas bidang ----------
# Residu terstandar z = e/σ dari leave-one-out: bidang kecil lebih seragam (rentang terlalu lebar), bidang sangat luas lebih
# beragam (rentang terlalu sempit). Pengali σ per kelas luas = (z75 − z25)/(2·0,674), disusutkan ke 1 (bobot n/(n+100)).
SPREAD_SIZE_EDGES = [0, 100, 175, 500, 1500, float('inf')]
def spread_class(a):
    for i in range(len(SPREAD_SIZE_EDGES) - 1):
        if SPREAD_SIZE_EDGES[i] <= a < SPREAD_SIZE_EDGES[i + 1]: return i
    return len(SPREAD_SIZE_EDGES) - 2
def spread_scales(sub):
    out = []
    for i in range(len(SPREAD_SIZE_EDGES) - 1):
        z = sorted(e / s for r, e, s, _, _ in sub if spread_class(r['area_m2']) == i)
        if len(z) < 30: out.append((1.0, len(z), None)); continue
        q = lambda p: z[int(p * (len(z) - 1))]
        raw = (q(0.75) - q(0.25)) / (2 * 0.674); w = len(z) / (len(z) + 100)
        out.append((w * raw + (1 - w) * 1.0, len(z), raw))
    return out
_sc = spread_scales(loo)
spread_by_size = [{'minM2': SPREAD_SIZE_EDGES[i], 'maxM2': None if SPREAD_SIZE_EDGES[i + 1] == float('inf') else SPREAD_SIZE_EDGES[i + 1],
                   'scale': round(sc, 3), 'scaleRaw': round(raw, 3) if raw else None, 'n': n} for i, (sc, n, raw) in enumerate(_sc)]
print('pengali sebaran per kelas luas', [(b['minM2'], b['scale'], b['n']) for b in spread_by_size])
# cakupan jujur: skala dihitung di separuh data, diuji di separuh lain (silang 2 lipat, dibagi menurut id)
import zlib
_fold = lambda r: zlib.crc32(r['source_id'].encode()) % 2
def _cov(sub, scales):
    return round(100 * sum(1 for r, e, s, _, _ in sub if abs(e) <= 0.674 * s * scales[spread_class(r['area_m2'])][0]) / len(sub), 1)
_cv = []
for f in (0, 1):
    tr = [x for x in loo if _fold(x[0]) != f]; te = [x for x in loo if _fold(x[0]) == f]
    _cv.append((_cov(te, spread_scales(tr)), _cov(te, [(1.0, 0, None)] * 5), len(te)))
def _cov_by_class(scales):
    o = []
    for i in range(len(SPREAD_SIZE_EDGES) - 1):
        sub = [x for x in loo if spread_class(x[0]['area_m2']) == i]
        o.append(_cov(sub, scales) if sub else None)
    return o
spread_cal = {'crossFitCoverage50': [{'withScale': a, 'without': b, 'n': n} for a, b, n in _cv],
              'coverageByClassWithout': _cov_by_class([(1.0, 0, None)] * 5), 'coverageByClassWith': _cov_by_class(_sc)}
print('kalibrasi sebaran', spread_cal)
for i, x in enumerate(loo):
    r, e, s, a, b = x
    loo[i] = (r, e, s * _sc[spread_class(r['area_m2'])][0], a, b)
# ---------- batas atas tier gang / tanpa akses ----------
# Bidang yang hanya bisa dicapai motor/jalan kaki tidak dihargai di atas bidang yang bisa dimasuki mobil di titik yang sama:
# batas atas rentang gang dibatasi pada titik estimasi jalan lingkungan; batas atas tanpa-akses pada titik estimasi gang.
# Diuji pada iklan berketerangan 'gang' (teks): kuartil atas harga/(titik jalan lingkungan di lokasinya) dilaporkan di gangCheck.
_gf = tiers['gang']['factor']; _sigTg = math.log(tiers['gang']['hi'] / tiers['gang']['lo']) / (2 * 1.96)
_g = [(e, s) for r, e, s, _, _ in loo if r['access_tier'] == 'gang']
_el = sorted(e + math.log(_gf) for e, _ in _g)
# Aturan struktural (bukan estimasi): batas = titik jalan lingkungan × 1,0. Kuartil atas iklan gang (n kecil, label teks)
# terlalu tidak stabil untuk dijadikan pengali; nilainya dilaporkan di gangCheck sebagai pemeriksaan.
GANG_CAP_MULT = 1.0
def _gcov(cap):
    inside = 0; above = 0
    for e, s in _g:
        S = math.sqrt(s * s + _sigTg ** 2); hi = 0.674 * S
        if cap: hi = min(hi, -math.log(_gf) + math.log(GANG_CAP_MULT))
        inside += (-0.674 * S <= e <= hi); above += e > hi
    return {'coverage50': round(100 * inside / len(_g), 1), 'aboveHigh': round(100 * above / len(_g), 1)} if _g else None
gang_check = {'n': len(_g), 'q25LogVsLingPoint': round(_el[len(_el) // 4], 3) if _el else None, 'medianLogVsLingPoint': round(_el[len(_el) // 2], 3) if _el else None,
              'q75LogVsLingPoint': round(_el[(3 * len(_el)) // 4], 3) if _el else None, 'shareAboveLingPoint': round(100 * sum(1 for v in _el if v > 0) / len(_el), 1) if _el else None,
              'withoutCap': _gcov(False), 'withCap': _gcov(True), 'capMult': round(GANG_CAP_MULT, 3)}
print('cek gang', gang_check)
def mape(es): return round((math.exp(statistics.median(es)) - 1) * 100, 1)
# ---------- kalibrasi akses hasil deteksi otomatis (OSM) ----------
# Di aplikasi, tier akses awal berasal dari deteksi OSM (jarak titik ke jalan). Audit 2026-10 (analysis/audit/access_calib.py,
# proto_eval.py): iklan berpin tepat yang dideteksi "gang"/"tanpa" TIDAK lebih murah daripada tetangganya (OSM sering tidak
# memetakan gang kampung; titik di tengah blok belum tentu terkurung). Maka harga utama untuk tier hasil deteksi memakai faktor
# terkalibrasi: median log(harga iklan / estimasi tanpa faktor akses) per tier deteksi, disusutkan ke faktor "tidak diketahui"
# (bobot n/(n+30)), lalu dibuat monoton (utama ≥ lingkungan ≥ gang ≥ tanpa). Faktor penuh tetap dipakai bila pengguna memilih tier.
AUTO_ORDER = ['utama', 'lingkungan', 'gang', 'tanpa']
def _tf_used(r):
    t = r['access_tier']; tf = tiers[t]['factor'] if t else math.exp(unknown_b)
    return tf * (cbd_factor(r['d_cbd']) if t == 'utama' else 1.0)
_auto_src = [(r, e + math.log(_tf_used(r)), s) for r, e, s, _, _ in loo if r['loc_level'] == 'titik' and r.get('osm_tier') in AUTO_ORDER]
def _pava(vals, ns):
    bl = [[v, n, [i]] for i, (v, n) in enumerate(zip(vals, ns))]; i = 0
    while i < len(bl) - 1:
        if bl[i][0] < bl[i + 1][0]:
            bl[i] = [(bl[i][0] * bl[i][1] + bl[i + 1][0] * bl[i + 1][1]) / (bl[i][1] + bl[i + 1][1]), bl[i][1] + bl[i + 1][1], bl[i][2] + bl[i + 1][2]]; del bl[i + 1]; i = max(0, i - 1)
        else: i += 1
    out = [0.0] * len(vals)
    for v, n, ix in bl:
        for j in ix: out[j] = v
    return out
_ag = {t: [y for r, y, _ in _auto_src if r['osm_tier'] == t] for t in AUTO_ORDER}
_amed = {t: (statistics.median(v) if v else unknown_b) for t, v in _ag.items()}
_ashr = [(len(_ag[t]) * _amed[t] + 30 * unknown_b) / (len(_ag[t]) + 30) for t in AUTO_ORDER]
_amono = dict(zip(AUTO_ORDER, _pava(_ashr, [len(_ag[t]) for t in AUTO_ORDER])))
# premi pusat kota untuk 'utama' hasil deteksi: skala s ∈ {0, ¼, ½, ¾, 1} dengan bias median terkecil (|median galat|) pada utama
# terdeteksi < 4 km. 2026-10-6: sebelumnya kriteria galat absolut median — kurvanya datar (n≈43, hanya ±7 iklan < 1,5 km) sehingga
# pilihan melompat (1 → ¼) karena perubahan kecil data; kriteria bias stabil (semua skala masih di bawah harga iklan → s terbesar).
_best = (9.0, 0.0)
for _s in (0.0, 0.25, 0.5, 0.75, 1.0):
    _b = [_amono['utama'] + _s * math.log(cbd_factor(r['d_cbd'])) - y for r, y, _ in _auto_src if r['osm_tier'] == 'utama' and r['d_cbd'] < 4000]
    if _b and abs(statistics.median(_b)) <= _best[0] + 1e-9: _best = (abs(statistics.median(_b)), _s)
AUTO_CBD_SCALE = _best[1]
def _auto_pred(r):
    return _amono[r['osm_tier']] + (AUTO_CBD_SCALE * math.log(cbd_factor(r['d_cbd'])) if r['osm_tier'] == 'utama' else 0.0)
def _disp_pred_old(r):
    t = r['osm_tier']; return math.log(tiers[t]['factor'] * (cbd_factor(r['d_cbd']) if t == 'utama' else 1.0))
# tambahan σ (ketidakpastian kondisi akses sebenarnya) agar rentang 50% memuat ±50% iklan
_sig_t = {t: math.log(tiers[t]['hi'] / tiers[t]['lo']) / (2 * 1.96) for t in AUTO_ORDER}
AUTO_SD = 0.0
for _x in (0.0, 0.05, 0.1, 0.15, 0.2, 0.25):
    if 100 * sum(1 for r, y, s in _auto_src if abs(y - _auto_pred(r)) <= 0.674 * math.sqrt(s * s + _x * _x)) / len(_auto_src) >= 50: AUTO_SD = _x; break
    AUTO_SD = _x
def _dstats(pred, sigf):
    es = [_y - pred(r) for r, _y, _ in _auto_src]
    return {'n': len(es), 'medianAbsErrPct': mape([abs(e) for e in es]), 'biasLog': round(-statistics.median(es), 3),
            'within25pct': round(100 * sum(1 for e in es if abs(e) <= math.log(1.25)) / len(es), 1),
            'coverage50pct': round(100 * sum(1 for (r, y, s), e in zip(_auto_src, es) if abs(e) <= 0.674 * sigf(r, s)) / len(es), 1),
            'biasByDetectedTier': {t: round(-statistics.median([_y - pred(r) for r, _y, _ in _auto_src if r['osm_tier'] == t]), 3) for t in AUTO_ORDER if _ag[t]}}
auto_access = {'factors': {t: round(math.exp(_amono[t]), 3) for t in AUTO_ORDER}, 'cbdScale': AUTO_CBD_SCALE, 'sdLog': AUTO_SD,
               'n': {t: len(_ag[t]) for t in AUTO_ORDER}, 'medianRaw': {t: round(math.exp(_amed[t]), 3) for t in AUTO_ORDER},
               'validation': {'before': _dstats(_disp_pred_old, lambda r, s: math.sqrt(s * s + _sig_t[r['osm_tier']] ** 2)),
                              'after': _dstats(_auto_pred, lambda r, s: math.sqrt(s * s + AUTO_SD ** 2)),
                              'note': 'leave-one-out, iklan berpin tepat; harga di titik iklan memakai tier hasil deteksi OSM (yang tampil saat pengguna mengklik titik itu). bias + = estimasi di atas harga iklan.'},
               'note': 'Faktor akses untuk tier hasil deteksi otomatis (belum dipastikan pengguna). Tier yang dipilih manual memakai faktor tiers[].factor.'}
print('akses otomatis', json.dumps(auto_access, ensure_ascii=False))
# ---------- koridor jalan arteri (2026-10-5; persimpangan & keanggotaan 2026-10-6) ----------
# Audit Majapahit (analysis/audit/corridor_cv*.py): iklan muka jalan di koridor arteri komersial (Majapahit–Brigjen Sudiarto,
# Soekarno-Hatta, Perintis Kemerdekaan, …) jauh di atas estimasi karena pembanding terdekat adalah bidang dalam, dan iklan muka
# jalan termahal justru dibuang aturan outlier per kelurahan. Premi koridor = median berbobot jarak (Gauss, bw CORR_BW) residu
# iklan muka jalan pada ruas arteri BERNAMA SAMA (termasuk yang ditandai outlier), disusutkan ke 0 dengan kekuatan CORR_K.
import corridor as CORR
CORR_K, CORR_BW = 2, 1500  # k: 2026-10-6 dikalibrasi ulang (LOO+CV pada iklan muka jalan, harga di ruas jalan): k=4 terlalu menyusutkan
CORR_EVIDENCE = os.environ.get('CORR_EVIDENCE', 'all')  # all | teks (uji)
_ut_log = math.log(tiers['utama']['factor'])
_dk = lambda a, ppm: (round(a), round(math.log(ppm), 2))
_ev = []  # (id, kunci ruas, lat, lng, residu, dupkey, row|None)
_rows_by_id = {f"{r['source']}:{r['source_id']}": r for r in rows}
for r in csv.DictReader(open(os.path.join(OUT, 'listings_all.csv'))):
    if r['loc_level'] != 'titik' or not r['lat'] or not (r['flags'] == '' or r['flags'].startswith('outlier')): continue
    lat, lng = float(r['lat']), float(r['lng']); k, how = CORR.tie(r, lat, lng)
    if not k: continue
    i = f"{r['source']}:{r['source_id']}"; m = _rows_by_id.get(i)
    if m is None:  # iklan outlier: fitur dihitung seperti pipeline
        m = {'lat': lat, 'lng': lng, 'kelurahan': r['kelurahan'], 'kecamatan': r['kecamatan'], 'exact': int(r['exact']), 'area_m2': float(r['area_m2']), 'ppm': float(r['ppm']), 'source': r['source']}
        p_ = math.pi / 180; _x = math.sin((CBD_CENTER[0] - lat) * p_ / 2) ** 2 + math.cos(lat * p_) * math.cos(CBD_CENTER[0] * p_) * math.sin((CBD_CENTER[1] - lng) * p_ / 2) ** 2
        m['d_cbd'] = 2 * 6371008.8 * math.asin(math.sqrt(_x)); m['d_campus'] = campus_dist_m(lat, lng)
        d = r['date'][:7] if r['date'] else AS_OF; y, mo = map(int, d.split('-')); ya, ma = map(int, AS_OF.split('-')); m['age_y'] = max(0, ((ya - y) * 12 + (ma - mo)) / 12)
        m['size_z'] = size_z(area_level(r['kelurahan'], r['kecamatan']))
    mu, _, sig = predict(m, loc_rows)  # leave-one-out (predict melewati baris itu sendiri)
    neu = mu + math.log(size_factor(m['area_m2'], m['size_z']) * campus_factor(m['d_campus'])) - trend_used * m['age_y'] - math.log(SRC_ADJ[m['source']])
    res = math.log(m['ppm']) - neu - _ut_log - math.log(cbd_factor(m['d_cbd']))
    pl, pg = CORR.project(k, lat, lng)
    _ev.append({'id': i, 'k': k, 'lat': pl, 'lng': pg, 'res': res, 'dk': _dk(m['area_m2'], m['ppm']), 'outlier': r['flags'] != '', 'how': how, 'sig': sig,
                'auto': res + _ut_log - _amono['utama'] + (1 - AUTO_CBD_SCALE) * math.log(cbd_factor(m['d_cbd']))})
_by_k = defaultdict(list)
for e in _ev:
    if CORR_EVIDENCE == 'all' or e['how'] == 'teks': _by_k[e['k']].append(e)
def _prem_loo(e):
    ev = _by_k.get(e['k'], [])
    if not ev: return 0.0
    return CORR.premium([(x['lat'], x['lng'], x['res']) for x in ev], e['lat'], e['lng'], CORR_K, CORR_BW, lambda j: ev[j]['id'] == e['id'] or ev[j]['dk'] == e['dk'])[0]
def _cstat(es):
    es = [x for x in es]; return {'n': len(es), 'medianAbsErrPct': mape([abs(x) for x in es]), 'biasLog': round(-statistics.median(es), 3)}
_pl = {e['id']: _prem_loo(e) for e in _ev}
corr_val = {'frontage': {
    'manualBefore': _cstat([e['res'] for e in _ev]), 'manualAfter': _cstat([e['res'] - _pl[e['id']] for e in _ev]),
    'autoBefore': _cstat([e['auto'] for e in _ev]), 'autoAfter': _cstat([e['auto'] - _pl[e['id']] for e in _ev]),
    'autoNonOutlierBefore': _cstat([e['auto'] for e in _ev if not e['outlier']]), 'autoNonOutlierAfter': _cstat([e['auto'] - _pl[e['id']] for e in _ev if not e['outlier']]),
    'autoTextBefore': _cstat([e['auto'] for e in _ev if e['how'] == 'teks']), 'autoTextAfter': _cstat([e['auto'] - _pl[e['id']] for e in _ev if e['how'] == 'teks']),
    'autoPinBefore': _cstat([e['auto'] for e in _ev if e['how'] == 'pin']), 'autoPinAfter': _cstat([e['auto'] - _pl[e['id']] for e in _ev if e['how'] == 'pin'])}}
# tampilan (tier deteksi OSM) untuk semua iklan berpin tepat: premi hanya untuk 'utama' terdeteksi yang ruas terdekatnya koridor
_ev_pts = {k: [(x['lat'], x['lng'], x['res']) for x in v] for k, v in _by_k.items()}
CORR_MAX_ROAD = 60
CORR_BLEND = os.environ.get('CORR_BLEND', '1') == '1'  # 2026-10-6: semua ruas koridor ≤ 60 m digabung (persimpangan); 0 = hanya ruas terdekat
def _corr_prem_at(r):
    if r['osm_tier'] != 'utama': return 0.0
    i = f"{r['source']}:{r['source_id']}"; dk = _dk(r['area_m2'], r['ppm'])
    if CORR_BLEND:
        ks = [k for k in CORR.nearby_keys(r['lat'], r['lng'], CORR_MAX_ROAD) if k in _by_k]
    else:
        d, hw, nm = CORR.nearest_main(r['lat'], r['lng']); k = CORR.key(nm) if nm else None
        ks = [k] if (k in _by_k and d <= CORR_MAX_ROAD) else []
    ps = []
    for k in ks:
        ev = _by_k[k]; ps.append(CORR.premium(_ev_pts[k], r['lat'], r['lng'], CORR_K, CORR_BW, lambda j: ev[j]['id'] == i or ev[j]['dk'] == dk))
    return CORR.blend(ps)[0]
_cp = {id(r): _corr_prem_at(r) for r, _, _ in _auto_src}
corr_val['display'] = {'before': auto_access['validation']['after'], 'after': _dstats(lambda r: _auto_pred(r) + _cp[id(r)], lambda r, s: math.sqrt(s * s + AUTO_SD ** 2)),
                       'nWithPremium': sum(1 for v in _cp.values() if abs(v) > 1e-9)}
_labels = {}
for k in _by_k:
    nms = sorted({x for x in CORR.ROADS if CORR.key(x) == k}, key=lambda x: (x != k, x))
    _labels[k] = ' – '.join(n.title() for n in nms)
corridor_model = {'k': CORR_K, 'bwM': CORR_BW, 'minWeight': 0.01, 'maxRoadM': CORR_MAX_ROAD, 'blend': CORR_BLEND, 'aliases': CORR.ALIASES,
                  'roads': {k: {'label': _labels[k], 'n': len(v), 'pts': [[round(x['lat'], 5), round(x['lng'], 5), round(x['res'], 3)] for x in v], 'ids': [x['id'] for x in v], 'text': [x['how'] == 'teks' for x in v]} for k, v in sorted(_by_k.items())},
                  'validation': corr_val,
                  'note': 'Premi log tier jalan utama di ruas arteri (OSM trunk/primary) bernama: median berbobot exp(−½(jarak/bwM)²) residu iklan muka jalan ruas itu, × nEff/(nEff + k). Berlaku bila ruas jalan utama terdekat ≤ maxRoadM dan bernama sama.'}
print('koridor', len(_ev), 'iklan,', len(_by_k), 'ruas', json.dumps(corr_val, ensure_ascii=False))
def vstats(sub):
    errs = [abs(e) for _, e, _, _, _ in sub]
    return {'n': len(sub), 'medianAbsErrPct_model': mape(errs),
            'medianAbsErrPct_kelurahanMedian': mape([x[3] for x in sub if x[3] is not None]),
            'medianAbsErrPct_kecamatanMedian_raw': mape([x[4] for x in sub if x[4] is not None]),
            'within25pct_model': round(100 * sum(1 for e in errs if e <= math.log(1.25)) / len(errs), 1),
            'coverage50pct': round(100 * sum(1 for _, e, s, _, _ in sub if abs(e) <= 0.674 * s) / len(sub), 1),
            'biasLog': round(statistics.median([e for _, e, _, _, _ in sub]), 3)}
# uji utama: iklan dengan pin tepat (lokasi sebenarnya diketahui)
val = vstats([x for x in loo if x[0]['loc_level'] == 'titik'])
val['target'] = 'iklan berpin tepat (loc_level=titik), leave-one-out'
val['allLocated'] = vstats(loo)
val['nKecamatanOnly'] = sum(1 for r in rows if r['kec_only'])
print('validation', val)
# residu leave-one-out per iklan (untuk analysis/access_spread.py; tidak dipublikasikan)
os.makedirs(os.path.join(os.path.dirname(__file__), '.cache'), exist_ok=True)
with open(os.path.join(os.path.dirname(__file__), '.cache', 'loo_residuals.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['id', 'lat', 'lng', 'loc_level', 'kelurahan', 'kecamatan', 'area_m2', 'access_tier', 'osm_tier', 'osm_drive_m', 'access_evidence', 'e', 'sig', 'ppm', 'pn'])
    for r, e, sig, _, _ in loo:
        w.writerow([f"{r['source']}:{r['source_id']}", r['lat'], r['lng'], r['loc_level'], r['kelurahan'], r['kecamatan'], r['area_m2'], r['access_tier'], r.get('osm_tier', ''), r.get('osm_drive_m', ''), r.get('access_evidence', ''), round(e, 4), round(sig, 4), round(r['ppm']), round(r['pn'])])
# ---------- keluaran ----------
src_meta = [
    {'id': 'pinhome', 'name': 'Pinhome', 'url': 'https://www.pinhome.id/jual/tanah/jawa-tengah/semarang', 'note': 'Halaman hasil pencarian "Tanah dijual di Kota Semarang" per kecamatan + halaman detail iklan (koordinat, kelurahan, tanggal dibuat/diperbarui, deskripsi).'},
    {'id': 'lamudi', 'name': 'Lamudi', 'url': 'https://www.lamudi.co.id/jual/jawa-tengah/semarang/tanah/', 'note': 'Halaman hasil pencarian "Tanah dijual di Semarang" (JSON-LD + koordinat peta pada kartu iklan; tanggal dibuat dari ID iklan UUIDv7, bila ada).'},
]
all_rows = list(csv.DictReader(open(os.path.join(OUT, 'listings_all.csv'))))
for s in src_meta:
    s['rawCount'] = sum(1 for r in all_rows if r['source'] == s['id'])
    s['cleanCount'] = sum(1 for r in rows if r['source'] == s['id'])
    ds = sorted(r['scraped_at'] for r in all_rows if r['source'] == s['id'] and r['scraped_at'])
    s['scrapedAt'] = ds[-1] if ds else ''
blocked = [
    {'name': 'Rumah123', 'reason': 'Cloudflare challenge (403) untuk akses skrip & browser headless'},
    {'name': '99.co', 'reason': 'Cloudflare challenge (403)'},
    {'name': 'OLX Properti', 'reason': 'Koneksi ditolak / HTTP2 error dari server pengambil data'},
    {'name': 'Rumah.com', 'reason': 'Situs tutup sejak 1 Des 2023'},
    {'name': 'Dot Property, Rumahku, UrbanIndo', 'reason': '403 / diblokir'},
    {'name': 'BHUMI ATR/BPN (Zona Nilai Tanah)', 'reason': 'Nilai ZNT hanya bisa dibaca lewat klik manual di peta BHUMI; layanan datanya memakai parameter terenkripsi sehingga tidak diambil otomatis. Layer ZNT Satu Peta (BIG) tidak mencakup Kota Semarang.'},
]
dates = sorted(r['date'][:10] for r in rows if r['date'])
comps = []
for r in rows:
    comps.append({
        'id': f"{r['source']}:{r['source_id']}", 'lat': round(r['lat'], 6), 'lng': round(r['lng'], 6), 'ppm': round(r['ppm']), 'pn': round(r['pn']),
        'tier': r['access_tier'] or None, 'tierSrc': 'teks' if r['access_tier'] else None, 'area': round(r['area_m2']), 'date': r['date'][:7],
        'src': r['source'], 'kel': r['kelurahan'] or None, 'kec': r['kecamatan'], 'exact': bool(r['exact']), 'loc': {'titik': 'titik', 'kelurahan': 'kel', 'kecamatan': 'kec'}[r['loc_level']], 'url': r['url'], 'title': (r['title'] or '')[:90],
    })
model = {
    'version': f'{AS_OF}-6', 'minEffComparables': MIN_EFF, 'locLevels': dict(Counter(r['loc_level'] for r in rows)), 'asOf': AS_OF, 'refArea': REF_AREA, 'sizeElasticity': round(beta_size, 4), 'sizeElasticitySE': round(se_size, 4),
    'sizeCurve': {'knots': size_curve, 'refBin': [SIZE_EDGES[SIZE_REF_BIN], SIZE_EDGES[SIZE_REF_BIN + 1]], 'priorSD': SIZE_PRIOR_SD, 'rss': size_rss,
                  'levelCenter': round(math.exp(SIZE_Z0)), 'zMin': round(SIZE_ZLO, 3), 'zMax': round(SIZE_ZHI, 3),
                  'note': 'Faktor luas = exp(coef(luas) + slope(luas) · z), z = log(median harga/m² mentah kelurahan / levelCenter) dibatasi [zMin, zMax]; coef & slope diinterpolasi linear terhadap log luas antara simpul (median luas tiap kelas), di luar simpul terujung tetap. Menggantikan elastisitas log-linear tunggal.'},
    'commercialFactor': round(math.exp(komersial_b), 3), 'recencyHalfLifeYears': 2, 'trendPerYear': round(trend_used, 4), 'trendRaw': round(trend, 4), 'trendSE': round(se_trend, 4),
    'sourceEffect': round(math.exp(src_b), 3), 'sourceAdj': {k: round(v, 3) for k, v in SRC_ADJ.items()}, 'unknownTierFactor': round(math.exp(unknown_b), 3),
    'cbdFrontage': {'center': list(CBD_CENTER), 'centerName': 'Simpang Lima', 'scaleM': CBD_L, 'coef': round(cbd_used, 4), 'coefRaw': round(cbd_b, 4), 'coefSE': round(cbd_se, 4),
                    'shrink': round(cbd_shr, 3), 'priorSD': CBD_PRIOR_SD, 'nUtamaWithin3L': n_utama_cbd, 'rssByScale': {str(L): round(v[7], 3) for L, v in cbd_fits.items()}, 'rssFlat': round(rss_flat, 3),
                    'note': 'Faktor tambahan untuk tier jalan utama: exp(coef · exp(−jarak ke Simpang Lima / scaleM)).'},
    'campus': {'minHa': CAMPUS_MIN_HA, 'priorSD': CAMPUS_PRIOR_SD, 'bands': campus_coef, 'nCampuses': len(CAMPUSES),
               'note': 'Pengali harga dasar menurut jarak ke poligon kampus terdekat (OSM, ≥ 2 ha, tanpa Akpol); diestimasi bersama efek tetap kelurahan.'},
    'spreadBySize': {'classes': spread_by_size, 'calibration': spread_cal,
                     'note': 'Pengali σ menurut luas bidang, dari residu leave-one-out terstandar: (z75 − z25)/(2·0,674), disusutkan ke 1.'},
    'tierCaps': {'gang': {'ref': 'lingkungan', 'mult': round(GANG_CAP_MULT, 3)}, 'tanpa': {'ref': 'gang', 'mult': 1.0}, 'gangCheck': gang_check,
                 'note': 'Batas atas rentang tier gang ≤ titik estimasi jalan lingkungan × mult (kuartil atas iklan gang); tanpa akses ≤ titik estimasi gang (lokasi & luas sama).'},
    'autoAccess': auto_access, 'corridor': corridor_model, 'smoothPrior': {'bwM': SMOOTH_PRIOR_BW, 'maxM': 3 * SMOOTH_PRIOR_BW, 'minN': 3, 'note': 'Prior = median berbobot Gauss(jarak/bwM) × bobot lokasi dari pembanding ≤ maxM; bila < minN pembanding, median kelurahan/kecamatan/kota.'},
    'tiers': tiers, 'cityMedianPn': round(city_med), 'citySpreadLog': round(city_spread, 4),
    'regression': {'n': n_reg, 'r2Within': round(r2w, 3), 'sigma': round(sigma, 3), 'nOsm': n_osm, 'r2WithinOsm': round(r2w_osm, 3),
                   'coefText': {k: [round(b, 4), round(s, 4)] for k, (b, s) in coef_txt.items()}, 'coefOsm': {k: [round(b, 4), round(s, 4)] for k, (b, s) in coef_osm.items()},
                   'countsText': dict(cnt_txt), 'countsOsm': dict(cnt_osm),
                   'note': 'OLS log(harga/m²) dengan efek tetap kelurahan; akses dibanding jalan lingkungan; kolom "unknown" = iklan tanpa keterangan akses.'},
    'validation': val,
}
osm_meta = json.load(open(os.path.join(PUB, 'osm-meta.json')))
dataset = {
    'meta': {'generatedAt': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'refArea': REF_AREA,
             'counts': {'raw': len(all_rows), 'clean': len(rows), 'bySource': dict(Counter(r['source'] for r in rows))},
             'flags': dict(Counter((r['flags'] or 'BERSIH').split(';')[0].split(' (')[0].split(' dari ')[0] for r in all_rows)),
             'dateMin': dates[0][:7], 'dateMax': dates[-1][:7], 'dateSources': dict(Counter(r['date_source'] for r in rows)),
             'sources': src_meta, 'blocked': blocked, 'osmExtract': ', '.join(sorted(set(x[:10] for x in osm_meta['roadsOsmBase']))),
             'kelurahanCovered': len(kel_stats), 'kelurahanTotal': 177},
    'comparables': comps, 'campuses': [{'name': c['name'], 'areaHa': c['areaHa'], 'rings': c['rings']} for c in CAMPUSES], 'kelurahan': kel_stats, 'kecamatan': kec_stats, 'model': model,
}
json.dump(dataset, open(os.path.join(PUB, 'dataset.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
json.dump(model, open(os.path.join(OUT, 'model_report.json'), 'w'), indent=1, ensure_ascii=False)
with open(os.path.join(OUT, 'listings_model.csv'), 'w', newline='') as f:
    cols = ['source', 'source_id', 'url', 'lat', 'lng', 'exact', 'loc_level', 'kelurahan', 'kecamatan', 'area_m2', 'ppm', 'pn', 'access_tier', 'access_evidence', 'osm_tier', 'osm_drive_m', 'osm_main_m', 'subtype', 'date', 'date_source']
    w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore'); w.writeheader()
    for r in rows:
        r2 = dict(r); r2['pn'] = round(r['pn']); r2['osm_drive_m'] = round(r['osm_drive_m']) if r['osm_drive_m'] is not None else ''; r2['osm_main_m'] = round(r['osm_main_m']) if r['osm_main_m'] is not None else ''
        w.writerow(r2)
print('dataset.json MB', round(os.path.getsize(os.path.join(PUB, 'dataset.json')) / 1e6, 2), 'kelurahan covered', len(kel_stats))
