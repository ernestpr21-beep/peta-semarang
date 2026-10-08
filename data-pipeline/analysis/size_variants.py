"""Pilih spesifikasi kurva luas lewat leave-one-out: (a) elastisitas log-linear lama, (b) kelas luas tanpa moderasi,
(c) kelas luas × tingkat harga wilayah (penuh), (d) idem tetapi hanya di bawah median (z ≤ 0, dipakai).
Menjalankan build_app_data.py per varian lalu compare_versions.py terhadap model terpasang sebelumnya; terakhir varian
bawaan dijalankan ulang agar keluaran aplikasi sesuai. Pemakaian: python3 size_variants.py <listings_model_lama.csv> <dataset_lama.json>
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PIPE = os.path.dirname(HERE); ROOT = os.path.dirname(PIPE)
OLD_CSV, OLD_DS = sys.argv[1], sys.argv[2]
VARIANTS = {'kelas_tanpa_moderasi': {'SIZE_INTERACT': '0'}, 'kelas_moderasi_penuh': {'SIZE_ZHI': 'p95'}, 'kelas_moderasi_bawah_median': {}}
out = {}
for name, env in VARIANTS.items():
    e = dict(os.environ, **env)
    subprocess.run([sys.executable, 'build_app_data.py'], cwd=PIPE, env=e, check=True, stdout=subprocess.DEVNULL)
    m = json.load(open(os.path.join(ROOT, 'public/data/dataset.json')))['model']
    tmp = f'/tmp/sv_{name}.json'
    subprocess.run([sys.executable, 'compare_versions.py', OLD_CSV, OLD_DS], cwd=HERE, env=dict(e, OLD_EST='new', OUT=tmp), check=True, stdout=subprocess.DEVNULL)
    c = json.load(open(tmp))
    out[name] = {'env': env, 'rss': m['sizeCurve']['rss'], 'looTitik': m['validation']['medianAbsErrPct_model'], 'looAllLocated': m['validation']['allLocated']['medianAbsErrPct_model'],
                 'groups': {k: {'n': v['n'], 'old': v['old']['mdae'], 'new': v['new']['mdae']} for k, v in c.items() if k != 'perKecamatan'},
                 'perKecamatan': {k: {'n': v['n'], 'old': v['old']['mdae'], 'new': v['new']['mdae']} for k, v in c['perKecamatan'].items()}}
    print(name, out[name]['looTitik'], out[name]['looAllLocated'], out[name]['rss'])
json.dump(out, open(os.path.join(ROOT, 'data/size_variants.json'), 'w'), indent=1, ensure_ascii=False)
# varian bawaan terakhir (keluaran aplikasi)
subprocess.run([sys.executable, 'build_app_data.py'], cwd=PIPE, check=True, stdout=subprocess.DEVNULL)
