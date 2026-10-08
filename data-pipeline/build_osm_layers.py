"""Bangun lapisan OSM statis untuk aplikasi:
 - public/data/roads/{ix}_{iy}.json : ubin jalan 0,01° (kelas ringkas, nama, lebar, geometri 5 desimal)
 - public/data/facilities.json       : fasilitas (pendidikan, kesehatan, transportasi, komersial, publik, ibadah)
Data © kontributor OpenStreetMap (ODbL). Sumber: Overpass API (lihat data-raw/osm/*.txt untuk query)."""
import json, os, glob, math, re, gzip, shutil

def jload(path):
    if not os.path.exists(path) and os.path.exists(path + '.gz'):
        path += '.gz'
    return json.load(gzip.open(path, 'rt') if path.endswith('.gz') else open(path))

from collections import defaultdict, Counter
from common import RAW, PUB

TILE = 0.01
osm = os.path.join(RAW, 'osm')
shutil.rmtree(os.path.join(PUB, 'roads'), ignore_errors=True)
os.makedirs(os.path.join(PUB, 'roads'), exist_ok=True)

def road_class(t):
    hw = t.get('highway', '')
    if hw in ('motorway', 'motorway_link'):
        return 'tol'
    if hw in ('trunk', 'primary', 'secondary', 'tertiary', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link'):
        return 'utama'
    if hw in ('footway', 'path', 'steps', 'pedestrian', 'track', 'cycleway', 'bridleway'):
        return 'setapak'
    if hw == 'service' and t.get('service') in ('alley',):
        return 'gang'
    if hw == 'service' and t.get('access') in ('private', 'no'):
        return 'gang'
    if hw in ('unclassified', 'residential', 'living_street', 'road', 'service'):
        w = parse_width(t.get('width'))
        if w is not None and w < 3:
            return 'gang'
        return 'lingkungan'
    return None

def parse_width(s):
    if not s:
        return None
    m = re.match(r'\s*(\d+(?:[.,]\d+)?)', str(s))
    if not m:
        return None
    w = float(m.group(1).replace(',', '.'))
    return w if 0.5 <= w <= 60 else None

ways = {}
stamps = []
for f in sorted(glob.glob(os.path.join(osm, 'roads_*.json*'))):
    d = jload(f)
    stamps.append(d.get('osm3s', {}).get('timestamp_osm_base'))
    for e in d['elements']:
        if e['type'] == 'way' and 'geometry' in e:
            ways[e['id']] = e
print('ways', len(ways), 'osm base', sorted(set(stamps)))
tiles = defaultdict(list)
cc = Counter()
for wid, e in ways.items():
    t = e.get('tags', {})
    c = road_class(t)
    if not c:
        continue
    cc[c] += 1
    g = []
    for p in e['geometry']:
        g += [round(p['lat'], 5), round(p['lon'], 5)]
    lats = g[0::2]; lngs = g[1::2]
    rec = {'c': c, 'hw': t.get('highway')}
    if t.get('name'):
        rec['n'] = t['name']
    w = parse_width(t.get('width'))
    if w is not None:
        rec['w'] = w
    rec['g'] = g
    # ubin yang disentuh bbox jalan (+ margin 0,0008° ≈ 90 m agar pencarian dekat batas ubin aman)
    m = 0.0008
    for ix in range(math.floor((min(lngs) - m) / TILE), math.floor((max(lngs) + m) / TILE) + 1):
        for iy in range(math.floor((min(lats) - m) / TILE), math.floor((max(lats) + m) / TILE) + 1):
            tiles[(ix, iy)].append(rec)
for (ix, iy), recs in tiles.items():
    json.dump(recs, open(os.path.join(PUB, 'roads', f'{ix}_{iy}.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('road classes', cc, 'tiles', len(tiles))
total = sum(os.path.getsize(os.path.join(PUB, 'roads', f)) for f in os.listdir(os.path.join(PUB, 'roads')))
print('roads tiles MB', round(total / 1e6, 1))

# ---------- fasilitas ----------
def classify(t):
    a = t.get('amenity', ''); shop = t.get('shop', ''); hw = t.get('highway', ''); rw = t.get('railway', '')
    name = (t.get('name') or '').lower(); hc = t.get('healthcare', '')
    if t.get('aeroway') == 'aerodrome': return 'transportasi', 'bandara'
    if t.get('barrier') == 'toll_booth' or hw == 'motorway_junction' or 'gerbang tol' in name: return 'transportasi', 'tol'
    if rw in ('station', 'halt') or t.get('public_transport') == 'station' and 'stasiun' in name: return 'transportasi', 'stasiun'
    if a == 'bus_station' or name.startswith('terminal'): return 'transportasi', 'terminal'
    if a == 'ferry_terminal' or 'pelabuhan' in name: return 'transportasi', 'pelabuhan'
    if hw == 'bus_stop' or t.get('public_transport') == 'platform': return 'transportasi', 'halte'
    if a == 'hospital' or hc == 'hospital' or name.startswith('rs ') or 'rumah sakit' in name: return 'kesehatan', 'rs'
    if 'puskesmas' in name or hc == 'centre': return 'kesehatan', 'puskesmas'
    if a in ('clinic', 'doctors', 'dentist') or hc in ('clinic', 'doctor', 'dentist', 'laboratory'): return 'kesehatan', 'klinik'
    if a == 'pharmacy' or hc == 'pharmacy': return 'kesehatan', 'apotek'
    if a in ('university', 'college') or re.search(r'universitas|institut|politeknik|sekolah tinggi|akademi|\bstie\b|\bstikes\b|\buin\b|\bundip\b|\bunnes\b', name): return 'pendidikan', 'kampus'
    if a == 'kindergarten' or re.search(r'\b(paud|tk|ra|kb)\b', name): return 'pendidikan', 'paud'
    if a == 'school':
        if re.search(r'\b(sma|smk|ma|man|smu|stm)\b', name): return 'pendidikan', 'sma'
        if re.search(r'\b(smp|mts|mtsn)\b', name): return 'pendidikan', 'smp'
        if re.search(r'\b(sd|mi|sdn|min)\b', name): return 'pendidikan', 'sd'
        return 'pendidikan', 'sekolah'
    if a == 'marketplace' or name.startswith('pasar '): return 'komersial', 'pasar'
    if shop in ('mall', 'department_store'): return 'komersial', 'mall'
    if shop == 'supermarket': return 'komersial', 'supermarket'
    if shop == 'convenience': return 'komersial', 'minimarket'
    if a == 'bank': return 'komersial', 'bank'
    if a == 'fuel': return 'komersial', 'spbu'
    if a == 'police': return 'publik', 'polisi'
    if a == 'fire_station': return 'publik', 'pemadam'
    if a == 'townhall' or t.get('office') == 'government':
        if 'kecamatan' in name: return 'publik', 'kecamatan'
        if 'kelurahan' in name or 'balai kel' in name: return 'publik', 'kelurahan'
        return 'publik', 'kantor'
    if a == 'place_of_worship':
        rel = t.get('religion', '')
        if rel == 'muslim': return 'ibadah', 'masjid'
        if rel == 'christian': return 'ibadah', 'gereja'
        return 'ibadah', 'ibadah'
    return None

fd = jload(os.path.join(osm, 'facilities_raw.json'))
rows = []; seen = set(); gc = Counter()
for e in fd['elements']:
    t = e.get('tags', {})
    c = classify(t)
    if not c: continue
    lat = e.get('lat') or (e.get('center') or {}).get('lat'); lng = e.get('lon') or (e.get('center') or {}).get('lon')
    if lat is None: continue
    name = t.get('name') or t.get('operator') or ''
    key = (c[1], name.lower(), round(lat, 4), round(lng, 4))
    if key in seen: continue
    seen.add(key); gc[c[0]] += 1
    rows.append([round(lat, 6), round(lng, 6), c[0], c[1], name, f"{e['type'][0]}{e['id']}"])
json.dump({'osmBase': fd.get('osm3s', {}).get('timestamp_osm_base'), 'rows': rows}, open(os.path.join(PUB, 'facilities.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('facilities', len(rows), gc, 'MB', round(os.path.getsize(os.path.join(PUB, 'facilities.json')) / 1e6, 2))
json.dump({'roadsOsmBase': sorted(set(s for s in stamps if s)), 'facilitiesOsmBase': fd.get('osm3s', {}).get('timestamp_osm_base'), 'tileDeg': TILE}, open(os.path.join(PUB, 'osm-meta.json'), 'w'))
