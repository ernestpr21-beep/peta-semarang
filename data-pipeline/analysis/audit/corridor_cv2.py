"""Varian koridor: Majapahit+Sudiarto digabung; opsi hanya trunk/primary; opsi premi positif saja."""
import io, contextlib, json, glob, math, os, numpy as np
with contextlib.redirect_stdout(io.StringIO()):
    import corridor_cv as K
for k, v in list(K.road_of.items()):
    if v == 'brigjen sudiarto': K.road_of[k] = 'majapahit'
K.FT.ROADS['majapahit'] = K.FT.ROADS['majapahit'] + K.FT.ROADS.get('brigjen sudiarto', [])
K.P = {o['id']: K.proj(K.road_of[o['id']], o['lat'], o['lng']) for o in K.T}
cls = {}
for f in glob.glob('/workspace/peta-semarang/public/data/roads/*.json'):
    for r in json.load(open(f)):
        if r['c'] == 'utama' and r.get('n'): cls.setdefault(K.FT.nn(r['n']), set()).add(r['hw'].replace('_link', ''))
ART = {r for r, c in cls.items() if c & {'trunk', 'primary'}} | {'majapahit'}
orig_run = K.run
def run2(mode, kp, bw, uo, art_only, pos_only):
    pr = orig_run(mode, kp, bw, uo)
    out = {}
    for i, v in pr.items():
        prem = v[2]
        if art_only and K.road_of[i] not in ART: prem = 0.0
        if pos_only: prem = max(prem, 0.0)
        out[i] = (v[0] - v[2] + prem, v[1] - v[2] + prem, prem)
    return out
res = {}
for mode in ('loo', 'cv'):
    print(f'\n== {mode}  [manual | auto | auto non-outl | arterial(trunk/primary) auto | Majapahit+Sudiarto auto]')
    for kp, bw, uo, ao, po in [(None, 1500, False, False, False), (4, 1500, True, False, False), (4, 1500, True, True, False), (4, 1500, True, True, True), (4, 1500, True, False, True), (2, 1500, True, True, False), (8, 1500, True, True, False), (4, 3000, True, True, False), (4, 1500, False, True, False)]:
        pr = run2(mode, kp, bw, uo, ao, po)
        name = 'sekarang' if kp is None else f'k={kp} bw={bw}{" +outl" if uo else ""}{" arteri" if ao else ""}{" pos" if po else ""}'
        a, b, c = K.st(pr, 0), K.st(pr, 1), K.st(pr, 1, lambda o: not o['outlier'])
        d = K.st(pr, 1, lambda o: K.road_of[o['id']] in ART); m = K.st(pr, 1, lambda o: K.road_of[o['id']] == 'majapahit')
        res[f'{mode}|{name}'] = dict(manual=a, auto=b, nonOutl=c, arterial=d, majapahit=m)
        print(f"  {name:32s} man {a[1]:5.1f}% {a[2]:+.3f} | auto {b[1]:5.1f}% {b[2]:+.3f} | nonout {c[1]:5.1f}% {c[2]:+.3f} | art n={d[0]} {d[1]:5.1f}% {d[2]:+.3f} | Maj n={m[0]} {m[1]:5.1f}% {m[2]:+.3f}")
json.dump(res, open(os.path.join(K.AUDIT_OUT, 'corridor_cv2.json'), 'w'), indent=1)
