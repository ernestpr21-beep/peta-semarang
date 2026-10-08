"""Assemble OSM boundary relations (out geom) into GeoJSON polygons for Kota Semarang,
kecamatan (admin_level 6) and kelurahan (admin_level 7). Data © OpenStreetMap contributors (ODbL)."""
import json
from shapely.geometry import LineString, Polygon, MultiPolygon, mapping, Point
from shapely.ops import linemerge, polygonize, unary_union
d = json.load(open('admin_geom.json'))
rels = [e for e in d['elements'] if e['type'] == 'relation']
def rel_poly(r):
    outers = []; inners = []
    for m in r['members']:
        if m['type'] != 'way' or 'geometry' not in m: continue
        ls = LineString([(p['lon'], p['lat']) for p in m['geometry']])
        (inners if m.get('role') == 'inner' else outers).append(ls)
    def build(lines):
        if not lines: return None
        u = unary_union(lines)
        polys = list(polygonize(u))
        return unary_union(polys) if polys else None
    o = build(outers); i = build(inners)
    if o is None: return None
    if i is not None: o = o.difference(i)
    return o
kota = None; kec = []; kel = []
for r in rels:
    lvl = r['tags'].get('admin_level'); g = rel_poly(r)
    if g is None or g.is_empty: print('EMPTY', r['tags'].get('name')); continue
    g = g.buffer(0)
    if lvl == '5': kota = g
    elif lvl == '6': kec.append((r, g))
    elif lvl == '7': kel.append((r, g))
canon = {'Gunung Pati': 'Gunungpati'}
def kname(n): return canon.get(n, n)
feats_kec = []
for r, g in kec:
    feats_kec.append({'type': 'Feature', 'properties': {'name': kname(r['tags']['name']), 'osm_id': r['id'], 'area_km2': round(g.area * 111.32**2 * 0.9926, 2)}, 'geometry': mapping(g.simplify(0.00005))})
feats_kel = []
for r, g in kel:
    c = g.representative_point()
    best = None
    for rk, gk in kec:
        a = g.intersection(gk).area
        if best is None or a > best[0]: best = (a, kname(rk['tags']['name']))
    feats_kel.append({'type': 'Feature', 'properties': {'name': r['tags']['name'], 'kecamatan': best[1], 'osm_id': r['id']}, 'geometry': mapping(g.simplify(0.00003))})
print('kec', len(feats_kec), 'kel', len(feats_kel))
from collections import Counter
print(Counter(f['properties']['kecamatan'] for f in feats_kel))
json.dump({'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'name': 'Kota Semarang', 'osm_id': 8409116}, 'geometry': mapping(kota.simplify(0.00005))}]}, open('kota.geojson', 'w'))
json.dump({'type': 'FeatureCollection', 'features': feats_kec}, open('kecamatan.geojson', 'w'))
json.dump({'type': 'FeatureCollection', 'features': feats_kel}, open('kelurahan.geojson', 'w'))
print('kota area km2', kota.area * 111.32**2 * 0.9926)
