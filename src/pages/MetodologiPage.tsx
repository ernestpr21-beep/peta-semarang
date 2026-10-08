import { useEffect } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { useDataset, useEvidence, type Evidence, type VStat } from "@/lib/data";
import { TIER_ORDER } from "@/lib/model";
import { ACCESS_THRESHOLDS } from "@/lib/access";
import { formatMonth, formatRupiahShort } from "@/lib/utils";
import { Skeleton } from "@/components/ui/primitives";
import { PageShell } from "./PageShell";

const jt = (v: number) => (v / 1e6).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const rng = (x: { low: number; high: number }) => `${jt(x.low)}–${jt(x.high)}`;

function EvidenceSection({ ev, model }: { ev: Evidence; model: import("@/lib/model").PriceModel }) {
  const lq = ev.locationQuality;
  const tt = ev.campus.tembalangText;
  const cbd = model.cbdFrontage;
  const regKel = ev.campus.regression.kelurahan ?? [];
  const regKec = ev.campus.regression.kecamatan ?? [];
  const ba = Object.entries(ev.beforeAfter).filter(([k]) => k !== "perKecamatan") as [string, { n: number; old: VStat; new: VStat }][];
  const fr = ev.frontage;
  return (
    <>
      <h2 id="lokasi">5. Ketepatan lokasi iklan, kampus &amp; pusat kota (pembaruan Okt 2026)</h2>
      <p>
        Pengguna melaporkan estimasi di sekitar Undip Tembalang terlalu rendah dan di pusat kota (Simpang Lima/Pandanaran) tidak konsisten. Hasil penelusuran data:
      </p>
      <h3>5a. Banyak "koordinat tepat" ternyata titik bawaan portal</h3>
      <ul>
        <li>
          <b>Titik bersama:</b> {lq.sharedPin.toLocaleString("id-ID")} iklan memakai koordinat yang persis sama dengan ≥ 4 iklan lain (mis. 212 iklan Pinhome di satu titik di Mangunharjo dengan kelurahan tertulis
          Bulusan, Sambiroto, Sendangmulyo, …). Itu titik pusat wilayah bawaan portal, bukan lokasi bidang. Sekarang iklan seperti ini dipindah ke kelurahan yang tertulis (lokasi "perkiraan", bobot ½) — atau,
          bila kelurahannya tidak tertulis, hanya dipakai di tingkat kecamatan.
        </li>
        <li>
          <b>Teks lokasi hanya nama kecamatan:</b> iklan yang lokasinya cuma "Tembalang", "Ngaliyan", "Mijen", … tanpa pin tepat dulu diletakkan di pusat kelurahan bernama sama — untuk Tembalang itu tepat di
          sebelah kampus Undip. Iklan ini (n={tt.kecOnlyN}, median Rp{jt(tt.kecOnlyMedian)} jt/m², luas median {tt.kecOnlyArea} m²) harganya mirip rata-rata seluruh Kec. Tembalang (iklan berpin, Rp
          {jt(tt.kecExactMedian)} jt, n={tt.kecExactN}), bukan kelurahan Tembalang di sekitar kampus (Rp{jt(tt.kelExactMedian)} jt, n={tt.kelExactN}). Inilah penyebab utama estimasi rendah di Jl. Prof.
          Soedarto/Baskoro: 16–23 dari 30 pembanding di sana adalah iklan "se-kecamatan" ini.
        </li>
        <li>
          <b>Teks bertentangan dengan pin:</b> {lq.textConflict} iklan berpin menyebut tempat yang semuanya jauh (&gt; 3 km) dari pinnya — mis. kavling "dekat Unnes", "daerah Meteseh", "Pakintelan Gunungpati"
          yang pinnya di Pleburan/Randusari/Wonodri (pusat kota). Lokasinya dipindah ke kawasan yang disebut (skrip <code>data-pipeline/location_text.py</code>).
        </li>
        <li>
          Hasil: {lq.levels.titik?.toLocaleString("id-ID")} iklan berpin tepat, {lq.levels.kelurahan?.toLocaleString("id-ID")} setingkat kelurahan, {lq.levels.kecamatan?.toLocaleString("id-ID")} hanya
          setingkat kecamatan. Iklan setingkat kecamatan <b>tidak dipakai</b> sebagai pembanding titik maupun median kelurahan, tetapi tetap masuk median kecamatan. Tidak tampil di peta.
        </li>
      </ul>

      <h3>5b. Premi kampus: nyata di Undip, tidak seragam antar kampus</h3>
      <table>
        <thead>
          <tr>
            <th>Kampus (poligon OSM)</th>
            <th>≤ 1 km</th>
            <th>1–3 km</th>
          </tr>
        </thead>
        <tbody>
          {ev.campus.perCampus.slice(0, 10).map((c) => (
            <tr key={c.campus}>
              <td>{c.campus}</td>
              <td className="num">
                Rp{jt(c.near)} jt <span className="text-fg-subtle">(n={c.nNear})</span>
              </td>
              <td className="num">
                Rp{jt(c.far)} jt <span className="text-fg-subtle">(n={c.nFar})</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-fg-muted">Median harga penawaran asli per m², iklan berpin tepat.</p>
      <table>
        <thead>
          <tr>
            <th>Sebutan di judul/deskripsi</th>
            <th>Iklan yang menyebut</th>
            <th>Sisa iklan di kecamatan yang sama</th>
          </tr>
        </thead>
        <tbody>
          {ev.campus.text.map((t) => (
            <tr key={t.group}>
              <td>{t.group}</td>
              <td className="num">
                Rp{jt(t.median)} jt <span className="text-fg-subtle">(n={t.n})</span>
              </td>
              <td className="num">
                Rp{jt(t.restMedian)} jt <span className="text-fg-subtle">({t.restKec.join(", ")}, n={t.restN})</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        Regresi log-harga (iklan berpin) dengan pita jarak ke kampus terdekat (≥ 2 ha, tanpa Akpol), acuan &gt; 2 km. Dengan efek tetap <i>kecamatan</i>:{" "}
        {regKec.map((b) => `${b.from}–${b.to} m ×${Math.exp(b.coef).toFixed(2)}`).join(", ")} — sebagian besar karena kampus berada di kelurahan yang memang mahal. Dengan efek tetap <i>kelurahan</i> (selisih di
        dalam kelurahan yang sama): {regKel.map((b) => `${b.from}–${b.to} m ×${Math.exp(b.coef).toFixed(2)} ± ${b.se.toFixed(2)}`).join(", ")}. Efek dalam-kelurahan ini kecil tetapi konsisten, sehingga dipakai
        sebagai <b>faktor kedekatan kampus</b> (diestimasi bersama regresi utama, disusutkan ke 0):{" "}
        {model.campus?.bands.map((b) => `${b.minM}–${b.maxM} m ×${Math.exp(b.coef).toFixed(2)}`).join(", ")}. Premi besar khas Undip (Rp6–7 jt vs Rp3–4 jt) sudah tertangkap oleh pembanding terdekat setelah
        lokasi iklan dibenahi; di Unnes, Unika, Udinus polanya tidak ada atau terbalik, jadi tidak ada "bonus kampus" besar yang dipukul rata.
      </p>

      <h3>5c. Muka jalan utama di pusat kota</h3>
      <p>
        Faktor jalan utama satu angka untuk seluruh kota ({pct(model.tiers.utama.factor)}) terlalu kecil di pusat kota. Regresi dengan interaksi jarak ke Simpang Lima (efek tetap kelurahan):
        {fr.cbd?.["utama×(≤2km Simpang Lima)"]
          ? ` iklan jalan utama ≤ 2 km dari Simpang Lima ×${Math.exp(fr.cbd["utama×(≤2km Simpang Lima)"][0]).toFixed(2)} (± ${fr.cbd["utama×(≤2km Simpang Lima)"][1].toFixed(2)} log) di atas premi jalan utama biasa;`
          : ""}
        {fr.level?.["utama×(lvl kel−kota)"] ? ` interaksi dengan tingkat harga kelurahan saja tidak signifikan (${fr.level["utama×(lvl kel−kota)"][0].toFixed(2)} ± ${fr.level["utama×(lvl kel−kota)"][1].toFixed(2)}).` : ""}{" "}
        {cbd ? (
          <>
            Dipakai bentuk halus: premi tambahan = exp({cbd.coef.toFixed(2)} · e<sup>−d/{cbd.scaleM} m</sup>), skala {cbd.scaleM} m dipilih dari {Object.keys(cbd.rssByScale).join("/")} m lewat galat regresi,
            koefisien {cbd.coefRaw.toFixed(2)} ± {cbd.coefSE.toFixed(2)} disusutkan ke {cbd.coef.toFixed(2)}. Artinya muka jalan utama di Simpang Lima ×{Math.exp(cbd.coef).toFixed(2)}, 1 km ×
            {Math.exp(cbd.coef * Math.exp(-1000 / cbd.scaleM)).toFixed(2)}, 3 km ×{Math.exp(cbd.coef * Math.exp(-3000 / cbd.scaleM)).toFixed(2)} di atas faktor jalan utama biasa (n={cbd.nUtamaWithin3L} iklan jalan
            utama dalam {(3 * cbd.scaleM) / 1000} km).
          </>
        ) : null}{" "}
        Data di pusat kota tetap tipis (Kec. Semarang Tengah/Selatan masing-masing &lt; 100 iklan) dan sangat beragam — kavling kampung Rp3–10 jt/m² bersebelahan dengan lahan komersial Rp50–65 jt/m² — sehingga
        rentang di sana lebar. Sumber lain (Rumah123, 99.co, OLX) masih memblokir pengambilan data; Brighton/Trovit bisa diakses tetapi tanpa koordinat.
      </p>

      <h3>5d. Sebelum vs sesudah (leave-one-out, target sama)</h3>
      <p>
        Pembanding diuji pada {ba[0]?.[1].n.toLocaleString("id-ID")} iklan yang berpin tepat menurut aturan baru dan ada di kedua versi data. Galat = median |log harga asli − log prediksi| (dalam %); cakupan =
        bagian iklan yang jatuh di rentang 50% (target 50%).
      </p>
      <table>
        <thead>
          <tr>
            <th>Kelompok</th>
            <th>n</th>
            <th>Galat lama</th>
            <th>Galat baru</th>
            <th>Cakupan lama → baru</th>
          </tr>
        </thead>
        <tbody>
          {ba.map(([k, x]) => (
            <tr key={k}>
              <td>{k}</td>
              <td className="num">{x.n}</td>
              <td className="num">{x.old.mdae}%</td>
              <td className="num">{x.new.mdae}%</td>
              <td className="num">
                {x.old.cov50}% → {x.new.cov50}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-fg-muted">
        Yang memburuk: Kec. Gajahmungkur &amp; Candisari (ring 2–4 km dari Simpang Lima). Di sana dulu ada ±95 iklan "titik bersama" yang kebetulan duduk di titik target uji; setelah dibenahi, pembanding
        lokal lebih sedikit dan harganya sangat beragam. Skrip: <code>data-pipeline/analysis/compare_versions.py</code>.
      </p>
      <table>
        <thead>
          <tr>
            <th>Titik</th>
            <th>Jalan lingkungan (lama → baru, Rp jt/m²)</th>
            <th>Jalan utama (lama → baru)</th>
          </tr>
        </thead>
        <tbody>
          {ev.points.after.map((p, i) => {
            const b = ev.points.before[i];
            return (
              <tr key={p.name}>
                <td>{p.name}</td>
                <td className="num">
                  {rng(b.lingkungan)} → <b>{rng(p.lingkungan)}</b>
                </td>
                <td className="num">
                  {rng(b.utama)} → <b>{rng(p.utama)}</b>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}

const pct = (f: number) => `${f >= 1 ? "+" : "−"}${Math.abs(Math.round((f - 1) * 100))}%`;

export function MetodologiPage() {
  const ds = useDataset();
  const ev = useEvidence();
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
        <li>Lokasi: koordinat iklan dicocokkan dengan poligon kelurahan OSM (admin_level 7). Bila koordinat jauh (&gt; 1,5 km) dari kelurahan yang ditulis di iklan, titik dipindah ke kelurahan tertulis dan ditandai "perkiraan". Koordinat yang dipakai bersama ≥ 5 iklan (titik bawaan portal), teks lokasi yang hanya nama kecamatan, dan pin yang bertentangan dengan tempat yang disebut di iklan ditangani khusus — lihat <a href="#lokasi">bagian 5</a>. Iklan di luar Kota Semarang dibuang.</li>
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
        <li>Cari iklan pembanding terdekat; radius diperbesar bertahap (400 m → 3 km) sampai setara ≥ {model.minEffComparables ?? 8} pembanding (iklan berlokasi perkiraan setingkat kelurahan dihitung setengah; iklan yang lokasinya hanya diketahui sampai kecamatan tidak dipakai). Maksimal 30 pembanding.</li>
        <li>Bobot tiap pembanding: kernel jarak (makin dekat makin berat), ketepatan lokasi, dan umur iklan (waktu paruh {model.recencyHalfLifeYears} tahun).</li>
        <li>Median terboboti dari harga ternormalisasi → harga lokal. Lalu "disusutkan" ke median kelurahan (atau kecamatan/kota bila data kelurahan &lt; 3) dengan bobot setara 3 pembanding — makin sedikit data lokal, makin besar peran median wilayah.</li>
        <li>
          <b>Rentang</b> = 50% tengah distribusi (±0,674σ), dengan σ dari sebaran (MAD, bobot diratakan dengan akar bobot agar 1–2 iklan terdekat tidak mendominasi) pembanding terdekat — dicampur sebaran kota bila pembanding sedikit — ditambah ketidakpastian faktor akses. Jadi lebar rentang
          mengikuti kepadatan &amp; keragaman data, bukan ±20% tetap.
        </li>
        <li>Harga untuk kondisi akses &amp; luas yang dipilih = harga dasar × faktor kedekatan kampus × faktor akses (jalan utama: × premi pusat kota) × faktor luas. Angka dibulatkan 2 angka penting.</li>
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

      {ev.data ? <EvidenceSection ev={ev.data} model={model} /> : null}

      <h2>6. Validasi (leave-one-out)</h2>
      <p>
        Setiap iklan berpin tepat ditebak dari iklan lain (dirinya dikeluarkan), lalu dibandingkan dengan harganya sendiri (n={v.n}
        {v.allLocated ? `; termasuk iklan setingkat kelurahan n=${v.allLocated.n}: galat model ${v.allLocated.medianAbsErrPct_model}%` : ""}):
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

      <h2>7. Skor lokasi 0–100</h2>
      <p>
        Lima aspek @20: pendidikan, kesehatan, transportasi, komersial (70% jarak fasilitas terdekat + 30% jumlah dalam 1 km) dan jarak ke Simpang Lima. Hanya fasilitas yang benar-benar ditemukan di ekstrak OSM
        yang dihitung; aspek tanpa fasilitas dalam 3 km bernilai 0. Skor &amp; harga baru tampil setelah semua data selesai dimuat — tidak ada angka sementara.
      </p>

      <h2>8. Keterbatasan</h2>
      <ul>
        <li>Harga penawaran ≠ harga transaksi. Contoh di Juknis Penilaian Tanah BPN 2023 menunjukkan selisih penawaran–transaksi 17–24%; angka di sini tidak dikoreksi untuk itu.</li>
        <li>Data menumpuk di Tembalang, Gunungpati, Banyumanik; kecamatan pusat &amp; utara (Semarang Tengah/Selatan/Utara, Tugu, Genuk, Gayamsari) jauh lebih sedikit iklannya — rentang di pusat kota lebar.</li>
        <li>Lokasi iklan bergantung pada pin/teks dari pengiklan; perbaikan di bagian 5 menangkap pola yang jelas (titik bersama, nama kecamatan, teks bertentangan), tidak semua salah letak.</li>
        <li>Ciri bidang (bentuk, hook, banjir/rob, kontur, zonasi RDTR, status sertifikat) tidak dimodelkan.</li>
        <li>Tidak memakai data NIB/sertifikat. Nilai ZNT BPN tidak diambil otomatis — cek manual di BHUMI.</li>
      </ul>
      <p className="text-fg-muted">
        Median kota (bidang acuan): {formatRupiahShort(model.cityMedianPn)}/m². Model versi {model.version}.
      </p>
    </PageShell>
  );
}
