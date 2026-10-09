"""Iklan muka jalan utama per ruas bernama: dari teks (pinggir/tepi/depan jalan X, judul 'di Jl. (Raya) X') dicocokkan ke nama jalan utama OSM."""
import csv, json, os, re, glob, math, collections, unicodedata
from common_audit import ROOT, AUDIT_OUT
csv.field_size_limit(10 ** 9)
def nn(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = re.sub(r'\b(jalan|jl|jln|raya|ruas)\b\.?', ' ', s)
    s = s.replace('brigadir jenderal', 'brigjen').replace('letnan jenderal', 'letjen').replace('mayor jenderal', 'mayjen').replace('kiai haji', 'kh').replace('dokter', 'dr')
    s = re.sub(r'[^a-z0-9 ]', ' ', s); return re.sub(r'\s+', ' ', s).strip()
ROADS = collections.defaultdict(list)  # nama ternormalisasi → titik
for f in glob.glob(os.path.join(ROOT, 'public/data/roads/*.json')):
    for r in json.load(open(f)):
        if r['c'] == 'utama' and r.get('n') and r['hw'].replace('_link', '') in ('trunk', 'primary', 'secondary', 'tertiary'):
            k = nn(r['n'])
            if len(k) >= 4: ROADS[k] += [(r['g'][i], r['g'][i + 1]) for i in range(0, len(r['g']), 2)]
ALIAS = {'brigjen sudiarto': ['brigjen sudiarto', 'sudiarto'], 'soekarno hatta': ['soekarno hatta', 'sukarno hatta'], 'setiabudi': ['setiabudi', 'setia budi'],
         'kaligarang': ['kaligarang', 'kali garang'], 'arteri yos sudarso': ['arteri yos sudarso', 'yos sudarso'], 'teuku umar': ['teuku umar', 'teuku umat']}
names = sorted(ROADS, key=len, reverse=True)
FRONT = r'(pinggir|tepi|depan|muka|hadap|menghadap|nempel|0 ?m dari|nol)\s+(jalan|jl\.?|jln\.?)?\s*(raya\s+|besar\s+)?'
def road_mentions(text, front_only):
    t = nn(text) if not front_only else text.lower()
    hits = []
    for k in names:
        for a in ALIAS.get(k, [k]):
            if front_only:
                if re.search(FRONT + re.escape(a), t): hits.append(k)
            elif re.search(r'\b' + re.escape(a) + r'\b', t): hits.append(k)
    return list(dict.fromkeys(hits))
def dist_to(k, lat, lng):
    return min(math.hypot((lat - a) * 110574, (lng - b) * 110500) for a, b in ROADS[k])
out = []
for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_all.csv'))):
    if not (r['flags'] == '' or r['flags'].startswith('outlier') or r['flags'].startswith('duplikat')): continue
    if not r['lat']: continue
    title = r['title'] or ''; desc = (r['description'] or '')[:1500]
    # judul Pinhome '… di <alamat>': alamat jalan utama di judul = bidang di jalan itu (bila ditulis 'Jl/Jalan X')
    m = re.search(r'\bdi\s+(jl\.?|jln\.?|jalan)\s*(raya\s+)?([^,|]+)$', title, re.I)
    tk = [k for k in road_mentions('jalan ' + m.group(3), False)] if m else []
    fk = road_mentions(title + ' \n ' + desc, True)
    ks = list(dict.fromkeys(fk + tk))
    if not ks: continue
    lat, lng = float(r['lat']), float(r['lng'])
    k = min(ks, key=lambda k: dist_to(k, lat, lng)); d = dist_to(k, lat, lng)
    out.append({'id': f"{r['source']}:{r['source_id']}", 'road': k, 'how': 'teks-muka' if k in fk else 'judul-alamat', 'dRoadPin': round(d), 'flag': r['flags'][:50],
                'loc': r['loc_level'], 'lat': lat, 'lng': lng, 'kel': r['kelurahan'], 'area': float(r['area_m2'] or 0), 'ppm': float(r['ppm'] or 0), 'date': r['date'][:10], 'title': title[:90]})
json.dump(out, open(os.path.join(AUDIT_OUT, 'frontage_text.json'), 'w'), ensure_ascii=False, indent=0)
c = collections.Counter(o['road'] for o in out)
print('listings with frontage road text:', len(out), '| unique roads', len(c))
print('by flag', collections.Counter(o['flag'].split(' ')[0] or 'clean' for o in out))
print('pin within 300 m of named road', sum(o['dRoadPin'] <= 300 for o in out), '| 300-1500', sum(300 < o['dRoadPin'] <= 1500 for o in out), '| >1500', sum(o['dRoadPin'] > 1500 for o in out))
print(c.most_common(30))
