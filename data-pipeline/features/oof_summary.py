"""Ringkas galat tingkat dasar (log pn) prediksi luar-lipatan per varian (keluaran feature_model.py eval)."""
import csv, json, math, sys, statistics, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = json.load(open(sys.argv[1])); E = {e['id']: e for e in json.load(open(sys.argv[2]))}
Y = {f"{r['source']}:{r['source_id']}": math.log(float(r['pn'])) for r in csv.DictReader(open(os.path.join(ROOT, 'data/listings_model.csv'))) if r['loc_level'] == 'titik'}
for mode, vs in P.items():
    for v, ps in sorted(vs.items()):
        e = [ps[i] - Y[i] for i in ps if i in Y and not E[i]['outlier']]
        a = sorted(abs(x) for x in e)
        print(f"{mode:4s} {v:10s} n={len(e)} MdAPE {(math.exp(statistics.median(a)) - 1) * 100:5.1f}% bias {statistics.median(e):+.3f}")
