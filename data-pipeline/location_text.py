"""Cek konsistensi lokasi: nama tempat yang disebut di judul/deskripsi iklan vs koordinat pin.

Banyak iklan kavling (mis. "dekat Unnes", "daerah Meteseh") memakai pin di tengah kota (alamat kantor
agen / alamat yang salah ketik). Bila SEMUA tempat yang disebut iklan berjarak > CONFLICT_M dari pin,
dan tempat-tempat itu saling berdekatan (satu kawasan), lokasi iklan dipindah ke kawasan yang disebut.
Bagian alamat Pinhome ("... di <alamat>") tidak ikut dipindai karena pin berasal dari alamat itu.
"""
import re
from shapely.geometry import Point
from common import norm

CONFLICT_M = 3000           # untuk nama kelurahan (jarak ke poligon)
CONFLICT_LANDMARK_M = 4000  # untuk landmark ("dekat Unnes" bisa beberapa km)
CONFLICT_KEC_M = 1500       # untuk nama kecamatan (jarak ke poligon kecamatan)
COHERENT_M = 3000
# nama kelurahan yang juga kata umum / nama tempat lain → tidak dipakai
SKIP = {'candi', 'kudu', 'wates', 'gemah', 'bendungan', 'pesantren', 'karanganyar', 'tugu', 'kauman', 'tandang', 'krapyak',
        'kuningan', 'jatisari', 'tegalsari', 'wonosari', 'purwosari', 'karangrejo', 'sukorejo', 'rejosari', 'sambirejo', 'jatirejo'}
# landmark → (lat, lng, kelurahan acuan atau None bila di luar kota)
LANDMARKS = {  # pola → [(lat, lng, kelurahan acuan atau None bila di luar kota), ...] (beberapa kampus)
    r'\bunnes\b|universitas negeri semarang': [(-7.0510, 110.3930, 'Sekaran')],
    r'pasca ?sarjana unnes|unnes kelud|unnes bendan': [(-7.0035, 110.4030, 'Bendan Ngisor')],
    r'\bundip\b|diponegoro': [(-7.0505, 110.4380, 'Tembalang')],
    r'undip pleburan|pleburan': [(-6.9925, 110.4195, 'Pleburan')],
    r'simpang ?lima': [(-6.9905, 110.4229, 'Pleburan')],
    r'tugu muda': [(-6.9840, 110.4093, 'Sekayu')],
    r'\bunimus\b': [(-7.0237, 110.4589, 'Kedungmundu')],
    r'\bpolines\b': [(-7.0526, 110.4360, 'Tembalang')],
    r'\budinus\b': [(-6.9822, 110.4091, 'Pendrikan Kidul')],
    r'\bunika\b|soegijapranata': [(-7.0035, 110.4010, 'Bendan Duwur')],
    r'\bbsb\b|bukit semarang baru': [(-7.0420, 110.3290, 'Jatisari')],
    r'\bungaran\b': [(-7.1390, 110.4050, None)],
    r'\bkendal\b': [(-6.9220, 110.2040, None)],
    r'\bdemak\b': [(-6.8940, 110.6370, None)],
    r'\bboja\b': [(-7.1070, 110.2830, None)],
}

class TextLocator:
    def __init__(self, A):
        self.A = A
        # (regex, [(geom|None, (lat,lng)|None)], kel, kec, label, ambang m)
        self.places = []
        kec_geom = {norm(n): (n, g) for n, g in A.kec}
        for name, kec, g in A.kel:
            key = norm(name)
            if key in SKIP or len(key) < 5:
                continue
            words = re.findall(r'[a-z]+', name.lower())
            pat = re.compile(r'\b' + r'\s?'.join(words) + r'\b')
            if key in kec_geom:  # "Tembalang", "Mijen", ... umumnya berarti kecamatan
                kn, kg = kec_geom[key]
                self.places.append((pat, [(kg, None)], None, kn, name, CONFLICT_KEC_M))
            else:
                self.places.append((pat, [(g, None)], name, kec, name, CONFLICT_M))
        names_done = {norm(p[4]) for p in self.places}
        for key, (name, g) in kec_geom.items():
            if key in SKIP or key in names_done:
                continue
            words = re.findall(r'[a-z]+', name.lower())
            self.places.append((re.compile(r'\b' + r'\s?'.join(words) + r'\b'), [(g, None)], None, name, name, CONFLICT_KEC_M))
        for rx, pts in LANDMARKS.items():
            kel = pts[0][2]
            kec = None
            if kel:
                x = A.kel_by_name(kel)
                kec = x[1] if x else None
            label = re.sub(r'\\b', '', rx.split('|')[0]).replace(' ?', ' ')
            if len(pts) > 1:
                kel = None; kec = None  # beberapa kampus → tidak dipakai untuk memindah lokasi
            self.places.append((re.compile(rx), [(None, (p[0], p[1])) for p in pts], kel, kec, label, CONFLICT_LANDMARK_M))

    def mentions(self, text):
        t = text.lower()
        return [p[1:] for p in self.places if p[0].search(t)]

    @staticmethod
    def _dist_m(lat, lng, g, pt):
        if g is not None:
            return g.distance(Point(lng, lat)) * 111000
        return ((lat - pt[0]) ** 2 + ((lng - pt[1]) * 0.993) ** 2) ** 0.5 * 111000

    def check(self, lat, lng, text):
        """→ None (konsisten / tak ada sebutan / sebutan tersebar) atau dict lokasi pengganti."""
        ms = self.mentions(text)
        if not ms:
            return None
        # konsisten bila ada SATU sebutan yang dekat pin
        for geoms, kel, kec, label, thr in ms:
            if min(self._dist_m(lat, lng, g, pt) for g, pt in geoms) <= thr:
                return None
        names = sorted({m[3] for m in ms})
        why = f'teks menyebut {", ".join(names)}, semuanya jauh dari pin'
        inside = [m for m in ms if m[2]]  # sebutan dalam kota dengan kecamatan jelas
        if not inside:  # hanya landmark luar kota / kampus ganda → tidak cukup untuk memindah
            return None
        reps = []
        for geoms, kel, kec, label, thr in inside:
            g, pt = geoms[0]
            if pt is None:
                c = g.representative_point(); pt = (c.y, c.x)
            reps.append(pt)
        span = max(self._dist_m(a[0], a[1], None, b) for a in reps for b in reps)
        kels = {m[1] for m in inside if m[1]}
        kecs = {m[2] for m in inside if m[2]}
        if len(kels) == 1 and span <= COHERENT_M:
            return {'kel': kels.pop(), 'kec': kecs.pop() if len(kecs) == 1 else None, 'why': why}
        if len(kecs) == 1:
            return {'kel': None, 'kec': kecs.pop(), 'why': why}
        return None
