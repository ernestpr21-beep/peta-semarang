import { useEffect } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { useDataset } from "@/lib/data";
import { TIER_ORDER } from "@/lib/model";
import { ACCESS_THRESHOLDS } from "@/lib/access";
import { formatMonth, formatRupiahShort } from "@/lib/utils";
import { Skeleton } from "@/components/ui/primitives";
import { PageShell } from "./PageShell";

const pct = (f: number) => `${f >= 1 ? "+" : "−"}${Math.abs(Math.round((f - 1) * 100))}%`;

export function MetodologiPage() {
  const ds = useDataset();
  const hash = useRouterState({ select: (s) => s.location.hash });
  useEffect(() => {
    if (hash && ds.data) document.getElementById(hash)?.scrollIntoView({ behavior: "smooth" });
  }, [hash, ds.data]);
  if (!ds.data)
    return (
      <PageShell title="Metodologi">
        <Skeleton className="h-64 w-full" />
      </PageShell>
    );
  const { meta, model } = ds.data;
  const r = model.regression;
  const v = model.validation;
  const ct = r.coefText;
  return (
    <PageShell
      title="Metodologi"
      lead={
        <>
          Bagaimana <b>estimasi kisaran harga pasar</b> tanah kosong dihitung. Angka ini dari harga penawaran iklan, bukan NJOP, bukan Zona Nilai Tanah (ZNT) BPN, dan bukan penilaian (appraisal) resmi.
        </>
      }
    >
      <h2>1. Data pembanding</h2>
      <p>
        {meta.counts.raw.toLocaleString("id-ID")} iklan tanah dijual dikumpulkan dari {meta.sources.map((s) => s.name).join(" dan ")} (diambil {meta.sources.map((s) => s.scrapedAt.slice(0, 10)).join(" / ")}). Setelah
        dibersihkan tersisa <b>{meta.counts.clean.toLocaleString("id-ID")} iklan</b> di {meta.kelurahanCovered} dari {meta.kelurahanTotal} kelurahan, tanggal iklan {formatMonth(meta.dateMin)}–{formatMonth(meta.dateMax)}. Rincian per
        kelurahan ada di <Link to="/data-zona">Data zona</Link>.
      </p>
      <p>Pembersihan (skrip <code>data-pipeline/clean_listings.py</code>, data mentah ikut disimpan di repositori):</p>
      <ul>
        <li>Hanya iklan jual tanah; iklan yang jelas berisi bangunan (rumah, gudang, ruko) dibuang kecuali disebut "hitung tanah".</li>
        <li>Harga/m² = harga ÷ luas tanah; iklan yang mencantumkan harga per m² dikenali dan tidak dibagi dua kali. Luas &lt; 30 m² atau &gt; 20 ha, dan harga/m² di luar Rp75 rb–Rp75 jt dibuang.</li>
        <li>Lokasi: koordinat iklan dicocokkan dengan poligon kelurahan OSM (admin_level 7). Bila koordinat jauh (&gt; 1,5 km) dari kelurahan yang ditulis di iklan, titik dipindah ke kelurahan tertulis dan ditandai "perkiraan". Iklan di luar Kota Semarang dibuang.</li>
        <li>Duplikat (kelurahan + luas + harga sama, termasuk lintas portal) dihapus.</li>
        <li>Pencilan: |z| &gt; 3 berdasarkan median &amp; MAD log-harga per kelurahan (atau kecamatan bila data kelurahan &lt; 6).</li>
      </ul>
      <p>
        Ringkasan buang: {Object.entries(meta.flags)
          .filter(([k]) => k !== "BERSIH")
          .map(([k, n]) => `${k} ${n}`)
          .join(" · ")}
        .
      </p>

      <h2>2. Normalisasi ke "bidang acuan"</h2>
      <p>
        Setiap iklan dinormalisasi ke bidang acuan: <b>{model.refArea} m², akses jalan lingkungan (mobil bisa masuk), per {formatMonth(model.asOf)}</b>. Faktornya diperoleh dari regresi log-harga dengan efek tetap kelurahan (OLS, n={r.n}):
      </p>
      <table>
        <thead>
          <tr>
            <th>Variabel</th>
            <th>Koefisien ± SE</th>
            <th>Arti</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>log(luas/{model.refArea})</td>
            <td className="num">
              {model.sizeElasticity.toFixed(3)} ± {model.sizeElasticitySE.toFixed(3)}
            </td>
            <td>luas 2× → harga/m² {pct(Math.pow(2, model.sizeElasticity))}</td>
          </tr>
          {ct["tier:utama"] ? (
            <tr>
              <td>akses jalan utama (disebut di iklan)</td>
              <td className="num">
                {ct["tier:utama"][0].toFixed(3)} ± {ct["tier:utama"][1].toFixed(3)}
              </td>
              <td>{pct(Math.exp(ct["tier:utama"][0]))} vs jalan lingkungan</td>
            </tr>
          ) : null}
          {ct["tier:gang"] ? (
            <tr>
              <td>gang / akses motor (disebut di iklan)</td>
              <td className="num">
                {ct["tier:gang"][0].toFixed(3)} ± {ct["tier:gang"][1].toFixed(3)}
              </td>
              <td>{pct(Math.exp(ct["tier:gang"][0]))} — hanya {r.countsText.gang ?? 0} iklan, sangat tidak pasti</td>
            </tr>
          ) : null}
          {ct["tier:unknown"] ? (
            <tr>
              <td>akses tidak disebut</td>
              <td className="num">
                {ct["tier:unknown"][0].toFixed(3)} ± {ct["tier:unknown"][1].toFixed(3)}
              </td>
              <td>{pct(model.unknownTierFactor)} vs yang menyebut jalan lingkungan</td>
            </tr>
          ) : null}
          <tr>
            <td>sumber Lamudi vs Pinhome</td>
            <td className="num">{ct["src_lamudi"] ? `${ct["src_lamudi"][0].toFixed(3)} ± ${ct["src_lamudi"][1].toFixed(3)}` : "—"}</td>
            <td>harga penawaran Lamudi {pct(model.sourceEffect)} di kelurahan yang sama; selisih dinetralkan ke rata-rata gabungan</td>
          </tr>
          <tr>
            <td>tren waktu</td>
            <td className="num">
              {model.trendRaw.toFixed(3)} ± {model.trendSE.toFixed(3)} /th
            </td>
            <td>dipakai {(model.trendPerYear * 100).toFixed(1)}%/tahun (dibatasi 0–12%)</td>
          </tr>
        </tbody>
      </table>
      <p className="text-fg-muted">
        R² dalam-kelurahan {r.r2Within.toFixed(2)}, σ residu {r.sigma.toFixed(2)} (log). Artinya: sebagian besar variasi harga <i>di dalam</i> satu kelurahan tidak terjelaskan oleh luas/akses yang tertulis —
        karena itu rentang estimasi sengaja lebar.
      </p>

      <h2>3. Estimasi di titik yang diklik</h2>
      <ol>
        <li>Cari iklan pembanding terdekat; radius diperbesar bertahap (400 m → 3 km) sampai setara ≥ 8 pembanding (iklan berlokasi perkiraan dihitung setengah). Maksimal 30 pembanding.</li>
        <li>Bobot tiap pembanding: kernel jarak (makin dekat makin berat), ketepatan lokasi, dan umur iklan (waktu paruh {model.recencyHalfLifeYears} tahun).</li>
        <li>Median terboboti dari harga ternormalisasi → harga lokal. Lalu "disusutkan" ke median kelurahan (atau kecamatan/kota bila data kelurahan &lt; 3) dengan bobot setara 3 pembanding — makin sedikit data lokal, makin besar peran median wilayah.</li>
        <li>
          <b>Rentang</b> = 50% tengah distribusi (±0,674σ), dengan σ dari sebaran (MAD) pembanding terdekat — dicampur sebaran kota bila pembanding sedikit — ditambah ketidakpastian faktor akses. Jadi lebar rentang
          mengikuti kepadatan &amp; keragaman data, bukan ±20% tetap.
        </li>
        <li>Harga untuk kondisi akses &amp; luas yang dipilih = harga dasar × faktor akses × faktor luas. Angka dibulatkan 2 angka penting.</li>
        <li>Tingkat keyakinan: tinggi (≥ 8 pembanding efektif, median jarak ≤ 1 km, sebaran wajar), sedang (≥ 4 dalam 2 km), selain itu rendah.</li>
      </ol>

      <h2 id="akses">4. Ada akses jalan vs tanpa akses</h2>
      <p>Empat kelas akses dipakai. Faktor relatif terhadap jalan lingkungan:</p>
      <table>
        <thead>
          <tr>
            <th>Kelas</th>
            <th>Faktor (95% CI)</th>
            <th>Dasar</th>
          </tr>
        </thead>
        <tbody>
          {TIER_ORDER.map((t) => {
            const ti = model.tiers[t];
            return (
              <tr key={t}>
                <td>
                  <b>{ti.label}</b>
                  <br />
                  <span className="text-fg-muted">{ti.desc}</span>
                </td>
                <td className="num">
                  ×{ti.factor.toFixed(2)}
                  {t !== "lingkungan" ? (
                    <>
                      <br />({ti.lo.toFixed(2)}–{ti.hi.toFixed(2)})
                    </>
                  ) : null}
                </td>
                <td>
                  {t === "lingkungan"
                    ? `Acuan (${ti.n} iklan menyebut akses mobil/jalan lingkungan).`
                    : ti.basis === "data"
                      ? `Data: ${ti.n} iklan yang menyebut kondisi ini; koefisien regresi ×${ti.dataFactor?.toFixed(2)}, digabung dengan rujukan ×${ti.prior.toFixed(2)} (bobot presisi).`
                      : ti.basis === "campuran"
                        ? `Campuran: hanya ${ti.n} iklan menyebut kondisi ini (koefisien ×${ti.dataFactor?.toFixed(2) ?? "—"}, tidak pasti), digabung dengan rujukan ×${ti.prior.toFixed(2)}.`
                        : `Rujukan: ${ti.n} iklan saja yang menyebut kondisi ini, jadi faktor memakai rujukan ×${ti.prior.toFixed(2)} dengan rentang lebar.`}{" "}
                  {t !== "lingkungan" ? ti.priorNote : ""}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <h3>Mengapa faktor "tanpa akses" belum bisa murni dari data</h3>
      <p>
        Hampir tidak ada iklan yang mengaku tanahnya tanpa akses — penjual menonjolkan kelebihan, bukan kekurangan. Dari {meta.counts.clean.toLocaleString("id-ID")} iklan bersih, {r.countsText.tanpa ?? 0} menyebut
        tanpa akses dan {r.countsText.gang ?? 0} menyebut gang/akses motor. Selisih <b>jalan utama vs jalan lingkungan</b> ({pct(model.tiers.utama.factor)}) cukup kuat datanya; selisih gang dan terkurung memakai rujukan:
      </p>
      <ul>
        <li>
          KUH Perdata Pasal 667: pemilik tanah terkurung berhak menuntut jalan keluar melalui tanah tetangga <i>dengan ganti rugi</i>. Jadi nilai tanah terkurung ≈ nilai tanah berakses dikurangi biaya &amp; ketidakpastian
          memperoleh akses itu.
        </li>
        <li>Praktik penilaian internasional melaporkan diskon tanah terkurung umumnya sekitar 50% (mis. putusan Tax Court New Jersey) hingga 50–75% bila akses sulit diperoleh.</li>
        <li>Juknis Penilaian Tanah BPN (2023) dan pedoman DJKN memperlakukan aksesibilitas &amp; lebar jalan sebagai faktor penyesuaian yang ditetapkan dari pasar lokal — tidak ada angka baku nasional.</li>
      </ul>
      <p>
        Maka "tanpa akses" diberi faktor ×{model.tiers.tanpa.factor.toFixed(2)} ({pct(model.tiers.tanpa.factor)}) dengan rentang lebar ({model.tiers.tanpa.lo.toFixed(2)}–{model.tiers.tanpa.hi.toFixed(2)}) yang ikut melebarkan
        kisaran harga.
      </p>
      <h3>Deteksi akses dari OSM di titik klik</h3>
      <p>Titik klik dianggap berada di dalam bidang. Jarak ke as jalan OSM terdekat menentukan kelas:</p>
      <ul>
        <li>≤ {ACCESS_THRESHOLDS.frontage} m dari jalan primer/sekunder/tersier/trunk → <b>jalan utama</b></li>
        <li>≤ {ACCESS_THRESHOLDS.frontage} m dari jalan residential/unclassified/service umum → <b>jalan lingkungan</b> (gang bila lebar tercatat &lt; 3 m)</li>
        <li>≤ {ACCESS_THRESHOLDS.narrow} m dari gang/jalan setapak/footway/track, atau {ACCESS_THRESHOLDS.frontage}–{ACCESS_THRESHOLDS.inner} m dari jalan mobil (bidang dalam) → <b>gang sempit</b></li>
        <li>tidak ada jalan/gang dalam {ACCESS_THRESHOLDS.inner} m → <b>tanpa akses</b></li>
      </ul>
      <p>
        Jalan tol tidak dihitung sebagai akses. OSM bisa belum memetakan gang kecil — terutama di pinggiran — sehingga "tanpa akses" bisa keliru; pengguna bisa mengubah kelas secara manual di panel. Diagnostik: pada{" "}
        {r.nOsm} iklan berkoordinat tepat, kelas OSM di titik iklan tidak berkorelasi jelas dengan harga (pin iklan sering diletakkan di jalan/pusat perumahan, bukan di bidang), sehingga koefisien OSM tidak
        dipakai untuk faktor.
      </p>

      <h2>5. Validasi (leave-one-out)</h2>
      <p>
        Setiap iklan bersih ditebak dari iklan lain (dirinya dikeluarkan), lalu dibandingkan dengan harganya sendiri (n={v.n}):
      </p>
      <table>
        <thead>
          <tr>
            <th>Metode</th>
            <th>Median galat absolut</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Model ini (pembanding terdekat + normalisasi + penyusutan)</td>
            <td className="num">{v.medianAbsErrPct_model}%</td>
          </tr>
          <tr>
            <td>Median kelurahan (ternormalisasi)</td>
            <td className="num">{v.medianAbsErrPct_kelurahanMedian}%</td>
          </tr>
          <tr>
            <td>Median kecamatan mentah (pendekatan versi lama)</td>
            <td className="num">{v.medianAbsErrPct_kecamatanMedian_raw}%</td>
          </tr>
        </tbody>
      </table>
      <p>
        {v.within25pct_model}% iklan tertebak dalam ±25%. Rentang 50% yang ditampilkan memuat {v.coverage50pct}% iklan uji (target 50%) — sebaran minimum log 0,25 dipilih dari kalibrasi ini. Galat ini juga mencerminkan keragaman harga penawaran itu sendiri (iklan sejenis di lokasi sama bisa berbeda 2×).
      </p>

      <h2>6. Skor lokasi 0–100</h2>
      <p>
        Lima aspek @20: pendidikan, kesehatan, transportasi, komersial (70% jarak fasilitas terdekat + 30% jumlah dalam 1 km) dan jarak ke Simpang Lima. Hanya fasilitas yang benar-benar ditemukan di ekstrak OSM
        yang dihitung; aspek tanpa fasilitas dalam 3 km bernilai 0. Skor &amp; harga baru tampil setelah semua data selesai dimuat — tidak ada angka sementara.
      </p>

      <h2>7. Keterbatasan</h2>
      <ul>
        <li>Harga penawaran ≠ harga transaksi. Contoh di Juknis Penilaian Tanah BPN 2023 menunjukkan selisih penawaran–transaksi 17–24%; angka di sini tidak dikoreksi untuk itu.</li>
        <li>Data menumpuk di Tembalang, Gunungpati, Banyumanik; kecamatan pusat &amp; utara (Semarang Utara, Tugu, Genuk, Gayamsari) jauh lebih sedikit iklannya.</li>
        <li>Ciri bidang (bentuk, hook, banjir/rob, kontur, zonasi RDTR, status sertifikat) tidak dimodelkan.</li>
        <li>Tidak memakai data NIB/sertifikat. Nilai ZNT BPN tidak diambil otomatis — cek manual di BHUMI.</li>
      </ul>
      <p className="text-fg-muted">
        Median kota (bidang acuan): {formatRupiahShort(model.cityMedianPn)}/m². Model versi {model.version}.
      </p>
    </PageShell>
  );
}
