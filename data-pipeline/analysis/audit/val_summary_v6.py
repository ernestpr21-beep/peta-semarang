"""Ringkasan validasi bersama (keluaran tests/validate-cv.test.ts): keseluruhan, muka jalan, per kecamatan, per tingkat harga."""
import json, math, sys, statistics, collections
R = json.load(open(sys.argv[1])); E = {e['id']: e for e in json.load(open(sys.argv[2]))}
D = json.load(open(sys.argv[3]))  # dataset untuk tingkat harga kelurahan
lvl = {s['name']: s['medianRaw'] for s in D['kelurahan']}
qs = sorted(lvl[e['kel']] for e in E.values() if e['kel'] in lvl); cut = [qs[int(len(qs) * q / 5)] for q in (1, 2, 3, 4)]
def qbin(e):
    v = lvl.get(e['kel']); return None if v is None else sum(v > c for c in cut)
def st(rs, key='eShown'):
    es = [r[key] for r in rs]
    if not es: return None
    a = sorted(abs(x) for x in es)
    return {'n': len(es), 'mdape': round((math.exp(statistics.median(a)) - 1) * 100, 1), 'bias': round(statistics.median(es), 3),
            'w25': round(100 * sum(x <= math.log(1.25) for x in a) / len(a), 1), 'cov': round(100 * sum(r['cov'] for r in rs) / len(rs), 1) if key == 'eShown' else None}
sets = {
    'overall (clean titik)': lambda e: not e['outlier'],
    'all incl. outlier-flagged': lambda e: True,
    'text "jalan utama" (all)': lambda e: e['txtTier'] == 'utama',
    'arterial frontage text-tied': lambda e: e['corrHow'] == 'teks',
    'arterial corridor any-tie': lambda e: e['corr'] is not None,
    'Majapahit–Sudiarto tied': lambda e: e['corr'] == 'majapahit',
}
out = {}
names = sorted({k.split('|')[0] for k in R}, key=lambda x: list(R).index(x + '|loo'))
for mode in ('loo', 'cv'):
    print(f'\n===== {mode}')
    for sname, f in sets.items():
        print(' ', sname)
        for n in names:
            rs = [r for r in R[f'{n}|{mode}'] if r and f(E[r['id']])]
            s1 = st(rs); key = 'eAutoU' if 'frontage' in sname or 'corridor' in sname or 'Maja' in sname else None
            s2 = st(rs, 'eManU') if key else None
            out[f'{mode}|{sname}|{n}'] = {'shown': s1, 'manualUtama': s2}
            if key:
                rr = [r for r in rs if r.get('eRoadAuto') is not None]
                s3, s4 = st(rr, 'eRoadAuto'), st(rr, 'eRoadMan')
                out[f'{mode}|{sname}|{n}']['atRoadAuto'] = s3; out[f'{mode}|{sname}|{n}']['atRoadManual'] = s4
                if s3: print(f"    {n:12s} AT ROAD n={s3['n']:3d} shown {s3['mdape']:6.1f}% bias {s3['bias']:+.3f} ±25% {s3['w25']:5.1f} | manual-utama {s4['mdape']:6.1f}% bias {s4['bias']:+.3f}")
            print(f"    {n:12s} shown n={s1['n']:4d} {s1['mdape']:6.1f}% bias {s1['bias']:+.3f} ±25% {s1['w25']:5.1f} cov {s1['cov']:5.1f}" + (f" | manual-utama {s2['mdape']:6.1f}% bias {s2['bias']:+.3f}" if s2 else ''))
    # per kecamatan & per tingkat harga (clean)
    for gname, gf in (('kecamatan', lambda e: e['kec']), ('price-level quintile (kel medianRaw)', qbin)):
        print(f'  by {gname} (clean; mdape / bias)')
        groups = collections.defaultdict(lambda: collections.defaultdict(list))
        for n in names:
            for r in R[f'{n}|{mode}']:
                if r and not E[r['id']]['outlier']: groups[gf(E[r['id']])][n].append(r)
        for g in sorted(groups, key=lambda x: (x is None, str(x))):
            row = ' | '.join(f"{n}: {st(groups[g][n])['mdape']:5.1f} {st(groups[g][n])['bias']:+.2f}" for n in names if groups[g][n])
            out[f'{mode}|{gname}|{g}'] = {n: st(groups[g][n]) for n in names if groups[g][n]}
            print(f"    {str(g):18s} n={len(groups[g][names[0]]):4d}  {row}")
json.dump(out, open(sys.argv[4], 'w'), indent=0)
