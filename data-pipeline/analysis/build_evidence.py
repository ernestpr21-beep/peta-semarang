"""Kumpulkan bukti analisis untuk halaman Metodologi → public/data/evidence.json.
Urutan: clean_listings.py → build_campus.py → build_app_data.py → analysis/campus_eval.py → analysis/frontage_eval.py
→ analysis/compare_versions.py <listings_model lama> <dataset lama> → analysis/build_evidence.py"""
import csv, json, os
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = lambda p: json.load(open(os.path.join(ROOT, 'data', p)))
clean = list(csv.DictReader(open(os.path.join(ROOT, 'data/listings_clean.csv'))))
notes = Counter()
for r in clean:
    n = r['loc_note']
    if n.startswith('titik bersama'): notes['titikBersama'] += 1
    elif n.startswith('teks menyebut'): notes['teksBertentangan'] += 1
    if 'hanya nama kecamatan' in n: notes['teksHanyaKecamatan'] += 1
ev = {
    'locationQuality': {'levels': dict(Counter(r['loc_level'] for r in clean)), 'sharedPin': notes['titikBersama'], 'textConflict': notes['teksBertentangan'],
                        'kecTextOnly': notes['teksHanyaKecamatan'], 'kecOnlyByKecamatan': dict(Counter(r['kecamatan'] for r in clean if r['loc_level'] == 'kecamatan').most_common())},
    'campus': D('campus_eval.json'),
    'frontage': D('frontage_eval.json'),
    'beforeAfter': D('validation_before_after.json'),
    'points': {'before': D('points_before.json'), 'after': D('points_after.json')},
}
json.dump(ev, open(os.path.join(ROOT, 'public/data/evidence.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
print('evidence.json', os.path.getsize(os.path.join(ROOT, 'public/data/evidence.json')), 'bytes', ev['locationQuality'])
