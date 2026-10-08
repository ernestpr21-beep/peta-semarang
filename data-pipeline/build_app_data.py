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

def regress(rows, tier_key, label, cbd_L=None):
    kels = sorted(set(r['kelurahan'] for r in rows))
    kidx = {k: i for i, k in enumerate(kels)}
    tiers_nb = ['utama', 'gang', 'tanpa', 'unknown']
    X = []; y = []
    for r in rows:
        t = r[tier_key] or 'unknown'
        fe = [0.0] * len(kels); fe[kidx[r['kelurahan']]] = 1.0
        x = fe + [math.log(r['area_m2'] / REF_AREA)] + [1.0 if t == tt else 0.0 for tt in tiers_nb] + [1.0 if r['subtype'] == 'komersial' else 0.0, 1.0 if r['source'] == 'lamudi' else 0.0, -r['age_y']]
        x.append(math.exp(-r['d_cbd'] / cbd_L) if (cbd_L and t == 'utama') else 0.0)
        x += [1.0 if r['campus_band'] == i else 0.0 for i in range(len(CAMPUS_BANDS))]
        X.append(x); y.append(math.log(r['ppm']))
    X = np.array(X); y = np.array(y)
    # buang kolom tier yang tidak ada datanya
    keep = [j for j in range(X.shape[1]) if X[:, j].any()]
    names = [f'kel:{k}' for k in kels] + ['log_area'] + [f'tier:{t}' for t in tiers_nb] + ['komersial', 'src_lamudi', 'trend_per_year', 'utama_cbd'] + [f'campus_{lim}' for lim in CAMPUS_BANDS]
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

beta_size, se_size = coef_txt['log_area']
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
    sf = (max(30, r['area_m2']) / REF_AREA) ** beta_size
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
def mape(es): return round((math.exp(statistics.median(es)) - 1) * 100, 1)
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
    'version': f'{AS_OF}-2', 'minEffComparables': MIN_EFF, 'locLevels': dict(Counter(r['loc_level'] for r in rows)), 'asOf': AS_OF, 'refArea': REF_AREA, 'sizeElasticity': round(beta_size, 4), 'sizeElasticitySE': round(se_size, 4),
    'commercialFactor': round(math.exp(komersial_b), 3), 'recencyHalfLifeYears': 2, 'trendPerYear': round(trend_used, 4), 'trendRaw': round(trend, 4), 'trendSE': round(se_trend, 4),
    'sourceEffect': round(math.exp(src_b), 3), 'sourceAdj': {k: round(v, 3) for k, v in SRC_ADJ.items()}, 'unknownTierFactor': round(math.exp(unknown_b), 3),
    'cbdFrontage': {'center': list(CBD_CENTER), 'centerName': 'Simpang Lima', 'scaleM': CBD_L, 'coef': round(cbd_used, 4), 'coefRaw': round(cbd_b, 4), 'coefSE': round(cbd_se, 4),
                    'shrink': round(cbd_shr, 3), 'priorSD': CBD_PRIOR_SD, 'nUtamaWithin3L': n_utama_cbd, 'rssByScale': {str(L): round(v[7], 3) for L, v in cbd_fits.items()}, 'rssFlat': round(rss_flat, 3),
                    'note': 'Faktor tambahan untuk tier jalan utama: exp(coef · exp(−jarak ke Simpang Lima / scaleM)).'},
    'campus': {'minHa': CAMPUS_MIN_HA, 'priorSD': CAMPUS_PRIOR_SD, 'bands': campus_coef, 'nCampuses': len(CAMPUSES),
               'note': 'Pengali harga dasar menurut jarak ke poligon kampus terdekat (OSM, ≥ 2 ha, tanpa Akpol); diestimasi bersama efek tetap kelurahan.'},
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
