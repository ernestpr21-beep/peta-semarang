import sys, os, math, json, collections, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import corridor_cv as K
pr = K.run('cv', None, 1500, False)
g = collections.defaultdict(list)
for k, v in pr.items(): g[K.road_of[k]].append((v[1], K.byid[k]))
cls = {}
import glob
for f in glob.glob('/workspace/peta-semarang/public/data/roads/*.json'):
    for r in json.load(open(f)):
        if r['c'] == 'utama' and r.get('n'): cls.setdefault(K.FT.nn(r['n']), set()).add(r['hw'].replace('_link', ''))
rows = []
for rd, v in g.items():
    if len(v) < 5: continue
    e = np.array([x[0] for x in v]); rows.append((rd, sorted(cls.get(rd, [])), len(v), sum(o['outlier'] for _, o in v), round(float(np.median(e)), 2), round(float(np.median([o['ppm'] for _, o in v])) / 1e6, 1)))
for r in sorted(rows, key=lambda r: r[4]): print(r)
