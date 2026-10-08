"""Fungsi bersama pipeline data Peta Semarang."""
import json, re, os, unicodedata
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW = os.path.join(ROOT, 'data-raw')
OUT = os.path.join(ROOT, 'data')
PUB = os.path.join(ROOT, 'public', 'data')


def norm(s):
    s = (s or '').lower()
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'^(kel\.|kelurahan|kec\.|kecamatan|desa)\s+', '', s.strip())
    return re.sub(r'[^a-z0-9]', '', s)


def fix_mojibake(s):
    """Perbaiki teks UTF-8 yang terbaca sebagai latin-1 (mis. 'mÂ²')."""
    if not s or not isinstance(s, str):
        return s
    if 'Â' in s or 'â' in s or 'Ã' in s:
        try:
            return s.encode('latin-1').decode('utf-8')
        except Exception:
            try:
                return s.encode('cp1252', errors='ignore').decode('utf-8', errors='ignore')
            except Exception:
                return s
    return s


def strip_html(s):
    s = re.sub(r'<br\s*/?>|</p>|</li>', '\n', s or '')
    s = re.sub(r'<[^>]+>', ' ', s)
    s = s.replace('&nbsp;', ' ').replace('&amp;', '&')
    return re.sub(r'[ \t]+', ' ', s).strip()


class Admin:
    def __init__(self):
        osm = os.path.join(RAW, 'osm')
        self.kota = shape(json.load(open(os.path.join(osm, 'kota.geojson')))['features'][0]['geometry'])
        self.kec = [(f['properties']['name'], shape(f['geometry'])) for f in json.load(open(os.path.join(osm, 'kecamatan.geojson')))['features']]
        self.kel = [(f['properties']['name'], f['properties']['kecamatan'], shape(f['geometry'])) for f in json.load(open(os.path.join(osm, 'kelurahan.geojson')))['features']]
        self.kel_tree = STRtree([g for _, _, g in self.kel])
        self.kel_by_norm = {}
        for name, kec, g in self.kel:
            self.kel_by_norm.setdefault(norm(name), []).append((name, kec, g))
        # alias penulisan umum di iklan
        aliases = {
            'gunungpati': 'gunungpati', 'gunungpati gunungpati': 'gunungpati', 'tanjungmas': 'tanjungmas', 'tambakharjo': 'tambakharjo',
            'kalibantengkidul': 'kalibantengkidul', 'ngemplak simongan': 'ngemplaksimongan', 'tambakaji': 'tambakaji',
            'jatibarang1': 'jatibarang', 'bambankerep': 'bambankerep', 'karangayu': 'karangayu', 'gajahmungkur': 'gajahmungkur',
            'bulustalan': 'bulustalan', 'salamanmloyo': 'salamanmloyo', 'mugasari': 'mugassari', 'mangunharjo': 'mangunharjo',
            'tlogosari': 'tlogosarikulon', 'muktiharjo': 'muktiharjokidul', 'pedurungan': 'pedurungantengah', 'srondol': 'srondolwetan',
        }
        self.alias = aliases

    def inside_city(self, lat, lng):
        return self.kota.buffer(0.0005).contains(Point(lng, lat))

    def kel_at(self, lat, lng):
        p = Point(lng, lat)
        for i in self.kel_tree.query(p):
            name, kec, g = self.kel[i]
            if g.contains(p):
                return name, kec
        return None, None

    def kel_by_name(self, name, kec=None):
        n = norm(name)
        n = self.alias.get(n, n)
        c = self.kel_by_norm.get(n)
        if not c:
            return None
        if kec:
            for x in c:
                if norm(x[1]) == norm(kec):
                    return x
        return c[0]

    def kel_center(self, name, kec=None):
        x = self.kel_by_name(name, kec)
        if not x:
            return None
        p = x[2].representative_point()
        return (p.y, p.x, x[0], x[1])

    def dist_to_kel_m(self, lat, lng, name, kec=None):
        x = self.kel_by_name(name, kec)
        if not x:
            return None
        return x[2].distance(Point(lng, lat)) * 111000

    def kec_names(self):
        return [k for k, _ in self.kec]


_PHONE = re.compile(r'(?<!\d)(?:\+?62|0)\s?8[\d\s\-\.]{7,15}\d')
_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
_WA = re.compile(r'(?:https?://)?(?:wa\.me|wa\.link|api\.whatsapp\.com|chat\.whatsapp\.com|whatsapp\.com/send)(?:/\S*)?', re.I)
# nomor yang sebagian sudah disamarkan portal (mis. "08xx xxxx ----") tetap dihapus
_PHONE_MASKED = re.compile(r'(?<!\d)(?:\+?62|0)\s?8[\d\s\.\-]{2,14}(?:-{2,}|x{2,}|\*{2,})', re.I)


def scrub_contacts(t):
    """Hapus nomor telepon/WA & email dari teks iklan (data agen/penjual tidak ikut dipublikasikan)."""
    if not t:
        return t
    t = _WA.sub('[kontak dihapus]', t)
    t = _EMAIL.sub('[kontak dihapus]', t)
    t = _PHONE_MASKED.sub('[kontak dihapus]', t)
    return _PHONE.sub('[kontak dihapus]', t)


def url_has_contact(u):
    """URL iklan yang slug-nya memuat nomor telepon/WA (mis. judul Pinhome berisi nomor) → tidak dipublikasikan."""
    if not u:
        return False
    slug = u.rstrip('/').rsplit('/', 1)[-1]
    return bool(_PHONE.search(slug) or _EMAIL.search(slug) or _WA.search(u))
