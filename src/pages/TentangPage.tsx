import { useDataset } from "@/lib/data";
import { formatMonth } from "@/lib/utils";
import { PageShell } from "./PageShell";

export function TentangPage() {
  const ds = useDataset();
  const meta = ds.data?.meta;
  return (
    <PageShell title="Tentang" lead="Peta Semarang — peta interaktif Kota Semarang untuk melihat lokasi, fasilitas, dan estimasi kisaran harga pasar tanah kosong.">
      <h2>Apa ini, dan apa yang bukan</h2>
      <ul>
        <li>
          Angka harga adalah <b>estimasi kisaran harga pasar</b> yang dihitung dari harga <i>penawaran</i> iklan tanah di sekitar titik. Bukan NJOP (nilai pajak PBB), bukan Zona Nilai Tanah (ZNT) BPN, bukan hasil
          appraisal KJPP, dan bukan harga transaksi.
        </li>
        <li>Tidak ada data sertifikat, NIB, pemilik, atau batas bidang. Aplikasi tidak bisa memastikan status hukum, sengketa, atau zonasi tata ruang.</li>
        <li>Gunakan sebagai gambaran awal; cek lapangan, tanya warga/perangkat kelurahan, dan cek ZNT di BHUMI ATR/BPN sebelum bertransaksi.</li>
      </ul>

      <h2>Sumber data &amp; lisensi</h2>
      <table>
        <thead>
          <tr>
            <th>Data</th>
            <th>Sumber</th>
            <th>Lisensi / catatan</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Peta jalan, batas kecamatan &amp; kelurahan, jalan untuk deteksi akses, fasilitas</td>
            <td>
              <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">
                OpenStreetMap
              </a>{" "}
              via Overpass API (ekstrak {meta?.osmExtract ?? "2026"})
            </td>
            <td>ODbL 1.0 — © kontributor OpenStreetMap</td>
          </tr>
          <tr>
            <td>Ubin peta jalan (terang)</td>
            <td>tile.openstreetmap.org</td>
            <td>© kontributor OSM; mengikuti kebijakan penggunaan ubin OSMF</td>
          </tr>
          <tr>
            <td>Label lapisan hibrid</td>
            <td>Esri World Transportation &amp; Boundaries and Places</td>
            <td>© Esri — sesuai ketentuan Esri. Mode gelap peta jalan memakai ubin OSM yang dibalik warnanya di peramban.</td>
          </tr>
          <tr>
            <td>Citra satelit</td>
            <td>Esri World Imagery</td>
            <td>© Esri, Maxar, Earthstar Geographics — sesuai ketentuan Esri</td>
          </tr>
          <tr>
            <td>Pencarian alamat</td>
            <td>Photon (Komoot), cadangan Nominatim</td>
            <td>Data OSM (ODbL); kebijakan penggunaan Nominatim berlaku</td>
          </tr>
          <tr>
            <td>Harga iklan tanah</td>
            <td>{meta ? meta.sources.map((s) => `${s.name} (${s.cleanCount} iklan, diambil ${s.scrapedAt.slice(0, 10)})`).join("; ") : "Pinhome, Lamudi"}</td>
            <td>Fakta harga/luas/lokasi dari halaman publik, diringkas untuk analisis; tiap titik menautkan ke iklan aslinya. Tidak menyimpan data pribadi agen/penjual maupun foto.</td>
          </tr>
        </tbody>
      </table>
      {meta ? (
        <>
          <h2>Sumber yang tidak bisa dipakai</h2>
          <ul>
            {meta.blocked.map((b) => (
              <li key={b.name}>
                <b>{b.name}</b>: {b.reason}
              </li>
            ))}
          </ul>
          <p className="text-fg-muted">
            Dataset dibuat {meta.generatedAt.slice(0, 10)}; iklan {formatMonth(meta.dateMin)}–{formatMonth(meta.dateMax)}.
          </p>
        </>
      ) : null}
      <h2>Teknis</h2>
      <p>
        Aplikasi web statis (Vite + React + Leaflet), tanpa server khusus atau kunci API berbayar. Data harga, jalan, dan fasilitas sudah diproses sebelumnya menjadi berkas JSON, sehingga peta tidak bergantung pada
        Overpass saat diklik. Seluruh skrip pengumpulan &amp; pembersihan data ada di repositori (<code>data-pipeline/</code>), beserta data iklan yang sudah dibersihkan (<code>data/</code>, nomor kontak dihapus) dan data mentah OSM (<code>data-raw/osm</code>).
      </p>
    </PageShell>
  );
}
