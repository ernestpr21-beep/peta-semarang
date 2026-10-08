import csv, math, statistics, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
POINTS = {
    'Jl. Prof. Soedarto': (-7.05561, 110.43728), 'Jl. Banjarsari Raya': (-7.05877, 110.43529), 'Jl. Tirto Agung': (-7.05412, 110.43067),
    'Jl. Ngesrep Timur V': (-7.04851, 110.4244), 'Jl. Mulawarman Raya': (-7.06382, 110.43814), 'Jl. Sumurboto Utara': (-7.05092, 110.42745),
    'Jl. Baskoro Raya': (-7.05479, 110.43673), 'Jl. Timoho Raya': (-7.06016, 110.44208),
}
def hav(a, b, c, d):
    p = math.pi / 180; x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 2 * 6371008.8 * math.asin(min(1, math.sqrt(x)))
rows = list(csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv'))))
titles = {r['source'] + r['source_id']: r for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_clean.csv')))}
for r in rows:
    for k in ('lat', 'lng', 'ppm', 'pn', 'area_m2'): r[k] = float(r[k])
    r['exact'] = int(r['exact']); r['title'] = titles[r['source'] + r['source_id']]['title']; r['loc_note'] = titles[r['source'] + r['source_id']]['loc_note']
if __name__ == '__main__':
    for name, (lat, lng) in POINTS.items():
        al = sorted(((hav(lat, lng, r['lat'], r['lng']), r) for r in rows), key=lambda x: x[0])
        for R in [400, 600, 800, 1000, 1500, 2000, 3000]:
            inr = [x for x in al if x[0] <= R]
            if sum(1 if x[1]['exact'] else 0.5 for x in inr) >= 8: break
        inr = inr[:30]
        ex = [x for x in inr if x[1]['exact']]; ap = [x for x in inr if not x[1]['exact']]
        print(f"\n== {name} R={R} used={len(inr)} exact={len(ex)} approx={len(ap)} | median pn exact={statistics.median([x[1]['pn'] for x in ex])/1e6 if ex else 0:.2f} approx={statistics.median([x[1]['pn'] for x in ap])/1e6 if ap else 0:.2f}")
        for d, r in inr[:14]:
            print(f"  {d:5.0f}m {'EX' if r['exact'] else 'ap'} {r['kelurahan'][:12]:12s} {r['area_m2']:7.0f}m2 ppm={r['ppm']/1e6:5.2f} pn={r['pn']/1e6:5.2f} {r['source'][:3]} {r['loc_note'][:18]:18s} {r['title'][:55]}")
