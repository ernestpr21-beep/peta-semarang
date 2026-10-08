"""Bias LOO per iklan untuk harga yang TAMPIL di aplikasi (tier hasil deteksi OSM) — v3 (terpasang) & v4 (prototipe)."""
import csv, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import ROOT, AUDIT_OUT
acc = {a['id']: a for a in json.load(open(os.path.join(AUDIT_OUT, 'listing_access.json')))}
m3 = json.load(open(os.path.join(AUDIT_OUT, 'dataset_v3.json')))['model']; m4 = json.load(open(os.path.join(ROOT, 'public/data/dataset.json')))['model']
rows = {f"{r['source']}:{r['source_id']}": r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv')))}
from common_audit import load_rows
dc = {r['id']: r['d_cbd'] for r in load_rows()[0]}
def cbdf(m, d): c = m['cbdFrontage']; return math.exp(c['coef'] * math.exp(-d / c['scaleM']))
def tf_used(m, r, d):
    t = r['access_tier']; f = m['tiers'][t]['factor'] if t else m['unknownTierFactor']
    return f * (cbdf(m, d) if t == 'utama' else 1)
loo3 = json.load(open(os.path.join(AUDIT_OUT, 'loo_points.json')))
out3 = []
for p in loo3:
    r = rows[p['id']]; d = dc[p['id']]; t = acc[p['id']]['tier']
    f = m3['tiers'][t]['factor'] * (cbdf(m3, d) if t == 'utama' else 1)
    out3.append(dict(p, b=round(p['b'] + math.log(f) - math.log(tf_used(m3, r, d)), 4)))
out4 = []
aa = m4['autoAccess']
for r4 in csv.DictReader(open(os.path.join(ROOT, 'data-pipeline/.cache/loo_residuals.csv'))):
    if r4['loc_level'] != 'titik': continue
    i = r4['id']; r = rows[i]; d = dc[i]; t = acc[i]['tier']
    f = aa['factors'][t] * (cbdf(m4, d) ** aa['cbdScale'] if t == 'utama' else 1)
    out4.append({'id': i, 'lat': float(r4['lat']), 'lng': float(r4['lng']), 'kel': r4['kelurahan'], 'kec': r4['kecamatan'],
                 'b': round(-float(r4['e']) + math.log(f) - math.log(tf_used(m4, r, d)), 4)})
json.dump(out3, open(os.path.join(AUDIT_OUT, 'loo_display_v3.json'), 'w')); json.dump(out4, open(os.path.join(AUDIT_OUT, 'loo_display_v4.json'), 'w'))
import statistics
for n, o in (('v3', out3), ('v4', out4)):
    b = [x['b'] for x in o]; print(n, len(b), 'median bias', round(statistics.median(b), 3), 'mdae', round((math.exp(statistics.median([abs(x) for x in b])) - 1) * 100, 1))
