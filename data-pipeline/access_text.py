"""Klasifikasi kondisi akses jalan dari teks iklan (judul + deskripsi).

Tingkat (tier):
  utama       — bidang di pinggir / muka jalan raya / jalan utama (arteri-kolektor)
  lingkungan  — ada akses jalan yang bisa dilalui mobil (jalan lingkungan/perumahan)
  gang        — hanya gang sempit / jalan setapak / akses motor
  tanpa       — tanpa akses jalan (tanah terkurung / belum ada jalan)
Mengembalikan (tier atau None, alasan, lebar_jalan_m atau None).
"""
import re

NUM = r'(\d+(?:[.,]\d+)?)'

TANPA = [
    r'tanpa\s+akses', r'tidak\s+(?:ada|punya|memiliki)\s+akses', r'tdk\s+(?:ada\s+)?akses', r'belum\s+(?:ada|punya)\s+(?:akses|jalan)',
    r'akses\s+(?:jalan\s+)?belum\s+(?:ada|tersedia|dibuka)', r'tanah\s+(?:ter)?kurung', r'\blandlocked\b', r'tidak\s+ada\s+jalan(?:\s+masuk)?',
    r'tanpa\s+jalan(?:\s+masuk)?', r'akses\s+(?:lewat|melalui|numpang)\s+(?:tanah|lahan|pekarangan|sawah|kebun)\s+(?:orang|warga|tetangga)',
    r'jalan\s+masuk\s+belum\s+ada', r'belum\s+ada\s+jalan\s+masuk',
]
GANG = [
    r'masuk\s+gang', r'\bgang\s+(?:sempit|kecil|kampung)', r'\bgg\.?\s+sempit', r'jalan\s+setapak', r'akses\s+(?:hanya\s+)?(?:sepeda\s+)?motor\b', r'akses\s+jalan\s+(?:hanya\s+)?(?:sepeda\s+)?motor\b',
    r'hanya\s+(?:bisa\s+)?(?:dilalui|dilewati|masuk)\s+motor', r'mobil\s+(?:tidak|tdk|belum|blm)\s+(?:bisa\s+)?(?:masuk|lewat|sampai)',
    r'(?:tidak|tdk|belum|blm)\s+(?:bisa\s+)?(?:dilalui|dilewati|masuk)\s+mobil', r'akses\s+(?:jalan\s+)?(?:kaki|setapak)', r'jalan\s+(?:kecil|sempit)\b',
    r'motor\s+saja', r'akses\s+gang', r'\bdalam\s+gang\b', r'di\s+gang\b',
    # alamat di gang bernama: "gang flamboyan", "gg. pete" (indikasi lemah: jalan sempit)
    r'(?:^|[\s,(])(?:gang|gg\.?)\s+(?!buntu|kavling|utama|besar|lebar)[a-z0-9]{2,}',
]
UTAMA = [
    r'(?:pinggir|tepi|muka|depan|hadap|nol|0)\s+(?:jalan|jl\.?|jln\.?)\s*(?:raya|besar|utama|provinsi|protokol|nasional|arteri|propinsi)',
    r'(?:pinggir|tepi|muka|hadap)\s+(?:jalan|jl\.?|jln\.?)\s+(?:raya\s+)?(?:majapahit|setiabudi|setia\s*budi|pemuda|pandanaran|gajah\s*mada|ahmad\s*yani|a\.?\s*yani|soekarno|sukarno|kaligawe|walisongo|siliwangi|brigjend|sudirman|imam\s*bonjol|kedungmundu|fatmawati|ngaliyan|prof\.?\s*hamka|hamka|mataram|dr\.?\s*cipto|diponegoro|tentara\s*pelajar|veteran|sultan\s*agung|sriwijaya|perintis|jatingaleh|banyumanik)',
    r'(?:lokasi|letak|berada)\s+(?:di\s+)?(?:pinggir|tepi)\s+jalan\s+(?:raya|besar|utama)', r'\bnol\s+jalan\b', r'\b0\s*m(?:eter)?\s+(?:dari\s+)?jalan\s+raya',
    r'pinggir\s+jalan\s+(?:raya|besar|utama|provinsi|propinsi|nasional)', r'tepi\s+jalan\s+(?:raya|besar|utama)', r'muka\s+jalan\s+raya', r'frontage',
    r'(?:pinggir|tepi)\s+jl\.?\s+raya', r'akses\s+(?:langsung\s+)?(?:jalan\s+)?raya\s+(?:provinsi|nasional|propinsi)',
]
LING = [
    r'akses\s+(?:jalan\s+)?mobil', r'(?:bisa|dapat)\s+(?:dilalui|dilewati|masuk)\s+mobil', r'mobil\s+(?:bisa\s+)?(?:masuk|sampai|papasan)', r'papasan\s+mobil',
    r'\b2\s*mobil\b', r'dua\s+mobil', r'jalan\s+(?:lebar|aspal|cor|beton|paving)', r'akses\s+jalan\s+(?:lebar|aspal|cor|beton|bagus|mudah)',
    r'pinggir\s+jalan\b(?!\s+(?:raya|besar|utama|provinsi|propinsi|nasional))', r'row\s+jalan', r'jalan\s+(?:lingkungan|perumahan|kampung)',
    r'truk\s+(?:bisa\s+)?masuk', r'truck\s+masuk', r'container\s+masuk', r'kontainer\s+(?:bisa\s+)?masuk',
]

WIDTH_PATTERNS = [
    rf'(?:lebar|lbr|row)\s*(?:jalan|jln|jl)?\.?\s*(?:depan|masuk|akses|lingkungan)?\s*[:±+\-~]*\s*(?:kurang\s+lebih|kl|sekitar|\+-|±)?\s*{NUM}\s*(?:m|meter|mtr|meteran)\b',
    rf'(?:akses|jalan)\s*(?:masuk|depan)?\s*(?:lebar)?\s*[:±~]*\s*{NUM}\s*(?:m|meter|mtr)\b(?!\s*(?:dari|ke|menuju|²|2\b))',
]


NEG = re.compile(r'(?:bukan|tidak|tdk|gak|ga|nggak|enggak|tak|tanpa|anti|jauh\s+dari|no)\s+(?:\w+\s*){0,2}$')


def _any(pats, t):
    for p in pats:
        for m in re.finditer(p, t):
            before = t[max(0, m.start() - 25):m.start()]
            if NEG.search(before) and not p.startswith('tanpa') and not p.startswith('tidak'):
                continue  # mis. "bukan gang buntu", "gak masuk gang"
            return m.group(0)
    return None


def road_width(t):
    for p in WIDTH_PATTERNS:
        for m in re.finditer(p, t):
            try:
                w = float(m.group(1).replace(',', '.'))
            except ValueError:
                continue
            # buang angka yang jelas bukan lebar jalan (mis. luas, jarak km)
            if 0.8 <= w <= 40:
                after = t[m.end():m.end() + 6]
                if re.match(r'\s*(?:x|×)\s*\d', after):
                    continue  # "lebar 10 x 20" = dimensi bidang
                return w, m.group(0)
    return None, None


def classify_access(title, desc):
    t = f"{title or ''}\n{desc or ''}".lower()
    t = re.sub(r'\s+', ' ', t)
    hit = _any(TANPA, t)
    if hit:
        return 'tanpa', hit, None
    w, wtxt = road_width(t)
    g = _any(GANG, t)
    if g and not (w and w >= 4):
        return 'gang', g, w
    if w is not None:
        if w < 3:
            return 'gang', f'lebar jalan {w:g} m ({wtxt})', w
        if w >= 8:
            return 'utama', f'lebar jalan {w:g} m ({wtxt})', w
    u = _any(UTAMA, t)
    if u:
        return 'utama', u, w
    if w is not None:
        return 'lingkungan', f'lebar jalan {w:g} m ({wtxt})', w
    l = _any(LING, t)
    if l:
        return 'lingkungan', l, w
    return None, None, w


if __name__ == '__main__':
    tests = [
        ('Tanah pinggir jalan raya Majapahit', ''), ('Tanah murah', 'akses jalan 2,5 meter, motor saja'), ('Kavling', 'Akses mobil papasan, jalan cor'),
        ('Tanah sawah', 'tanpa akses jalan, cocok untuk investasi'), ('Tanah', 'lebar jalan depan 12 m'), ('Tanah', 'dekat jalan raya 5 menit'),
        ('Tanah', 'masuk gang sempit 50 m'), ('Tanah', 'lebar 10 x 20 m pinggir jalan'),
    ]
    for a, b in tests:
        print(a, '|', b, '→', classify_access(a, b))
