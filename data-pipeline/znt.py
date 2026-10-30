"""Batas bawah ZNT BPN (Bhumi) sebagai pemeriksa/penahan bawah harga pasar (kalibrasi per kelurahan, mulai 2026-10-9 ronde 1).
data/znt_readings.csv: satu baris per titik baca (hanya zona & pita nilai, tanpa data pribadi). Hanya baris active=1 yang dipakai.
Jangkar 'frontage' (titik baca di muka jalan utama): batas bawah tier jalan utama untuk titik ≤ maxRoadM dari jalan utama yang
namanya termasuk roads (ruas yang dibaca; harus ≤ 25 m dari titik baca), penuh sampai r0 m, melemah linear (log) sampai r1 m.
Jangkar 'area' (jalan lingkungan/gang): batas bawah harga dasar (semua tier dikali sama) — hanya jangkar area TERDEKAT, penuh sampai r0, nol di r1.
Di luar kelurahan jangkar radius dikali outsideScale (zona ZNT bisa melintas batas, tapi belum dibaca). Batas = pita bawah × margin (harga pasar umumnya ≥ ZNT; kolom margin per titik bila bukti iklan menunjukkan pasar dekat pita bawah).
Jangkar muka jalan: hanya jangkar TERDEKAT pada ruas yang sama (mis. Walisongo barat 5–10 jt tidak ditimpa Walisongo tengah >20 jt).
Kolom roads 'nama@r1': ruas simpang dengan radius sendiri (mis. jalan lain yang hanya bersinggungan di titik baca). Kolom radius 'r0;r1' (opsional): radius jangkar sendiri (area: mis. titik baris kedua di zona jalur jalan; muka jalan: ruas yang iklannya jauh di bawah ZNT).
Zona: ≥ 3 titik area dengan zona & pita sama → selubung cembung + 40 m, berlaku penuh di dalam, melemah sampai 80 m di luar."""
import csv, glob, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
MARGIN = 1.15
FRONT_R = (250.0, 500.0); AREA_R = (50.0, 120.0); ROAD_M = 25.0; ZONE_MIN = 3; ZONE_BUF = 40.0; ZONE_R = 80.0; OUTSIDE = 0.5  # di luar kelurahan jangkar: radius × OUTSIDE
def _seg_d(lat, lng, a, b, c, d):
    kx = 111320 * math.cos(math.radians(lat)); ky = 110574
    px, py = (lng - b) * kx, (lat - a) * ky; qx, qy = (d - b) * kx, (c - a) * ky
    L = qx * qx + qy * qy; t = 0 if L == 0 else max(0, min(1, (px * qx + py * qy) / L))
    return math.hypot(px - t * qx, py - t * qy)
def roads_near(lat, lng, maxm=60.0):
    from corridor import nn
    fm = os.path.join(ROOT, 'data/frontage_model.json'); al = json.load(open(fm))['aliases'] if os.path.exists(fm) else {}
    rkey = lambda n: al.get(nn(n), nn(n))
    out = set()
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            p = os.path.join(ROOT, 'public/data/roads', f'{math.floor(lng / 0.01) + dx}_{math.floor(lat / 0.01) + dy}.json')
            if not os.path.exists(p): continue
            for r in json.load(open(p)):
                if r['c'] != 'utama' or not r.get('n'): continue
                g = r['g']
                if any(_seg_d(lat, lng, g[i], g[i + 1], g[i + 2], g[i + 3]) <= maxm for i in range(0, len(g) - 2, 2)): out.add(rkey(r['n']))
    return sorted(out)
def build():
    p = os.path.join(ROOT, 'data/znt_readings.csv')
    if not os.path.exists(p): return None
    rows = [r for r in csv.DictReader(open(p)) if r['active'] == '1']
    if not rows: return None
    anchors = []
    for r in rows:
        a = {'id': r['id'], 'lat': float(r['lat']), 'lng': float(r['lon']), 'zone': r['zone'] or None, 'lo': int(r['band_lo']), 'hi': int(r['band_hi']) if r['band_hi'] else None,
             'year': int(r['year']), 'kind': r['kind'], 'kel': r['kelurahan'], **({'margin': float(r['margin'])} if r.get('margin') else {}),
             **({'r': [float(x) for x in r['radius'].split(';')]} if r.get('radius') else {})}
        if r['kind'] == 'frontage':
            # ruas yang dibaca (kolom roads, kunci koridor) — bila kosong: ruas utama bernama ≤ ROAD_M m dari titik baca
            # 'nama@r1' = ruas simpang: hanya berlaku sampai r1 m pada ruas itu (penuh sampai r1/2)
            rr = [x.strip() for x in r['roads'].split(';') if x.strip()] if r.get('roads') else []
            a['roads'] = sorted(x.split('@')[0].strip() for x in rr) if rr else roads_near(a['lat'], a['lng'], ROAD_M)
            rR = {x.split('@')[0].strip(): [float(x.split('@')[1]) / 2, float(x.split('@')[1])] for x in rr if '@' in x}
            if rR: a['roadR'] = rR
            near = roads_near(a['lat'], a['lng'], ROAD_M)
            assert all(k in near for k in a['roads']), (r['id'], a['roads'], near)
        # jangkar area dengan radius sendiri (titik baris kedua di zona jalur) tidak ikut membentuk poligon zona
        anchors.append(a)
    # zona dengan ≥ ZONE_MIN titik baca area berpita sama → poligon zona perkiraan (selubung cembung titik + ZONE_BUF m), batas bawah berlaku penuh di dalamnya
    from shapely.geometry import MultiPoint, mapping
    zones = []
    by = {}
    for a in anchors:
        if a['kind'] == 'area' and a['zone'] and 'r' not in a: by.setdefault((a['zone'], a['lo'], a['hi']), []).append(a)
    for (zn, lo, hi), aa in by.items():
        if len(aa) < ZONE_MIN: continue
        k = 1 / 110574.0
        hull = MultiPoint([(a['lng'], a['lat']) for a in aa]).convex_hull.buffer(ZONE_BUF * k, 8).simplify(3 * k)
        ring = [[round(x, 6), round(y, 6)] for x, y in hull.exterior.coords]
        mg = [a['margin'] for a in aa if 'margin' in a]
        zones.append({'zone': zn, 'lo': lo, 'hi': hi, 'year': aa[0]['year'], 'kel': aa[0]['kel'], 'ids': [a['id'] for a in aa], 'ring': ring, **({'margin': min(mg)} if mg else {})})
    return {'margin': MARGIN, 'zoneR': ZONE_R, 'zones': zones, 'frontR': list(FRONT_R), 'areaR': list(AREA_R), 'outsideScale': OUTSIDE, 'rounds': sorted({r['round'] for r in rows}), 'anchors': anchors,
            'note': 'Batas bawah dari ZNT BPN (Bhumi, nilai pita per zona). Harga pasar = max(model, pita bawah × margin) di sekitar titik baca; ZNT hanya penahan bawah, bukan harga pasar.'}
if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=1)[:2500])
