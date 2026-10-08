"""Port Python dari src/lib/access.ts — deteksi kelas akses dari jalan OSM terdekat (ubin public/data/roads)."""
import json, math, os
from functools import lru_cache
from common import PUB

TILE = 0.01
FRONTAGE, NARROW, INNER = 30, 25, 60

@lru_cache(maxsize=2048)
def tile(ix, iy):
    p = os.path.join(PUB, 'roads', f'{ix}_{iy}.json')
    return json.load(open(p)) if os.path.exists(p) else []

def roads_near(lat, lng):
    ix, iy = math.floor(lng / TILE), math.floor(lat / TILE)
    seen = set(); out = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for r in tile(ix + dx, iy + dy):
                k = id(r)
                if k not in seen:
                    seen.add(k); out.append(r)
    return out

def seg_dist(ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0 if l2 == 0 else max(0, min(1, -(ax * dx + ay * dy) / l2))
    x, y = ax + t * dx, ay + t * dy
    return math.hypot(x, y)

def nearest(lat, lng):
    kx = math.pi / 180 * 6371008.8 * math.cos(math.radians(lat)); ky = math.pi / 180 * 6371008.8
    best = {}
    for r in roads_near(lat, lng):
        g = r['g']; dmin = 1e18
        px, py = (g[1] - lng) * kx, (g[0] - lat) * ky
        for i in range(2, len(g), 2):
            qx, qy = (g[i + 1] - lng) * kx, (g[i] - lat) * ky
            if not (min(px, qx) > 400 or max(px, qx) < -400 or min(py, qy) > 400 or max(py, qy) < -400):
                d = seg_dist(px, py, qx, qy)
                if d < dmin: dmin = d
            px, py = qx, qy
        c = r['c']
        if dmin < 1e18 and (c not in best or dmin < best[c][0]):
            best[c] = (dmin, r.get('w'))
    return best

def detect(lat, lng):
    b = nearest(lat, lng)
    u = b.get('utama'); l = b.get('lingkungan')
    nar = min([x for x in (b.get('gang'), b.get('setapak')) if x], default=None, key=lambda x: x[0])
    drv = min([x for x in (u, l) if x], default=None, key=lambda x: x[0])
    if u and u[0] <= FRONTAGE: t = 'utama'
    elif l and l[0] <= FRONTAGE: t = 'gang' if (l[1] is not None and l[1] < 3) else 'lingkungan'
    elif nar and nar[0] <= NARROW: t = 'gang'
    elif drv and drv[0] <= INNER: t = 'gang'
    else: t = 'tanpa'
    return t, (drv[0] if drv else None), (u[0] if u else None)
