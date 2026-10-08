"""Kampus perguruan tinggi dari OSM (amenity=university/college) → data/campus.json.
Poligon way + relation (outer), luas (ha), disederhanakan ±15 m. Dipakai untuk faktor kedekatan kampus."""
import json, gzip, os
from shapely.geometry import Polygon, LineString, mapping
from shapely.ops import polygonize, unary_union
from pyproj import Geod
from common import RAW, PUB, OUT

geod = Geod(ellps='WGS84')
d = json.load(gzip.open(os.path.join(RAW, 'osm', 'campus_raw.json.gz'), 'rt'))
items = []
for e in d['elements']:
    t = e.get('tags', {})
    if e['type'] == 'way' and 'geometry' in e:
        pts = [(p['lon'], p['lat']) for p in e['geometry']]
        if len(pts) < 4: continue
        geom = Polygon(pts).buffer(0)
    elif e['type'] == 'relation':
        lines = [LineString([(p['lon'], p['lat']) for p in m['geometry']]) for m in e.get('members', []) if m.get('role') in ('outer', '') and m.get('geometry')]
        polys = list(polygonize(unary_union(lines)))
        if not polys: continue
        geom = unary_union(polys)
    else:
        continue
    area = abs(geod.geometry_area_perimeter(geom)[0]) / 1e4
    items.append({'name': t.get('name') or t.get('amenity'), 'type': t.get('amenity'), 'osm': f"{e['type'][0]}{e['id']}", 'area_ha': round(area, 2), 'geom': geom})
# gabungkan bagian yang tumpang tindih (mis. way + relation untuk kampus yang sama) → ambil yang terbesar
items.sort(key=lambda x: -x['area_ha'])
kept = []
for it in items:
    if any(k['geom'].buffer(0).intersection(it['geom']).area > 0.5 * it['geom'].area for k in kept):
        continue
    kept.append(it)
out = []
for it in kept:
    g = it['geom'].simplify(0.00015, preserve_topology=True)
    polys = [g] if g.geom_type == 'Polygon' else list(g.geoms)
    rings = [[[round(y, 5), round(x, 5)] for x, y in p.exterior.coords] for p in polys if p.geom_type == 'Polygon']
    c = it['geom'].representative_point()
    out.append({'name': it['name'], 'type': it['type'], 'osm': it['osm'], 'areaHa': it['area_ha'], 'lat': round(c.y, 5), 'lng': round(c.x, 5), 'rings': rings})
json.dump({'osmBase': d['osm3s']['timestamp_osm_base'], 'campuses': out}, open(os.path.join(OUT, 'campus.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print(len(out), 'kampus;', sum(1 for o in out if o['areaHa'] >= 5), '≥5 ha')
for o in out[:16]: print(o['areaHa'], o['name'], o['lat'], o['lng'])
