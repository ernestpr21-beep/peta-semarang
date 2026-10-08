"""5. Tempat yang paling 'kelihatan salah': kelurahan dengan bias tampilan LOO terbesar (v3 terpasang) + bandingannya di v4."""
import json, math, os, statistics, sys, csv
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common_audit import AUDIT_OUT, ROOT
d3 = {p['id']: p for p in json.load(open(os.path.join(AUDIT_OUT, 'loo_display_v3.json')))}
d4 = {p['id']: p for p in json.load(open(os.path.join(AUDIT_OUT, 'loo_display_v4.json')))}
rows = {f"{r['source']}:{r['source_id']}": r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv')))}
g3 = json.load(open(os.path.join(AUDIT_OUT, 'grid_v3.json'))); g4 = json.load(open(os.path.join(AUDIT_OUT, 'grid_v4.json')))
pop = lambda c: (c['nSeg'] >= 3) or (c['dLing'] is not None and c['dLing'] <= 60)
by = {}
for i, p in d3.items():
    if i in d4: by.setdefault((p['kel'], p['kec']), []).append(i)
out = []
for (kel, kec), ids in by.items():
    if len(ids) < 6: continue
    b3 = [d3[i]['b'] for i in ids]; b4 = [d4[i]['b'] for i in ids]
    lat = statistics.median(float(rows[i]['lat']) for i in ids); lng = statistics.median(float(rows[i]['lng']) for i in ids)
    # sel kisi berpenduduk terdekat ke pusat iklan
    j = min((k for k in range(len(g3)) if pop(g3[k]) and g3[k]['kel'] == kel), key=lambda k: (g3[k]['lat'] - lat) ** 2 + (g3[k]['lng'] - lng) ** 2, default=None)
    if j is None: continue
    c3, c4 = g3[j], g4[j]
    ppm150 = statistics.median(float(rows[i]['ppm']) for i in ids)
    se = 1.2533 * 1.4826 * statistics.median([abs(x - statistics.median(b3)) for x in b3]) / math.sqrt(len(b3))
    out.append({'kel': kel, 'kec': kec, 'n': len(ids), 'lat': c3['lat'], 'lng': c3['lng'], 'tierDetected': c3['tier'],
                'v3Shown': c3['shown'], 'v3Range': [c3['shownLo'], c3['shownHi']], 'v4Shown': c4['shown'], 'v4Range': [c4['shownLo'], c4['shownHi']],
                'listingMedianPpm': round(ppm150), 'listingIQR': [round(float(np.quantile([float(rows[i]['ppm']) for i in ids], q))) for q in (.25, .75)],
                'medianAreaM2': round(statistics.median(float(rows[i]['area_m2']) for i in ids)),
                'v3DisplayBias': round(statistics.median(b3), 3), 'v4DisplayBias': round(statistics.median(b4), 3), 'z3': round(statistics.median(b3) / se, 2) if se else None})
out.sort(key=lambda o: -abs(o['v3DisplayBias']) * math.sqrt(o['n']))
json.dump(out, open(os.path.join(AUDIT_OUT, 'worst_places.json'), 'w'), indent=1, ensure_ascii=False)
print('kelurahan n≥6:', len(out), '| |bias v3|>0.25:', sum(abs(o['v3DisplayBias']) > 0.25 for o in out), '| v4:', sum(abs(o['v4DisplayBias']) > 0.25 for o in out))
print('median |bias| per kelurahan v3', round(statistics.median(abs(o['v3DisplayBias']) for o in out), 3), 'v4', round(statistics.median(abs(o['v4DisplayBias']) for o in out), 3))
for o in out[:22]:
    print(f"{o['kel']:16s} {o['kec']:15s} n{o['n']:3d} ({o['lat']},{o['lng']}) det={o['tierDetected']:10s} v3 {o['v3Shown']/1e6:5.2f} v4 {o['v4Shown']/1e6:5.2f} | iklan med {o['listingMedianPpm']/1e6:5.2f} IQR {o['listingIQR'][0]/1e6:.2f}-{o['listingIQR'][1]/1e6:.2f} luas {o['medianAreaM2']} | bias v3 {o['v3DisplayBias']:+.2f} v4 {o['v4DisplayBias']:+.2f}")
