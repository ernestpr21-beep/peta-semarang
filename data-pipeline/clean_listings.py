"""Bersihkan iklan tanah mentah (Pinhome + Lamudi) → data/listings_clean.csv & data/listings_all.csv.

Langkah:
 1. Normalisasi skema (sumber, id, url, harga total, luas, harga/m², koordinat, kelurahan teks, tanggal).
 2. Harga per m²: deteksi iklan yang mencantumkan harga per m² sebagai "harga".
 3. Lokasi: titik-dalam-poligon kelurahan OSM; cocokkan dengan kelurahan teks iklan. Bila koordinat
    jelas tidak cocok (> 1,5 km dari kelurahan teks) atau hanya titik pusat wilayah → pakai titik
    representatif kelurahan teks dan tandai exact=0.
    Tingkat lokasi (loc_level): 'titik' (pin iklan), 'kelurahan' (hanya diketahui kelurahannya),
    'kecamatan' (hanya diketahui kecamatannya). "Titik bersama" — koordinat yang sama persis dipakai
    ≥ 5 iklan — adalah titik pusat wilayah bawaan portal, bukan lokasi bidang, sehingga tidak dianggap pin.
    Teks lokasi yang hanya berupa nama kecamatan (mis. "Tembalang", yang juga nama kelurahan) dianggap
    tingkat kecamatan bila tidak ada pin yang tepat.
 4. Saring: di luar Kota Semarang, bukan tanah kosong (ada bangunan dihitung), luas/harga tidak wajar.
 5. Akses jalan dari teks iklan (access_text.py).
 6. Deduplikasi (iklan sama di beberapa agen/situs).
 7. Outlier: batas mutlak + MAD per kelurahan (setelah koreksi luas).
Setiap baris menyimpan sumber, URL, tanggal iklan (dibuat/diperbarui) dan tanggal diambil.
"""
import json, re, os, csv, math, glob, statistics, datetime
from collections import Counter, defaultdict
from common import RAW, OUT, Admin, norm, fix_mojibake, strip_html, scrub_contacts, url_has_contact
from access_text import classify_access
from location_text import TextLocator

os.makedirs(OUT, exist_ok=True)
A = Admin()
TL = TextLocator(A)
recs = []

# ---------- Pinhome ----------
plist = {}
for f in sorted(glob.glob(os.path.join(RAW, 'pinhome', 'list*.jsonl'))):
    for l in open(f):
        d = json.loads(l)
        plist.setdefault(d['href'], d)
pdet = {}
for l in open(os.path.join(RAW, 'pinhome', 'detail.jsonl')):
    d = json.loads(l)
    if d.get('id'):
        pdet[d['href']] = d  # versi terakhir menang
for href, li in plist.items():
    d = pdet.get(href)
    if not d:
        continue
    title = fix_mojibake(d.get('title') or li.get('name'))
    desc = strip_html(fix_mojibake(d.get('description') or ''))
    price = d.get('minPrice') or li.get('minPriceValue')
    area = d.get('surfaceArea') or (li.get('specs') or {}).get('surfaceArea')
    coord = d.get('coordinate')
    recs.append({
        'source': 'pinhome', 'source_id': str(d['id']), 'url': 'https://www.pinhome.id' + href,
        'title': title, 'description': desc, 'price': float(price) if price else None, 'area_m2': float(area) if area else None,
        'price_is_ppm': False, 'lat': coord[0] if coord else None, 'lng': coord[1] if coord else None, 'coord_hint': 'pin',
        'kel_text': (d.get('kelurahan') or '').split('(')[0].strip(), 'kec_text': d.get('kecamatan') or li.get('districtTitle'),
        'subtype': 'komersial' if 'commercial' in (d.get('buildingType') or '') else 'residensial',
        'date_listed': (d.get('createdAt') or '')[:10], 'date_updated': (li.get('lastModifiedAt') or '')[:10],
        'scraped_at': (d.get('fetchedAt') or '')[:10],
    })

# ---------- Lamudi ----------
for l in open(os.path.join(RAW, 'lamudi', 'listings.jsonl')):
    d = json.loads(l)
    title = d.get('title') or ''
    desc = d.get('description') or ''
    geo = d.get('map_geo') or d.get('ld_geo')
    exact = bool(d.get('map_exact')) or (d.get('ld_geo') is not None and d.get('map_exact') is None)
    addr = d.get('address') or ''
    # kelurahan dari alamat: cari token yang cocok dengan nama kelurahan OSM
    kel_text = None
    for tok in [t.strip() for t in re.split(r',', addr)]:
        tok2 = re.sub(r'\s*(kel\.|kelurahan)$', '', tok, flags=re.I).strip()
        tok2 = re.sub(r'^(kel\.|kelurahan)\s*', '', tok2, flags=re.I).strip()
        if A.kel_by_name(tok2):
            kel_text = tok2
            break
    if not kel_text:
        m = re.search(r'Dijual di (.+)$', title)
        if m and A.kel_by_name(m.group(1)):
            kel_text = m.group(1)
    recs.append({
        'source': 'lamudi', 'source_id': d['id'], 'url': d['url'], 'title': title, 'description': desc,
        'price': d.get('price'), 'area_m2': d.get('area_m2'), 'price_is_ppm': False,
        'lat': geo[0] if geo else None, 'lng': geo[1] if geo else None, 'coord_hint': 'exact' if exact else 'approx',
        'kel_text': kel_text or '', 'kec_text': '', 'subtype': 'komersial' if re.search(r'komersial|usaha|gudang|industri|ruko', title + ' ' + desc[:300], re.I) else 'residensial',
        'date_listed': (d.get('createdAt') or '')[:10], 'date_updated': '', 'scraped_at': (d.get('scrapedAt') or '')[:10],
        'address': addr,
    })

print('raw records', len(recs), Counter(r['source'] for r in recs))

# ---------- normalisasi & filter ----------
BUILDING = re.compile(r'(tanah\s*(?:dan|&|\+)\s*bangunan|(?:ada|berdiri|bonus|termasuk|beserta|plus)\s+(?:rumah|bangunan|gudang|ruko|kos|kost)\b|rumah\s+(?:tua|lama|hitung\s+tanah)|bangunan\s+(?:lama|tua|existing|eksisting)|kondisi\s+bangunan|luas\s+bangunan\s*:?\s*[1-9])', re.I)
LAND_ONLY_OK = re.compile(r'hitung\s+tanah|harga\s+tanah\s+saja|dihitung\s+tanah', re.I)
PPM_TEXT = re.compile(r'(?:per\s*(?:meter|m2|m²|mtr|m\b)|/\s*(?:m2|m²|meter|mtr)|permeter|per\s*meter\s*persegi)', re.I)
NOT_SALE = re.compile(r'\b(disewakan|sewa|dikontrakkan|kontrak)\b', re.I)

def money_from_text(t):
    """Cari 'Rp 2,5 jt/m' dsb dalam teks → harga per m²."""
    m = re.search(r'(?:rp\.?|harga)\s*([\d.,]+)\s*(jt|juta|rb|ribu|k)?\s*(?:/|per)\s*(?:m2|m²|meter|mtr|m\b)', t, re.I)
    if not m:
        return None
    num = m.group(1).replace('.', '').replace(',', '.')
    try:
        v = float(num)
    except ValueError:
        return None
    unit = (m.group(2) or '').lower()
    if unit in ('jt', 'juta'):
        v *= 1e6
    elif unit in ('rb', 'ribu', 'k'):
        v *= 1e3
    return v if 50_000 <= v <= 80_000_000 else None

# titik bersama: koordinat identik (5 desimal ≈ 1 m) yang dipakai banyak iklan
SHARED_MIN = 5
pin_count = Counter((round(r['lat'], 5), round(r['lng'], 5)) for r in recs if r['lat'] is not None)
KEC_NORM = {norm(k): k for k in A.kec_names()}
_kec_geom = {k: g for k, g in A.kec}

def kec_point(name):
    g = _kec_geom.get(name)
    if g is None:
        return None
    p = g.representative_point()
    return p.y, p.x

out_all = []
for r in recs:
    r['title'] = scrub_contacts(r['title']); r['description'] = scrub_contacts(r['description'])
    if url_has_contact(r['url']):
        r['url'] = ''  # slug URL memuat nomor telepon → tautan tidak dipublikasikan (sumber & id iklan tetap dicatat)
    flags = []
    t = f"{r['title']}\n{r['description']}"
    if not r['price'] or not r['area_m2'] or r['area_m2'] <= 0:
        flags.append('harga/luas kosong')
        ppm = None
    else:
        ppm = r['price'] / r['area_m2']
        # harga yang dicantumkan sebenarnya harga per m²
        if ppm < 40_000 and 50_000 <= r['price'] <= 80_000_000:
            r['price_is_ppm'] = True
            ppm = r['price']
        elif ppm < 40_000:
            tp = money_from_text(t)
            if tp:
                r['price_is_ppm'] = True
                ppm = tp
    r['ppm'] = ppm
    if NOT_SALE.search(r['title'] or ''):
        flags.append('bukan jual')
    if BUILDING.search(t) and not LAND_ONLY_OK.search(t):
        flags.append('ada bangunan')
    if r['area_m2'] and (r['area_m2'] < 30 or r['area_m2'] > 200_000):
        flags.append('luas tidak wajar')
    if ppm is not None and (ppm < 75_000 or ppm > 75_000_000):
        flags.append('harga/m² di luar batas')

    # ---- lokasi ----
    exact = 0
    loc_note = ''
    lat, lng = r['lat'], r['lng']
    kel_poly, kec_poly = (A.kel_at(lat, lng) if lat is not None else (None, None))
    kt = r['kel_text']
    kt_is_kec = bool(kt) and norm(kt) in KEC_NORM
    shared_n = pin_count.get((round(lat, 5), round(lng, 5)), 0) if lat is not None else 0
    if lat is not None and kel_poly and shared_n >= SHARED_MIN:
        # titik pusat wilayah bawaan portal → bukan pin bidang
        c = A.kel_center(kt, r['kec_text'] or None) if kt and not kt_is_kec else None
        if c:
            lat, lng, kel_poly, kec_poly = c
            loc_note = f'titik bersama {shared_n} iklan → titik kelurahan teks'
        else:
            kec_poly = KEC_NORM[norm(kt)] if kt_is_kec else (KEC_NORM.get(norm(r['kec_text'] or '')) or kec_poly)
            kel_poly = ''
            loc_note = f'titik bersama {shared_n} iklan, kelurahan tidak jelas → hanya kecamatan'
    elif lat is not None and kel_poly:
        if kt and norm(kt) != norm(kel_poly):
            dkm = A.dist_to_kel_m(lat, lng, kt, r['kec_text'] or None)
            if dkm is not None and dkm > 1500:
                c = A.kel_center(kt, r['kec_text'] or None)
                if c:
                    lat, lng, kel_poly, kec_poly = c
                    loc_note = f'koordinat iklan {round(dkm)} m dari kelurahan teks → titik kelurahan'
                    exact = 0
            else:
                exact = 1 if r['coord_hint'] in ('pin', 'exact') else 0
                loc_note = 'koordinat dekat batas kelurahan teks'
        else:
            exact = 1 if r['coord_hint'] in ('pin', 'exact') else 0
    elif kt:
        c = A.kel_center(kt, r['kec_text'] or None)
        if c:
            lat, lng, kel_poly, kec_poly = c
            loc_note = 'tanpa koordinat valid → titik kelurahan teks'
            exact = 0
    if exact:
        loc_level = 'titik'
    elif kel_poly == '' or kt_is_kec:
        # teks lokasi hanya nama kecamatan ("Tembalang", "Ngaliyan", ...) dan tidak ada pin tepat
        loc_level = 'kecamatan'
        if kel_poly:
            kec_poly = KEC_NORM[norm(kt)]
            kel_poly = ''
            loc_note = (loc_note + '; ' if loc_note else '') + 'teks lokasi hanya nama kecamatan → hanya kecamatan'
    else:
        loc_level = 'kelurahan'
    if loc_level == 'titik':
        # pin vs nama tempat di teks iklan (alamat Pinhome "... di <alamat>" tidak dipindai: pin berasal dari situ)
        head = re.sub(r'\s+di\s+[^,]*$', '', r['title'] or '') if r['source'] == 'pinhome' else (r['title'] or '')
        c = TL.check(lat, lng, head + '\n' + (r['description'] or '')[:800])
        if c:
            exact = 0
            x = A.kel_center(c['kel'], c['kec']) if c['kel'] else None
            if x:
                lat, lng, kel_poly, kec_poly = x
                loc_level = 'kelurahan'
            else:
                kec_poly = c['kec']; kel_poly = ''
                loc_level = 'kecamatan'
            loc_note = c['why'] + (' → titik kelurahan teks' if loc_level == 'kelurahan' else ' → hanya kecamatan')
    if loc_level == 'kecamatan' and kec_poly:
        kp = kec_point(kec_poly)
        if kp:
            lat, lng = kp
    if lat is None or kel_poly is None or kec_poly is None or not A.inside_city(lat, lng):
        flags.append('di luar Kota Semarang / lokasi tak dikenal')
    r.update({'lat': lat, 'lng': lng, 'kelurahan': kel_poly, 'kecamatan': kec_poly, 'exact': exact, 'loc_level': loc_level, 'loc_note': loc_note})

    tier, why, width = classify_access(r['title'], r['description'])
    r.update({'access_tier': tier or '', 'access_evidence': (why or '')[:120], 'road_width_m': width if width else ''})
    r['date'] = r['date_updated'] or r['date_listed'] or r['scraped_at']
    r['date_source'] = 'diperbarui' if r['date_updated'] else ('dibuat' if r['date_listed'] else 'aktif saat diambil')
    r['flags'] = ';'.join(flags)
    out_all.append(r)

# ---------- dedup ----------
def dkey(r):
    return (norm(r['kelurahan'] or r['kecamatan'] or ''), round(r['area_m2'] or 0), round((r['price'] or 0) / 1e6))
groups = defaultdict(list)
for r in out_all:
    if not r['flags']:
        groups[dkey(r)].append(r)
dups = 0
for k, g in groups.items():
    if len(g) > 1:
        g.sort(key=lambda x: (-x['exact'], -len(x['description'] or ''), x['date']))
        for x in g[1:]:
            x['flags'] = 'duplikat dari ' + g[0]['source'] + ':' + g[0]['source_id']
            dups += 1
print('duplicates', dups)

# ---------- dedup lintas kelurahan/portal (2026-10-6) ----------
# Bidang yang sama sering diiklankan beberapa agen dengan pin berserakan di kelurahan berbeda (mis. 7.252 m² @ Rp7 jt/m²
# tercatat 7× dari Kalicari sampai Bugangan), sehingga kunci kelurahan di atas gagal. Dua iklan dianggap sama bila luasnya sama
# (±0,5 m² atau ±0,1%) dan harga totalnya sama (±1%), DAN teksnya mirip (Jaccard bigram ≥ 0,3) ATAU luasnya khas (≥ 300 m², bukan
# kelipatan 25 m²) dan pinnya ≤ 5 km. Yang disimpan: pin tepat yang paling sentral di antara salinan (medoid), lalu deskripsi terpanjang.
DEDUP_X = os.environ.get('DEDUP_X', '1') == '1'
def _bigr(r):
    t = re.sub(r'[^a-z0-9 ]', ' ', ((r['title'] or '') + ' ' + (r['description'] or '')).lower()).split()
    return set(zip(t, t[1:]))
def _dm(a, b):
    if a['lat'] is None or b['lat'] is None: return 9e9
    return math.hypot((a['lat'] - b['lat']) * 110574, (a['lng'] - b['lng']) * 110500)
dups_x = 0
if DEDUP_X:
    cand = [r for r in out_all if not r['flags'] and r['area_m2'] and r['ppm']]
    cand.sort(key=lambda r: r['area_m2'])
    bg = {id(r): _bigr(r) for r in cand}
    parent = {}
    def _find(i):
        while parent.get(i, i) != i: i = parent[i]
        return i
    for i, x in enumerate(cand):
        tol = max(0.5, 0.001 * x['area_m2'])
        for y in cand[i + 1:]:
            if y['area_m2'] - x['area_m2'] > tol: break
            tx, ty = x['area_m2'] * x['ppm'], y['area_m2'] * y['ppm']
            if abs(tx - ty) > 0.01 * max(tx, ty): continue
            distinct = any(a >= 300 and round(a) % 25 != 0 for a in (x['area_m2'], y['area_m2']))
            sim = len(bg[id(x)] & bg[id(y)]) / max(1, len(bg[id(x)] | bg[id(y)]))
            if sim >= 0.3 or (distinct and _dm(x, y) <= 5000):
                parent[_find(id(y))] = _find(id(x))
    comp = defaultdict(list)
    for r in cand: comp[_find(id(r))].append(r)
    for g in comp.values():
        if len(g) < 2: continue
        def rank(x):
            return (-x['exact'], sum(_dm(x, y) for y in g if y['exact']) if x['exact'] else 0, -len(x['description'] or ''), x['date'])
        g.sort(key=rank)
        for x in g[1:]:
            x['flags'] = 'duplikat lintas wilayah dari ' + g[0]['source'] + ':' + g[0]['source_id']
            dups_x += 1
print('duplicates lintas kelurahan/portal', dups_x)

# ---------- outlier per kelurahan (log harga/m² setelah koreksi luas kasar) ----------
ok = [r for r in out_all if not r['flags']]
def logadj(r):
    return math.log(r['ppm']) + 0.12 * math.log(max(30, r['area_m2']) / 150)
byk = defaultdict(list)
for r in ok:
    byk[r['kelurahan']].append(r)
byc = defaultdict(list)
for r in ok:
    byc[r['kecamatan']].append(r)
# 2026-10-6: pencilan diukur SETELAH koreksi kelas akses dari teks. Sebelumnya bidang muka jalan utama dibandingkan langsung dengan
# bidang dalam se-kelurahan sehingga iklan muka jalan yang wajar (mis. Jl. Majapahit Rp22–30 jt/m²) terbuang sebagai pencilan.
# Koreksi per kelas = median simpangan (logadj − median pool) iklan kelas itu di seluruh kota (data, bukan angka tetap).
OUTLIER_TIER = os.environ.get('OUTLIER_TIER', '1') == '1'
def _pool(r):
    return byk[r['kelurahan']] if r['kelurahan'] and len(byk[r['kelurahan']]) >= 6 else byc[r['kecamatan']]
tier_off = defaultdict(float)
if OUTLIER_TIER:
    _dev = defaultdict(list)
    _pm = {}
    for r in ok:
        pl = _pool(r)
        if len(pl) < 5: continue
        k = id(pl)
        if k not in _pm: _pm[k] = statistics.median([logadj(x) for x in pl])
        _dev[r['access_tier'] or ''].append(logadj(r) - _pm[k])
    _base = statistics.median(_dev['']) if _dev[''] else 0.0
    for t, v in _dev.items(): tier_off[t] = statistics.median(v) - _base if len(v) >= 20 else 0.0
    print('koreksi kelas akses untuk pencilan', {t: round(v, 3) for t, v in tier_off.items()})
def logadj_t(r): return logadj(r) - tier_off[r['access_tier'] or '']
outl = 0
for r in ok:
    pool = _pool(r)
    vals = [logadj_t(x) for x in pool]
    if len(vals) < 5:
        continue
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals]) * 1.4826
    mad = max(mad, 0.25)
    z = (logadj_t(r) - med) / mad
    if abs(z) > 3.0:
        r['flags'] = f'outlier (z={z:.1f} vs median {"kelurahan" if pool is byk[r["kelurahan"]] else "kecamatan"})'
        outl += 1
print('outliers', outl)

cols = ['source', 'source_id', 'url', 'title', 'price', 'area_m2', 'price_is_ppm', 'ppm', 'lat', 'lng', 'exact', 'loc_level', 'loc_note', 'kelurahan', 'kecamatan',
        'kel_text', 'subtype', 'access_tier', 'access_evidence', 'road_width_m', 'date', 'date_source', 'date_listed', 'date_updated', 'scraped_at', 'flags']
with open(os.path.join(OUT, 'listings_all.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols + ['description'], extrasaction='ignore')
    w.writeheader()
    for r in out_all:
        r2 = dict(r)
        r2['description'] = (r['description'] or '')[:1500]
        if r2['lat'] is not None:
            r2['lat'] = round(r2['lat'], 6); r2['lng'] = round(r2['lng'], 6)
        if r2.get('ppm'):
            r2['ppm'] = round(r2['ppm'])
        w.writerow(r2)
clean = [r for r in out_all if not r['flags']]
with open(os.path.join(OUT, 'listings_clean.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
    w.writeheader()
    for r in clean:
        r2 = dict(r); r2['lat'] = round(r2['lat'], 6); r2['lng'] = round(r2['lng'], 6); r2['ppm'] = round(r2['ppm'])
        w.writerow(r2)
fc = Counter()
for r in out_all:
    for fl in (r['flags'] or 'BERSIH').split(';'):
        fc[re.sub(r'\(.*', '', fl).split(' dari ')[0].strip()] += 1
print('flags', fc.most_common())
print('clean', len(clean), Counter(r['source'] for r in clean))
print('access tiers', Counter(r['access_tier'] or '(tidak disebut)' for r in clean))
print('exact', Counter(r['exact'] for r in clean))
print('loc_level', Counter(r['loc_level'] for r in clean))
print('loc_level x kecamatan (kecamatan-only)', Counter(r['kecamatan'] for r in clean if r['loc_level'] == 'kecamatan').most_common())
print('per kecamatan', Counter(r['kecamatan'] for r in clean).most_common())
