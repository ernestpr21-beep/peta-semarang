"""Himpunan uji bersama untuk membandingkan versi model (2026-10-6): iklan berpin tepat dari data bersih v6 + iklan muka jalan
(termasuk yang ditandai pencilan), dengan grup salinan (dikeluarkan dari pool saat menguji). Keluaran: AUDIT_OUT/eval_v6.json"""
import csv, json, os, sys, re, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
import corridor as C
csv.field_size_limit(10 ** 9)
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '../../../data/listings_all.csv')
OUTF = sys.argv[2] if len(sys.argv) > 2 else '/workspace/semarang-ref/audit/eval_v6.json'
R = list(csv.DictReader(open(SRC)))
grp = collections.defaultdict(set)
for r in R:
    i = f"{r['source']}:{r['source_id']}"
    m = re.search(r'dari (\S+)$', r['flags'] or '')
    if r['flags'].startswith('duplikat') and m:
        grp[m.group(1)].add(i)
def root(i, seen=()):
    return i
# grup penuh (rantai salinan)
full = {}
for k, v in grp.items():
    s = {k} | v
    for x in list(v): s |= grp.get(x, set())
    full[k] = sorted(s)
out = []
for r in R:
    if r['loc_level'] != 'titik' or not r['lat'] or not (r['flags'] == '' or r['flags'].startswith('outlier')): continue
    i = f"{r['source']}:{r['source_id']}"; lat, lng = float(r['lat']), float(r['lng'])
    k, how = C.tie(r, lat, lng)
    pj = C.project(k, lat, lng) if k else None
    out.append({'id': i, 'lat': lat, 'lng': lng, 'area': float(r['area_m2']), 'ppm': float(r['ppm']), 'date': r['date'][:7], 'src': r['source'], 'kel': r['kelurahan'], 'kec': r['kecamatan'],
                'outlier': r['flags'] != '', 'txtTier': r['access_tier'], 'corr': k, 'corrHow': how, 'proj': pj, 'group': full.get(i, [i])})
json.dump(out, open(OUTF, 'w'))
print(len(out), 'clean', sum(not o['outlier'] for o in out), 'textUtama', sum(o['txtTier'] == 'utama' for o in out), 'corr teks', sum(o['corrHow'] == 'teks' for o in out), 'grouped', sum(len(o['group']) > 1 for o in out))
