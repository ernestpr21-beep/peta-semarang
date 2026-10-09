"""Koridor jalan arteri (2026-10-5): bukti harga iklan muka jalan per ruas arteri bernama (OSM trunk/primary).

Iklan dikaitkan ke satu ruas bila (a) judul/deskripsi menyebut bidang di muka/pinggir jalan itu ("pinggir jalan X",
judul "… di Jl. X") dan pin ≤ 1,5 km dari ruas itu, atau (b) pin ≤ 30 m dari ruas bernama trunk/primary/secondary.
Hanya ruas yang punya bagian trunk/primary (arteri) yang dipakai sebagai koridor. Dipakai oleh build_app_data.py;
diuji di analysis/audit/corridor_cv.py, corridor_cv2.py (leave-one-out & validasi silang blok spasial)."""
import glob, json, math, os, re, unicodedata
from collections import defaultdict
import numpy as np
from scipy.spatial import cKDTree
from common import PUB

KX, KY = 110500, 110574
# Satu jalan arteri menerus yang di OSM bernama dua: ruas timur "Brigjen Sudiarto" disebut "Jl. Majapahit" di iklan.
ALIASES = {'brigjen sudiarto': 'majapahit'}
TEXT_ALIAS = {'brigjen sudiarto': ['brigjen sudiarto', 'sudiarto'], 'soekarno hatta': ['soekarno hatta', 'sukarno hatta'], 'setiabudi': ['setiabudi', 'setia budi'],
              'kaligarang': ['kaligarang', 'kali garang'], 'arteri yos sudarso': ['arteri yos sudarso', 'yos sudarso'], 'teuku umar': ['teuku umar', 'teuku umat']}

def nn(s):
    """nama jalan ternormalisasi (sama dengan corridorKey() di src/lib/estimate.ts)"""
    s = unicodedata.normalize('NFKD', (s or '').lower())
    s = re.sub(r'\b(jalan|jl|jln|raya|ruas)\b\.?', ' ', s)
    s = s.replace('brigadir jenderal', 'brigjen').replace('letnan jenderal', 'letjen').replace('mayor jenderal', 'mayjen').replace('kiai haji', 'kh').replace('dokter', 'dr')
    s = re.sub(r'[^a-z0-9 ]', ' ', s); return re.sub(r'\s+', ' ', s).strip()
def key(name): k = nn(name); return ALIASES.get(k, k)

ROADS = defaultdict(list); CLS = defaultdict(set); _segs = []
for f in sorted(glob.glob(os.path.join(PUB, 'roads/*.json'))):
    for r in json.load(open(f)):
        hw = r['hw'].replace('_link', '')
        if r['c'] != 'utama' or hw not in ('trunk', 'primary', 'secondary', 'tertiary'): continue
        g = r['g']; nm = r.get('n') or ''
        for i in range(0, len(g) - 2, 2): _segs.append((g[i], g[i + 1], g[i + 2], g[i + 3], hw, nm))
        if not nm: continue
        k = nn(nm)
        if len(k) >= 4:
            ROADS[k] += [(g[i], g[i + 1]) for i in range(0, len(g), 2)]; CLS[k].add(hw)
ARTERIAL = {key(k) for k, c in CLS.items() if c & {'trunk', 'primary'}}
_mid = np.array([[(a[1] + a[3]) / 2 * KX, (a[0] + a[2]) / 2 * KY] for a in _segs]); _tree = cKDTree(_mid)
_rtree = {k: cKDTree(np.array([[b * KX, a * KY] for a, b in v])) for k, v in ROADS.items()}

def nearest_main(lat, lng):
    """(jarak m, kelas, nama) ruas jalan utama terdekat (≤ 400 m)"""
    p = np.array([lng * KX, lat * KY]); best = (9e9, None, '')
    for i in _tree.query_ball_point(p, 400):
        a = _segs[i]; x1, y1, x2, y2 = a[1] * KX, a[0] * KY, a[3] * KX, a[2] * KY
        dx, dy = x2 - x1, y2 - y1; t = max(0, min(1, ((p[0] - x1) * dx + (p[1] - y1) * dy) / (dx * dx + dy * dy or 1)))
        d = math.hypot(p[0] - x1 - t * dx, p[1] - y1 - t * dy)
        if d < best[0]: best = (d, a[4], a[5])
    return best

def dist_to(k, lat, lng):
    d, _ = _rtree[k].query([lng * KX, lat * KY]); return float(d)
def project(k, lat, lng):
    """titik OSM terdekat pada ruas k (gabungan alias)"""
    ks = [x for x in ROADS if key(x) == k]
    best = min(((dist_to(x, lat, lng), x) for x in ks))
    _, i = _rtree[best[1]].query([lng * KX, lat * KY]); return ROADS[best[1]][i]

_names = sorted(ROADS, key=len, reverse=True)
FRONT = r'(pinggir|tepi|depan|muka|hadap|menghadap|nempel|0 ?m dari|nol)\s+(jalan|jl\.?|jln\.?)?\s*(raya\s+|besar\s+)?'
def _mentions(text, front_only):
    t = nn(text) if not front_only else text.lower(); hits = []
    for k in _names:
        for a in TEXT_ALIAS.get(k, [k]):
            if (re.search(FRONT + re.escape(a), t) if front_only else re.search(r'\b' + re.escape(a) + r'\b', t)): hits.append(k)
    return list(dict.fromkeys(hits))
def text_road(title, desc, lat, lng):
    """ruas jalan utama yang disebut sebagai muka bidang dalam teks iklan → (nama ternormalisasi, jarak pin ke ruas) atau None"""
    m = re.search(r'\bdi\s+(jl\.?|jln\.?|jalan)\s*(raya\s+)?([^,|]+)$', title or '', re.I)
    ks = list(dict.fromkeys(_mentions(title + ' \n ' + (desc or '')[:1500], True) + (_mentions('jalan ' + m.group(3), False) if m else [])))
    if not ks: return None
    k = min(ks, key=lambda k: dist_to(k, lat, lng)); return k, dist_to(k, lat, lng)

def tie(r, lat, lng):
    """(kunci koridor arteri, cara: teks|pin) untuk iklan, atau (None, None)"""
    tr = text_road(r.get('title') or '', r.get('description') or '', lat, lng)
    if tr and tr[1] <= 1500: k, how = key(tr[0]), 'teks'
    else:
        d, hw, nm = nearest_main(lat, lng)
        k, how = (key(nm) if (d <= 30 and hw in ('trunk', 'primary', 'secondary') and nm) else None), 'pin'
    return (k, how) if k in ARTERIAL else (None, None)

def premium(pts, lat, lng, k_prior, bw, exclude=lambda i: False):
    """premi log koridor di (lat, lng): median berbobot Gauss(jarak/bw) residu iklan ruas yang sama, disusutkan ke 0 (kekuatan k_prior)"""
    ws, vs = [], []
    for i, (a, b, v) in enumerate(pts):
        if exclude(i): continue
        w = math.exp(-0.5 * (math.hypot((a - lat) * KY, (b - lng) * KX) / bw) ** 2)
        if w > 0.01: ws.append(w); vs.append(v)
    if not ws: return 0.0, 0.0
    o = sorted(range(len(vs)), key=lambda i: vs[i]); tot = sum(ws); acc = 0; med = vs[o[-1]]
    for i in o:
        acc += ws[i]
        if acc >= 0.5 * tot: med = vs[i]; break
    neff = tot ** 2 / sum(w * w for w in ws)
    return neff * med / (neff + k_prior), neff
