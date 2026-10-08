# Peta Semarang (v2)

Peta interaktif Kota Semarang: alamat, kecamatan/kelurahan, fasilitas OSM, skor lokasi 0–100, dan **estimasi kisaran harga pasar** tanah kosong. Harga dibedakan menurut **akses jalan**: pinggir jalan utama, jalan lingkungan, gang sempit, tanpa akses (terkurung).

> Semua angka harga = *estimasi kisaran harga pasar* dari harga **penawaran** iklan. Bukan NJOP, bukan Zona Nilai Tanah (ZNT) BPN, bukan appraisal. Tidak memakai data NIB/sertifikat.

## Menjalankan

```bash
npm install
npm run dev          # pengembangan, http://localhost:5173
npm run typecheck
npm test             # vitest: logika estimasi, akses, skor
npm run build        # hasil ke dist/
npm start            # server statis + fallback SPA, PORT=4173 bawaan
npm run build:pages  # build untuk GitHub Pages (base /peta-semarang/)
```

Aplikasi berupa SPA murni (Vite + React 19 + TanStack Router + react-leaflet). Tidak ada SSR, jadi Leaflet tidak pernah dijalankan di server; peta dimuat lewat `import()` dinamis. Tidak butuh kunci API apa pun.

## Data & pipeline

```
data-raw/                 data mentah
  pinhome/, lamudi/       hasil scraping iklan - TIDAK ikut di repo publik (teks asli memuat nomor kontak agen);
                          jalankan skrip di data-pipeline/scrape untuk mengambil ulang
  osm/                    roads_*.json.gz, facilities_raw.json.gz, kota/kecamatan/kelurahan.geojson, query Overpass
data-pipeline/
  scrape/                 skrip pengambil data (Pinhome, Lamudi via Chrome headful, Overpass, batas admin)
  clean_listings.py       gabung + bersihkan iklan  → data/listings_all.csv, data/listings_clean.csv
                          (tingkat lokasi: titik / kelurahan / kecamatan; titik bersama & teks bertentangan ditangani)
  location_text.py        cek nama tempat di teks iklan vs pin (kavling "dekat Unnes" berpin di pusat kota, dst.)
  build_campus.py         poligon kampus OSM → data/campus.json (faktor kedekatan kampus)
  access_text.py          klasifikasi akses dari teks iklan (dengan penanganan negasi)
  build_osm_layers.py     ubin jalan 0,01° (public/data/roads), fasilitas (public/data/facilities.json)
  osm_access.py           port Python deteksi akses (sama dengan src/lib/access.ts)
  build_app_data.py       regresi, faktor akses, normalisasi, statistik wilayah, validasi LOO
                          → public/data/dataset.json, data/model_report.json, data/listings_model.csv
  analysis/               campus_eval.py, frontage_eval.py, compare_versions.py (LOO lama vs baru),
                          loo_variants.py (eksplorasi), build_evidence.py → public/data/evidence.json (Metodologi §5)
```

Membangun ulang data:

```bash
pip install shapely numpy          # (pyproj/scipy tidak wajib)
python3 data-pipeline/build_osm_layers.py
python3 data-pipeline/clean_listings.py
python3 data-pipeline/build_campus.py
python3 data-pipeline/build_app_data.py
# bukti untuk Metodologi (versi pembanding = commit sebelumnya):
python3 data-pipeline/analysis/campus_eval.py && python3 data-pipeline/analysis/frontage_eval.py
git show ee6a01e:data/listings_model.csv > /tmp/old.csv && git show ee6a01e:public/data/dataset.json > /tmp/old.json
python3 data-pipeline/analysis/compare_versions.py /tmp/old.csv /tmp/old.json
POINTS_LABEL=after npx vitest run tests/points-report.test.ts
python3 data-pipeline/analysis/build_evidence.py
```

Versi bersih ada di `data/` (`listings_all.csv` = semua iklan + alasan dibuang, `listings_clean.csv`, `listings_model.csv`); nomor telepon/WA/email di teks iklan sudah dihapus, dan URL iklan yang slug-nya memuat nomor telepon dikosongkan. Setiap titik data menyimpan sumber (portal + URL iklan), tanggal (diperbarui > dibuat > tanggal ambil, lihat kolom `date_source`), dan penanda lokasi tepat/perkiraan.

## Metode singkat

1. **Normalisasi**: tiap iklan → harga/m² bidang acuan 150 m², akses jalan lingkungan, per bulan data terakhir; selisih tingkat harga antarportal dinetralkan (regresi log-harga dengan efek tetap kelurahan).
2. **Estimasi titik**: pembanding terdekat (radius adaptif 400 m–3 km sampai ≥ 10 pembanding efektif, maks. 30; iklan yang lokasinya hanya setingkat kecamatan tidak dipakai), bobot jarak × ketepatan lokasi × umur iklan, median terboboti, disusutkan ke median kelurahan/kecamatan; dikali faktor kedekatan kampus (pita 0–500/500–1000/1000–2000 m, dalam-kelurahan) dan, untuk jalan utama, premi pusat kota exp(b·e^(−d/1500 m)) dari Simpang Lima.
3. **Rentang**: 50% tengah (±0,674σ) dengan σ dari sebaran pembanding lokal (MAD dengan akar bobot, minimum 0,25 log, dikalibrasi leave-one-out), ditambah ketidakpastian faktor akses.
4. **Akses**: dideteksi dari jarak titik ke jalan OSM (≤ 30 m jalan utama/lingkungan, ≤ 25 m gang/setapak, 30–60 m = bidang dalam → gang, > 60 m = tanpa akses). Pengguna bisa mengganti kelas secara manual. Faktor jalan utama berasal dari data; gang & tanpa akses memakai gabungan data minim + rujukan (lihat halaman Metodologi).
5. **Skor**: hanya fasilitas yang benar-benar ditemukan di OSM yang dihitung; tanpa fasilitas → 0.

## Lisensi data

- OpenStreetMap (jalan, batas, fasilitas, ubin peta): © kontributor OSM, ODbL 1.0.
- Citra & label hibrid: © Esri, Maxar, Earthstar Geographics.
- Pencarian: Photon (Komoot) & Nominatim (data OSM).
- Iklan: Pinhome & Lamudi. Yang disimpan hanya fakta harga/luas/lokasi/tanggal/deskripsi dari halaman publik, plus tautan ke iklan asli. Tidak ada data pribadi agen atau foto.

## Deploy

GitHub Actions (`.github/workflows/pages.yml`) membangun dengan `BASE_PATH=/<nama-repo>/` dan menerbitkan `dist/` ke GitHub Pages pada setiap push ke `main`. `scripts/postbuild.mjs` menyalin `index.html` ke tiap rute (`/metodologi/`, `/tentang/`, `/data-zona/`) dan `404.html` agar tautan langsung berfungsi.
