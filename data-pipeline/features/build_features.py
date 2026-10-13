"""Raster fitur wilayah (25 m) untuk model harga berbasis fitur (model 2026-10-8). Semua data gratis:
OSM (jalan, bangunan, tata guna lahan, sungai, pantai, fasilitas), ESA WorldCover 2021 (10 m), Copernicus GLO-30 DEM.
Keluaran: data-pipeline/.cache/features.npz (lapisan fitur) — dibaca sampler.py. Butuh rasterio, shapely, scipy."""
import gzip, json, math, os, glob
import numpy as np, rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from rasterio.merge import merge
from scipy import ndimage
from shapely.geometry import shape, LineString, Polygon, MultiPolygon
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(ROOT, 'data-raw/osm'); CACHE = os.path.join(ROOT, 'data-pipeline/.cache')
W, S, E, N = 110.247, -7.135, 110.529, -6.908
RES_M = 25.0
DX = RES_M / (111320 * math.cos(math.radians(-7.02))); DY = RES_M / 110574
NX = int(math.ceil((E - W) / DX)); NY = int(math.ceil((N - S) / DY))
TR = from_origin(W, N, DX, DY)
def burn(geoms, all_touched=True):
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms: return np.zeros((NY, NX), np.uint8)
    return rasterize(((g, 1) for g in geoms), out_shape=(NY, NX), transform=TR, all_touched=all_touched, dtype=np.uint8)
def pts_count(latlng):
    a = np.zeros((NY, NX), np.float32)
    for lat, lng in latlng:
        i = int((N - lat) / DY); j = int((lng - W) / DX)
        if 0 <= i < NY and 0 <= j < NX: a[i, j] += 1
    return a
def dist_m(mask):  # jarak (m) ke sel bernilai 1
    if not mask.any(): return np.full((NY, NX), 2e4, np.float32)
    return (ndimage.distance_transform_edt(mask == 0) * RES_M).astype(np.float32)
def focal_mean(a, radius_m):
    k = int(round(radius_m / RES_M))
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]; disk = ((yy ** 2 + xx ** 2) <= k * k).astype(np.float32)
    from scipy.signal import fftconvolve
    return (fftconvolve(a.astype(np.float32), disk, mode='same') / disk.sum()).astype(np.float32)
def focal_sum(a, radius_m): return focal_mean(a, radius_m) * (math.pi * (radius_m / RES_M) ** 2)
L = {}
# --- WorldCover 2021 ---
wc = rasterio.open(os.path.join(CACHE, 'wc/worldcover_smg.tif'))
def wc_share(classes):
    src = np.isin(wc.read(1), classes).astype(np.float32); dst = np.zeros((NY, NX), np.float32)
    reproject(src, dst, src_transform=wc.transform, src_crs=wc.crs, dst_transform=TR, dst_crs=wc.crs, resampling=Resampling.average); return dst
built = wc_share([50]); tree = wc_share([10]); crop = wc_share([40]); grass = wc_share([20, 30]); water = wc_share([80, 90, 95])
L['built_250'] = focal_mean(built, 250); L['built_1000'] = focal_mean(built, 1000); L['built_2500'] = focal_mean(built, 2500)
L['tree_500'] = focal_mean(tree, 500); L['crop_500'] = focal_mean(crop, 500); L['grass_500'] = focal_mean(grass, 500)
L['water_500'] = focal_mean(water, 500)
# --- DEM ---
D = os.path.join(CACHE, 'dem')
arr, dtr = merge([rasterio.open(f) for f in sorted(glob.glob(os.path.join(D, '*.tif')))], bounds=(W - 0.01, S - 0.01, E + 0.01, N + 0.01))
dem = np.zeros((NY, NX), np.float32)
reproject(arr[0].astype(np.float32), dem, src_transform=dtr, src_crs='EPSG:4326', dst_transform=TR, dst_crs='EPSG:4326', resampling=Resampling.bilinear)
gy, gx = np.gradient(ndimage.uniform_filter(dem, 3), RES_M, RES_M)
slope = np.degrees(np.arctan(np.hypot(gx, gy)))
L['elev'] = ndimage.uniform_filter(dem, 5); L['slope_250'] = focal_mean(slope, 250)
# --- jalan ---
cls_of = {'motorway': 'tol', 'motorway_link': 'tol', 'trunk': 'art', 'trunk_link': 'art', 'primary': 'art', 'primary_link': 'art', 'secondary': 'sec', 'secondary_link': 'sec', 'tertiary': 'ter', 'tertiary_link': 'ter',
          'residential': 'res', 'unclassified': 'res', 'living_street': 'res', 'road': 'res', 'service': 'svc', 'track': 'svc'}
lines = {k: [] for k in set(cls_of.values())}
for f in glob.glob(os.path.join(RAW, 'roads_*.json.gz')):
    for e in json.load(gzip.open(f))['elements']:
        c = cls_of.get(e.get('tags', {}).get('highway'))
        if c and len(e.get('geometry', [])) >= 2: lines[c].append(LineString([(p['lon'], p['lat']) for p in e['geometry']]))
R = {k: burn(v) for k, v in lines.items()}
drive = np.clip(sum(R[k] for k in ('tol', 'art', 'sec', 'ter', 'res', 'svc')), 0, 1)
L['roaddens_500'] = focal_mean(drive, 500)
L['d_art'] = dist_m(R['art']); L['d_sec'] = dist_m(np.clip(R['art'] + R['sec'], 0, 1)); L['d_drive'] = dist_m(drive)
# --- fasilitas ---
fac = json.load(gzip.open(os.path.join(RAW, 'facilities_raw.json.gz')))['elements']
def fpts(pred):
    out = []
    for e in fac:
        t = e.get('tags', {}); lat = e.get('lat') or e.get('center', {}).get('lat'); lng = e.get('lon') or e.get('center', {}).get('lon')
        if lat and pred(t): out.append((lat, lng))
    return out
comm = pts_count(fpts(lambda t: t.get('shop') in ('supermarket', 'convenience', 'mall', 'department_store') or t.get('amenity') in ('bank', 'marketplace', 'fuel')))
L['poi_comm_1000'] = focal_sum(comm, 1000); L['poi_comm_3000'] = focal_sum(comm, 3000)
L['d_mall'] = dist_m(pts_count(fpts(lambda t: t.get('shop') in ('mall', 'department_store'))) > 0)
L['d_market'] = dist_m(pts_count(fpts(lambda t: t.get('amenity') == 'marketplace')) > 0)
L['school_1000'] = focal_sum(pts_count(fpts(lambda t: t.get('amenity') in ('school', 'kindergarten'))), 1000)
L['health_1500'] = focal_sum(pts_count(fpts(lambda t: t.get('amenity') in ('hospital', 'clinic') or t.get('healthcare') in ('hospital', 'clinic'))), 1500)
L['d_toll'] = dist_m(np.clip(pts_count(fpts(lambda t: t.get('barrier') == 'toll_booth' or t.get('highway') == 'motorway_junction')), 0, 1) + R['tol'] * 0 > 0)
# pusat kota (Simpang Lima)
yy, xx = np.mgrid[0:NY, 0:NX]
lat_c = N - (yy + 0.5) * DY; lng_c = W + (xx + 0.5) * DX
L['d_cbd'] = (np.hypot((lat_c + 6.99050) * 110574, (lng_c - 110.42290) * 110574 * math.cos(math.radians(7.0)))).astype(np.float32)
# --- tata guna lahan OSM ---
def osm_polys(path, pred):
    out = []
    for e in json.load(gzip.open(path))['elements']:
        t = e.get('tags', {})
        if not pred(t): continue
        if e['type'] == 'way' and len(e.get('geometry', [])) >= 4:
            out.append(Polygon([(p['lon'], p['lat']) for p in e['geometry']]).buffer(0))
        elif e['type'] == 'relation':
            outer = [Polygon([(p['lon'], p['lat']) for p in m['geometry']]) for m in e.get('members', []) if m.get('role') == 'outer' and len(m.get('geometry', [])) >= 4]
            out += [o.buffer(0) for o in outer]
    return out
lu = os.path.join(RAW, 'features/lu.json.gz')
if os.path.exists(lu):
    L['ind_500'] = focal_mean(burn(osm_polys(lu, lambda t: t.get('landuse') in ('industrial', 'port')), False).astype(np.float32), 500)
    L['comlu_500'] = focal_mean(burn(osm_polys(lu, lambda t: t.get('landuse') in ('commercial', 'retail')), False).astype(np.float32), 500)
# --- sungai & pantai ---
wat = os.path.join(RAW, 'features/wat.json.gz')
if os.path.exists(wat):
    el = json.load(gzip.open(wat))['elements']
    riv = [LineString([(p['lon'], p['lat']) for p in e['geometry']]) for e in el if e.get('tags', {}).get('waterway') in ('river', 'canal') and len(e.get('geometry', [])) >= 2]
    coast = [LineString([(p['lon'], p['lat']) for p in e['geometry']]) for e in el if e.get('tags', {}).get('natural') == 'coastline' and len(e.get('geometry', [])) >= 2]
    L['d_river'] = dist_m(burn(riv))
    sea = burn(coast)
    L['d_coast'] = dist_m(sea) if sea.any() else None
if L.get('d_coast') is None:  # cadangan: air WorldCover di utara
    L['d_coast'] = dist_m(((water > 0.5) & (lat_c > -6.97)).astype(np.uint8))
# rawan rob: elevasi < 4 m dan ≤ 4 km dari pantai — pangsa dalam 250 m
L['rob_250'] = focal_mean(((L['elev'] < 4) & (L['d_coast'] < 4000)).astype(np.float32), 250)
# --- bangunan OSM ---
bf = sorted(glob.glob(os.path.join(RAW, 'features/bld_*.json.gz')))
if len(bf) == 9:
    pts = []
    for f in bf:
        for e in json.load(gzip.open(f))['elements']:
            c = e.get('center')
            if c: pts.append((c['lat'], c['lon']))
    print('bangunan OSM', len(pts))
    L['bld_250'] = focal_sum(pts_count(pts), 250) / (math.pi * 0.25 ** 2 * 100)  # per ha
L = {k: v for k, v in L.items() if v is not None}
# --- agregat per kelurahan & kecamatan (karakter wilayah): rata-rata lapisan di dalam poligon ---
kg = json.load(open(os.path.join(ROOT, 'public/data/kelurahan.geojson')))['features']
lab = rasterize(((shape(f['geometry']), i + 1) for i, f in enumerate(kg)), out_shape=(NY, NX), transform=TR, dtype=np.int32)
kec_names = sorted({f['properties']['kecamatan'] for f in kg}); kec_of = np.array([0] + [kec_names.index(f['properties']['kecamatan']) + 1 for f in kg])
labc = kec_of[lab] * (lab > 0)
AGG = ['built_250', 'bld_250', 'slope_250', 'elev', 'poi_comm_1000', 'tree_500', 'crop_500', 'roaddens_500', 'rob_250', 'ind_500']
for k in [a for a in AGG if a in L]:
    src = L[k] if k not in ('bld_250', 'poi_comm_1000') else np.log1p(np.maximum(L[k], 0))
    mk = np.array([0] + list(ndimage.mean(src, lab, np.arange(1, len(kg) + 1)))); L['kel_' + k] = np.nan_to_num(mk[lab]).astype(np.float32)
    mc = np.array([0] + list(ndimage.mean(src, labc, np.arange(1, len(kec_names) + 1)))); L['kec_' + k] = np.nan_to_num(mc[labc]).astype(np.float32)
L['_kel_label'] = lab
np.savez_compressed(os.path.join(CACHE, 'features.npz'), **L, _meta=np.array([W, N, DX, DY, NX, NY]))
for k, v in L.items():
    if k.startswith('_'): continue
    print(f'{k:14s} p5 {np.percentile(v, 5):9.3f} p50 {np.percentile(v, 50):9.3f} p95 {np.percentile(v, 95):9.3f}')
