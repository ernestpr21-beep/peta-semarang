import { useEffect } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { useDataset, useEvidence, type Evidence, type VStat } from "@/lib/data";
import { TIER_ORDER, type PriceModel } from "@/lib/model";
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

const VARIANT_LABEL: Record<string, string> = {
  kelas_tanpa_moderasi: "kelas luas, sama untuk semua wilayah",
  kelas_moderasi_penuh: "kelas luas × tingkat harga wilayah (penuh)",
  kelas_moderasi_bawah_median: "kelas luas × tingkat harga, hanya di bawah median (dipakai)",
};
const TIERS4 = ["utama", "lingkungan", "gang", "tanpa"] as const;

function SizeGangSection({ ev, model }: { ev: NonNullable<Evidence["v3"]>; model: import("@/lib/model").PriceModel }) {
  const sc = model.sizeCurve;
  const sb = model.spreadBySize;
  const gc = model.tierCaps?.gangCheck;
  const tp = ev.terrain.testPoint;
  const ba = Object.entries(ev.beforeAfter).filter(([k]) => k !== "perKecamatan") as [string, { n: number; old: VStat; new: VStat }][];
  const kec = Object.entries(ev.beforeAfter.perKecamatan ?? {});
  const vs = Object.entries(ev.sizeVariants);
  const zLo = sc?.zMin ?? 0;
  return (
    <>
      <h3 id="luas">5e. Luas bidang, lereng &amp; rentang gang sempit (model {model.version})</h3>
      <p>
        Uji lapangan pengguna: titik {tp.lat}, {tp.lng} (Candisari, Gg. V), bidang 44 m² per sertifikat, gang sempit hanya motor di lereng curam dengan rumah padat. Titik tengah peta (≈ Rp5 jt/m²) dinilai
        wajar, tetapi batas atas rentang terlalu tinggi untuk tanah gang. Yang diperiksa dari data:
      </p>
      <ol>
        <li>
          <b>Luas bidang tidak log-linear.</b> Model lama memakai satu elastisitas ({model.sizeElasticity.toFixed(3)}: bidang kecil sedikit <i>lebih mahal</i> per m²). Dengan kelas luas dalam regresi efek tetap
          kelurahan, bidang &lt; 75 m² justru ≈ 20% lebih murah per m² daripada 125–175 m² di kelurahan yang sama (di kelurahan bertingkat harga median ke atas), dan polanya berbeda menurut tingkat harga wilayah: di kelurahan murah bidang luas adalah lahan
          mentah (diskon besar), di kelurahan mahal bidang luas bernilai pengembangan. Tiga spesifikasi diuji leave-one-out:
        </li>
      </ol>
      <table>
        <thead>
          <tr>
            <th>Kurva luas</th>
            <th>Jumlah kuadrat sisa regresi</th>
            <th>Galat LOO (pin tepat)</th>
            <th>Galat LOO (semua berlokasi)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>elastisitas log-linear (lama)</td>
            <td className="num">{vs[0]?.[1].rss.linear}</td>
            <td className="num" colSpan={2}>
              lihat tabel sebelum/sesudah di bawah
            </td>
          </tr>
          {vs.map(([k, v]) => (
            <tr key={k}>
              <td>{VARIANT_LABEL[k] ?? k}</td>
              <td className="num">{v.rss.bins}</td>
              <td className="num">{v.looTitik}%</td>
              <td className="num">{v.looAllLocated}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        Dipakai: kelas luas dengan moderasi tingkat harga <i>hanya di bawah median</i> (median harga mentah kelurahan Rp{jt(sc?.levelCenter ?? 0)} jt/m²). Di atas median, premi bidang luas kemungkinan tercampur nilai
        komersial/muka jalan yang tidak tercatat di iklan, jadi tidak diekstrapolasi; varian ini juga galat LOO-nya terkecil. Faktor luas (×, relatif 150 m²):
      </p>
      {sc ? (
        <table>
          <thead>
            <tr>
              <th>Luas (median kelas)</th>
              <th>Kelurahan tingkat median ke atas</th>
              <th>Kelurahan termurah (z = {zLo.toFixed(2)})</th>
              <th>n iklan</th>
            </tr>
          </thead>
          <tbody>
            {sc.knots.map((k) => (
              <tr key={k.area}>
                <td className="num">
                  {k.area} m² <span className="text-fg-subtle">({k.minM2}–{k.maxM2 ?? "…"})</span>
                </td>
                <td className="num">×{Math.exp(k.coef).toFixed(2)}</td>
                <td className="num">×{Math.exp(k.coef + (k.slope ?? 0) * zLo).toFixed(2)}</td>
                <td className="num">{k.n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      <ol start={2}>
        <li>
          <b>Lebar rentang menurut luas.</b> Residu leave-one-out terstandar menunjukkan bidang kecil lebih seragam (rentang 50% lama memuat{" "}
          {sb?.calibration.coverageByClassWithout[0]}% iklan &lt; 100 m²) dan bidang sangat luas jauh lebih beragam (hanya {sb?.calibration.coverageByClassWithout[4]}% untuk ≥ 1.500 m²). Pengali σ per kelas luas:{" "}
          {sb?.classes.map((c) => `${c.minM2}–${c.maxM2 ?? "…"} m² ×${c.scale.toFixed(2)}`).join(", ")}; cakupan per kelas menjadi {sb?.calibration.coverageByClassWith.join("/")}%. Uji silang 2 lipat (skala
          dihitung di separuh data, diuji di separuh lain): cakupan {sb?.calibration.crossFitCoverage50.map((c) => `${c.without}% → ${c.withScale}%`).join(" dan ")}.
        </li>
        <li>
          <b>Batas atas gang &amp; tanpa akses.</b> Rentang tier gang tidak lagi sekadar rentang jalan lingkungan × faktor: batas atasnya dibatasi pada <i>titik estimasi jalan lingkungan</i> di lokasi &amp; luas yang
          sama (tanah yang hanya bisa dicapai motor tidak dihargai di atas tanah yang bisa dimasuki mobil di titik yang sama); batas atas tanpa akses dibatasi pada titik estimasi gang. Ini aturan struktural, bukan
          hasil estimasi — datanya terlalu sedikit untuk membuktikan atau membantahnya: dari {gc?.n} iklan yang menyebut gang/akses motor, median harganya{" "}
          {gc?.medianLogVsLingPoint != null ? `×${Math.exp(gc.medianLogVsLingPoint).toFixed(2)}` : "—"} dan kuartil atasnya{" "}
          {gc?.q75LogVsLingPoint != null ? `×${Math.exp(gc.q75LogVsLingPoint).toFixed(2)}` : "—"} dari titik jalan lingkungan di lokasinya ({gc?.shareAboveLingPoint}% di atasnya). Cakupan rentang 50% pada iklan gang
          itu {gc?.withoutCap?.coverage50}% tanpa batas → {gc?.withCap?.coverage50}% dengan batas (n kecil; label teks iklan juga tidak selalu tepat).
        </li>
        <li>
          <b>Lereng: diuji, tidak dipakai.</b> {ev.terrain.dem}. Titik uji pengguna lerengnya ≈ {tp.slopeDeg}° (lebih curam dari 97% iklan berpin; median {ev.terrain.slopeQuantiles["0.5"]}°). Dalam kelurahan yang
          sama, selisih harga menurut kelas lereng (acuan {ev.terrain.refBand}):{" "}
          {ev.terrain.withinKelurahan.map((b) => `${b.band} ${b.coef >= 0 ? "+" : "−"}${Math.abs(b.coef).toFixed(2)} ± ${b.se.toFixed(2)} (n=${b.n})`).join(", ")} — tidak bermakna. Hanya kelas ≥ 15° (n=
          {ev.terrain.looResidualByBand[4]?.n}) yang residunya sedikit negatif (median {ev.terrain.looResidualByBand[4]?.median}), belum cukup untuk faktor. Skrip: <code>data-pipeline/analysis/terrain_eval.py</code>.
        </li>
      </ol>
      <p>Validasi model {model.version} vs model sebelumnya (estimator sama, leave-one-out, target sama):</p>
      <table>
        <thead>
          <tr>
            <th>Kelompok</th>
            <th>n</th>
            <th>Galat sebelum</th>
            <th>Galat sesudah</th>
            <th>Cakupan sebelum → sesudah</th>
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
        Per kecamatan: {kec.map(([k, x]) => `${k} ${x.old.mdae}→${x.new.mdae}%`).join(" · ")}. Yang memburuk: kecamatan pinggiran (Gunungpati, Mijen, Genuk), Tembalang (sedikit), serta Semarang Selatan &amp;
        Timur (n kecil). Kurva luas adalah rata-rata kota per tingkat harga; di wilayah-wilayah ini pola luas–harga tampaknya berbeda. Catatan: estimasi bidang 150 m² di wilayah mahal turun karena bidang luas di
        sana (yang per m² lebih mahal) kini dinormalisasi ke bawah sebelum dipakai sebagai pembanding.
      </p>
      <table>
        <thead>
          <tr>
            <th>Titik (luas)</th>
            {TIERS4.map((t) => (
              <th key={t}>{model.tiers[t].short} (sebelum → sesudah)</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ev.points.after.map((p, i) => {
            const b = ev.points.before[i];
            return (
              <tr key={p.name}>
                <td>
                  {p.name} <span className="text-fg-subtle">({p.area ?? 150} m²)</span>
                </td>
                {TIERS4.map((t) => (
                  <td key={t} className="num">
                    {b?.[t] && p[t] ? (
                      <>
                        {rng(b[t]!)} → <b>{rng(p[t]!)}</b>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                ))}
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
      <p>Pembersihan (skrip <code>data-pipeline/clean_listings.py</code>; data mentah iklan tidak dipublikasikan karena memuat kontak agen — nomor telepon, tautan WhatsApp &amp; email dihapus dari data yang dipakai):</p>
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
          {model.sizeCurve ? (
            <tr>
              <td>kelas luas (acuan {model.sizeCurve.refBin[0]}–{model.sizeCurve.refBin[1]} m²)</td>
              <td className="num">{model.sizeCurve.knots.map((k) => `${k.area} m² ${k.coefRaw >= 0 ? "+" : "−"}${Math.abs(k.coefRaw).toFixed(2)}`).join(" · ")}</td>
              <td>
                kurva luas, berbeda menurut tingkat harga wilayah — lihat <a href="#luas">bagian 5e</a> (dulu satu elastisitas {model.sizeElasticity.toFixed(3)} ± {model.sizeElasticitySE.toFixed(3)})
              </td>
            </tr>
          ) : (
            <tr>
              <td>log(luas/{model.refArea})</td>
              <td className="num">
                {model.sizeElasticity.toFixed(3)} ± {model.sizeElasticitySE.toFixed(3)}
              </td>
              <td>luas 2× → harga/m² {pct(Math.pow(2, model.sizeElasticity))}</td>
            </tr>
          )}
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
        {model.kelurahanPricing ? (
          <li>
            <b>Hanya iklan dari kelurahan yang sama</b> dengan titik yang diklik (point-in-polygon pada batas kelurahan) yang dipakai — tidak ada pembanding yang dipinjam dari kelurahan tetangga.
            Lihat <a href="#per-kelurahan">bagian 3a</a>.
          </li>
        ) : null}
        <li>Cari iklan pembanding terdekat{model.kelurahanPricing ? " di dalam kelurahan itu" : ""}; radius diperbesar bertahap (400 m → 3 km) sampai setara ≥ {model.minEffComparables ?? 8} pembanding (iklan berlokasi perkiraan setingkat kelurahan dihitung setengah; iklan yang lokasinya hanya diketahui sampai kecamatan tidak dipakai). Maksimal 30 pembanding.</li>
        <li>Bobot tiap pembanding: kernel jarak (makin dekat makin berat), ketepatan lokasi, dan umur iklan (waktu paruh {model.recencyHalfLifeYears} tahun).</li>
        <li>
          Median terboboti dari harga ternormalisasi → harga lokal. Lalu "disusutkan" ke median wilayah dengan bobot setara 3 pembanding — makin sedikit data lokal, makin besar peran median wilayah.
          {model.kelurahanPricing ? (
            <>
              {" "}
              Sejak model 2026-10-7, median wilayah = <b>median kelurahan bertingkat</b>: median harga ternormalisasi iklan di kelurahan itu, disusutkan ke median kecamatan setara{" "}
              {model.kelurahanPricing.mKel} iklan; median kecamatan disusutkan ke median kota setara {model.kelurahanPricing.mKec} iklan. Bila kelurahan punya &lt; {model.kelurahanPricing.minKel} iklan,
              median lokal disusutkan lebih kuat (setara {model.kelurahanPricing.weakLocalStrength ?? 3} iklan).
            </>
          ) : model.smoothPrior ? (
            <>
              {" "}
              Sejak model {model.version}, median wilayah adalah <b>median berbobot jarak</b> (Gauss, lebar {model.smoothPrior.bwM.toLocaleString("id-ID")} m) dari pembanding dalam{" "}
              {model.smoothPrior.maxM / 1000} km, bukan median kelurahan — sehingga estimasi tidak melompat di garis batas kelurahan. Akurasi setara (validasi silang blok spasial 2 km: galat 37,4% vs 37,3%;
              leave-one-out 33,8% vs 33,9%), lompatan antar sel kisi 250 m berkurang.
            </>
          ) : (
            " Median wilayah = median kelurahan (atau kecamatan/kota bila data kelurahan < 3)."
          )}
        </li>
        <li>
          <b>Rentang</b> = 50% tengah distribusi (±0,674σ), dengan σ dari sebaran (MAD, bobot diratakan dengan akar bobot agar 1–2 iklan terdekat tidak mendominasi) pembanding terdekat — dicampur sebaran kota bila pembanding sedikit — ditambah ketidakpastian faktor akses, lalu dikali pengali menurut luas bidang (bidang kecil lebih seragam, bidang sangat luas lebih beragam). Untuk gang sempit, batas atas tidak melebihi titik
          estimasi jalan lingkungan; untuk tanpa akses, tidak melebihi titik estimasi gang (<a href="#luas">bagian 5e</a>). Jadi lebar rentang mengikuti kepadatan &amp; keragaman data, bukan ±20% tetap.
        </li>
        <li>
          Harga untuk kondisi akses &amp; luas yang dipilih = harga dasar × faktor kedekatan kampus × faktor akses (jalan utama: × premi pusat kota) × faktor luas. Angka dibulatkan 2 angka penting.
          {model.autoAccess ? (
            <>
              {" "}
              Selama kondisi akses <b>belum dipilih</b> pengguna (hanya hasil deteksi OSM), faktor akses yang dipakai adalah faktor terkalibrasi untuk deteksi itu — lihat <a href="#akses-otomatis">bagian 4b</a>.
            </>
          ) : null}
        </li>
        <li>Tingkat keyakinan: tinggi (≥ 8 pembanding efektif, median jarak ≤ 1 km, sebaran wajar), sedang (≥ 4 dalam 2 km), selain itu rendah.</li>
      </ol>

      {model.frontage ? <FrontageSection /> : null}
      {model.znt ? <ZntSection /> : null}
      {model.featurePricing ? <FeatureSection /> : null}
      {model.kelurahanPricing ? <KelurahanSection /> : null}

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

      {model.autoAccess ? <AutoAccessSection model={model} /> : null}
      {model.corridor ? <CorridorSection model={model} /> : null}

      {ev.data ? <EvidenceSection ev={ev.data} model={model} /> : null}
      {ev.data?.v3 ? <SizeGangSection ev={ev.data.v3} model={model} /> : null}

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
        {v.within25pct_model}% iklan tertebak dalam ±25%. Rentang 50% yang ditampilkan memuat {v.coverage50pct}% iklan uji (target 50%) — sebaran minimum log 0,25 dan pengali per kelas luas dipilih dari kalibrasi ini. Galat ini juga mencerminkan keragaman harga penawaran itu sendiri (iklan sejenis di lokasi sama bisa berbeda 2×).
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
        <li>Ciri bidang (bentuk, hook, banjir/rob, zonasi RDTR, status sertifikat) tidak dimodelkan. Kemiringan lereng sudah diuji dengan DEM Copernicus 30 m tetapi tidak berpengaruh bermakna di dalam kelurahan, jadi tidak dipakai (bagian 5e).</li>
        <li>Tidak memakai data NIB/sertifikat. Nilai ZNT BPN tidak diambil otomatis — cek manual di BHUMI.</li>
      </ul>
      <p className="text-fg-muted">
        Median kota (bidang acuan): {formatRupiahShort(model.cityMedianPn)}/m². Model versi {model.version}.
      </p>
    </PageShell>
  );
}

function AutoAccessSection({ model }: { model: PriceModel }) {
  const aa = model.autoAccess!;
  const b = aa.validation.before, a = aa.validation.after;
  const pctLog = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(Math.round((Math.exp(x) - 1) * 100))}%`;
  return (
    <>
      <h3 id="akses-otomatis">4b. Akses hasil deteksi otomatis: faktor terkalibrasi (audit Okt 2026, model {model.version})</h3>
      <p>
        Audit menyeluruh (Okt 2026) menemukan penyebab terbesar estimasi "terlalu rendah": di titik yang diklik, kelas akses diambil dari deteksi OSM lalu dikalikan faktor penuhnya (gang ×{model.tiers.gang.factor.toFixed(2)}, tanpa akses ×
        {model.tiers.tanpa.factor.toFixed(2)}). Padahal iklan berpin tepat yang titiknya dideteksi "gang" atau "tanpa akses" <b>tidak lebih murah</b> daripada tetangganya: banyak gang kampung belum dipetakan di OSM, dan
        titik di tengah blok belum tentu terkurung. Pada kisi 250 m, ±45% sel permukiman terdeteksi gang/tanpa akses; di sana harga tampil ±20–45% terlalu rendah (terutama Gunungpati, Mijen, Ngaliyan, Tugu, Tembalang timur), dan harga melompat-lompat
        antar titik bertetangga (2.201 pasang sel tetangga berselisih &gt; ×1,5, kini 231).
      </p>
      <p>
        Sekarang, selama kondisi akses belum dipilih pengguna, harga utama memakai <b>faktor akses terkalibrasi</b>: median log(harga iklan / estimasi tanpa faktor akses) per kelas deteksi (leave-one-out), disusutkan ke faktor
        "akses tidak disebut" (bobot n/(n+30)) dan dibuat monoton (utama ≥ lingkungan ≥ gang ≥ tanpa):{" "}
        {TIER_ORDER.map((t) => `${model.tiers[t].short} ×${aa.factors[t].toFixed(2)} (n=${aa.n[t]})`).join(", ")}
        {aa.cbdScale > 0 ? "; jalan utama di pusat kota tetap mendapat premi pusat kota" : ""}. Rentang ditambah σ {aa.sdLog.toFixed(2)} (kondisi akses sebenarnya belum diketahui). Bila pengguna memilih kelas akses,
        faktor penuh di tabel atas yang dipakai (mis. gang sempit yang memang hanya bisa dilalui motor).
      </p>
      <table>
        <thead>
          <tr>
            <th>Harga yang tampil di titik iklan (leave-one-out, n={a.n})</th>
            <th>Sebelum</th>
            <th>Sesudah</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>Galat median</td><td className="num">{b.medianAbsErrPct}%</td><td className="num">{a.medianAbsErrPct}%</td></tr>
          <tr><td>Bias median (estimasi vs iklan)</td><td className="num">{pctLog(b.biasLog)}</td><td className="num">{pctLog(a.biasLog)}</td></tr>
          <tr><td>Dalam ±25%</td><td className="num">{b.within25pct}%</td><td className="num">{a.within25pct}%</td></tr>
          <tr><td>Cakupan rentang 50%</td><td className="num">{b.coverage50pct}%</td><td className="num">{a.coverage50pct}%</td></tr>
          {TIER_ORDER.map((t) => (
            <tr key={t}>
              <td>Bias bila terdeteksi "{model.tiers[t].short}"</td>
              <td className="num">{b.biasByDetectedTier[t] != null ? pctLog(b.biasByDetectedTier[t]!) : "—"}</td>
              <td className="num">{a.biasByDetectedTier[t] != null ? pctLog(a.biasByDetectedTier[t]!) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-fg-muted">
        Validasi silang blok spasial (blok 2 km keluar bersama, faktor dikalibrasi hanya dari lipatan latih): galat harga tampil 45,6% → 38,8%, bias −16% → 0%. Aturan lain yang diuji dan <b>tidak</b> memperbaiki
        validasi: koreksi kata kunci iklan (BU/cicilan/sawah/hook), buang pencilan lebih ketat, dedup lintas portal, tren waktu lebih curam, ukuran radius/kernel/jumlah pembanding, dan gradient boosting
        (LightGBM: galat 35,8–36,8% tetapi bias kuat ke rata-rata — wilayah murah terlalu tinggi, mahal terlalu rendah). Skrip: <code>data-pipeline/analysis/audit/</code>.
      </p>
    </>
  );
}

function CorridorSection({ model }: { model: PriceModel }) {
  const c = model.corridor!;
  const f = c.validation.frontage;
  const d = c.validation.display;
  const pctLog = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(Math.round((Math.exp(x) - 1) * 100))}%`;
  const roads = Object.values(c.roads).sort((a, b) => b.n - a.n);
  const rows: [string, string, string][] = [
    ["Iklan muka jalan arteri, harga tampil (deteksi OSM)", "autoBefore", "autoAfter"],
    ["… hanya yang teksnya menyebut muka jalan itu", "autoTextBefore", "autoTextAfter"],
    ["… tanpa iklan yang ditandai pencilan", "autoNonOutlierBefore", "autoNonOutlierAfter"],
    ["Iklan muka jalan arteri, tier utama dipilih manual", "manualBefore", "manualAfter"],
  ];
  return (
    <>
      <h3 id="koridor-arteri">4c. Premi koridor jalan arteri (audit Jl. Majapahit, Okt 2026, model {model.version})</h3>
      <p>
        Laporan: Jl. Majapahit tampil jauh terlalu murah (Rp2,7–6,8 jt/m²). Iklan yang menyebut bidang di muka Jl. Majapahit–Brigjen Sudiarto meminta ±Rp7–30 jt/m², sedangkan pembanding terdekat di
        titik itu adalah bidang dalam perumahan/kampung (Rp2–4 jt/m²). Premi jalan utama yang seragam (×{model.tiers.utama.factor.toFixed(2)}, deteksi otomatis ×{model.autoAccess?.factors.utama.toFixed(2)}) tidak
        cukup di koridor komersial seperti ini, dan iklan muka jalan termahal justru terbuang oleh aturan pencilan per kelurahan (aturan itu membandingkan dengan bidang dalam di kelurahan yang sama). Di tingkat kota
        rata-rata premi muka jalan arteri sudah kira-kira pas (±×1,1); kekurangannya terpusat pada koridor tertentu (Majapahit–Sudiarto, Soekarno-Hatta, Perintis Kemerdekaan).
      </p>
      <p>
        Karena itu tier <b>jalan utama</b> kini mendapat <b>premi koridor</b> bila jalan utama terdekat (≤ {c.maxRoadM} m) adalah ruas arteri (OSM trunk/primary) bernama yang punya iklan muka jalan: premi = median
        residu log iklan muka jalan pada ruas bernama sama (terhadap estimasi tier utama, leave-one-out; termasuk iklan yang ditandai pencilan), berbobot Gauss(jarak/{(c.bwM / 1000).toLocaleString("id-ID")} km), lalu
        disusutkan ke 0 dengan bobot nEff/(nEff + {c.k}) (k dikalibrasi ulang 2026-10-6 dari 4 ke 2: dengan k = 4 estimasi di ruas masih ±40% di bawah iklan muka jalan). Iklan dikaitkan ke ruas bila teksnya menyebut bidang di muka/pinggir jalan itu (pin ≤ 1,5 km dari ruas), atau pinnya ≤ 30 m dari ruas itu{" "}
        <b>dan</b> teksnya menyebut akses jalan utama atau nama ruas itu (sejak 2026-10-6; sebelumnya kavling murah tanpa keterangan yang kebetulan berpin di persimpangan ikut terhitung). Bila ada beberapa ruas
        koridor dalam {c.maxRoadM} m (persimpangan), preminya digabung berbobot jumlah bukti efektif (nEff), sehingga ruas dengan sedikit bukti tidak menimpa ruas arteri utama. Ruas
        "Brigjen Sudiarto" di OSM digabung dengan Jl. Majapahit (satu jalan arteri menerus; iklan di ruas timur menyebutnya Jl. Majapahit). Ruas: {roads.slice(0, 8).map((r) => `${r.label} (${r.n})`).join(", ")}
        {roads.length > 8 ? `, dan ${roads.length - 8} ruas lain dengan 1–2 iklan` : ""}. Premi bisa juga &lt; 1 bila iklan di ruas itu lebih murah dari estimasi. Ruas kolektor (secondary) tidak diberi premi koridor: di
        sana iklan muka jalan rata-rata justru sedikit di bawah estimasi.
      </p>
      <table>
        <thead>
          <tr>
            <th>Leave-one-out (iklan itu sendiri & salinannya dikeluarkan dari bukti koridor)</th>
            <th>Sebelum</th>
            <th>Sesudah</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([lab, kb, ka]) =>
            f[kb] && f[ka] ? (
              <tr key={kb}>
                <td>
                  {lab} (n={f[kb].n})
                </td>
                <td className="num">
                  {f[kb].medianAbsErrPct}% · bias {pctLog(f[kb].biasLog)}
                </td>
                <td className="num">
                  {f[ka].medianAbsErrPct}% · bias {pctLog(f[ka].biasLog)}
                </td>
              </tr>
            ) : null,
          )}
          <tr>
            <td>Semua iklan berpin tepat, harga tampil (n={d.after.n}; {d.nWithPremium} mendapat premi koridor)</td>
            <td className="num">
              {d.before.medianAbsErrPct}% · ±25%: {d.before.within25pct}% · cakupan {d.before.coverage50pct}%
            </td>
            <td className="num">
              {d.after.medianAbsErrPct}% · ±25%: {d.after.within25pct}% · cakupan {d.after.coverage50pct}%
            </td>
          </tr>
        </tbody>
      </table>
      <p className="text-fg-muted">
        Uji bersama 2026-10-6 (versi lama vs baru pada himpunan iklan yang sama; salinan iklan uji dikeluarkan dari pembanding; harga dihitung di titik ruas jalan terdekat seperti saat pengguna
        mengklik jalan): 31 iklan yang teksnya menyebut muka jalan arteri — galat harga tampil leave-one-out 75,9% → 66,5% (bias −40% → −30%), validasi silang blok spasial 2 km 98% → 78%; seluruh 1.871 iklan
        berpin tepat — leave-one-out 34,5% → 34,1%, validasi silang 35,3% → 34,3% (dalam ±25%: 39,4% → 38,4% leave-one-out, 39,0% → 39,2% validasi silang). Estimasi di koridor <b>masih di bawah</b> harga iklan
        muka jalan (±30%): premi disusutkan karena tiap ruas hanya punya sedikit iklan, dan harga penawaran ≠ transaksi. Yang diuji dan tidak dipakai: premi menurut jarak saja (tanpa nama ruas), premi untuk ruas
        kolektor. Skrip: <code>data-pipeline/corridor.py</code>, <code>data-pipeline/analysis/audit/corridor_cv*.py</code>, <code>eval_set_v6.py</code>, <code>tests/validate-cv.test.ts</code>.
      </p>
      <h3 id="pembersihan-2026-10-6">4d. Pembersihan data: salinan lintas wilayah &amp; pencilan menurut kelas akses (model {model.version})</h3>
      <p>
        <b>Salinan lintas kelurahan/portal.</b> Satu bidang sering diiklankan beberapa agen dengan pin berserakan (mis. 7.252 m² @ Rp7 jt/m² di Jl. Majapahit tercatat 10× dari Kalicari sampai Bugangan), sehingga
        deduplikasi lama (kunci kelurahan + luas + harga) gagal dan bidang itu berbobot berlipat. Kini dua iklan dianggap sama bila luasnya sama (±0,5 m² atau ±0,1%) dan harga totalnya sama (±1%), dan teksnya mirip (Jaccard
        bigram ≥ 0,3) atau luasnya khas (≥ 300 m², bukan kelipatan 25 m²) dengan pin ≤ 5 km; yang disimpan pin tepat paling sentral di antara salinannya.
      </p>
      <p>
        <b>Pencilan menurut kelas akses.</b> Aturan pencilan membandingkan harga/m² dengan median kelurahan; bidang muka jalan utama yang wajar ikut terbuang karena dibandingkan dengan bidang dalam. Kini simpangan
        diukur setelah koreksi kelas akses dari teks (koreksi = median simpangan kelas itu di seluruh kota: jalan utama +19%, gang −15%). Iklan muka jalan yang masih ekstrem (mis. Rp19–22 jt/m² di Brigjen Sudiarto)
        tetap tidak dipakai sebagai pembanding bidang dalam, tetapi ikut menjadi bukti premi koridor di atas.
      </p>
      <p className="text-fg-muted">
        Premi pusat kota untuk jalan utama hasil deteksi kini dipilih dengan kriteria bias median terkecil (sebelumnya galat absolut median, yang kurvanya datar pada ±43 iklan sehingga pilihannya melompat-lompat bila
        data sedikit berubah).
      </p>
    </>
  );
}

function KelurahanSection() {
  const rows: [string, string, string, string, string][] = [
    ["Keseluruhan (1.871 iklan berpin tepat)", "34,1%", "35,6%", "34,3%", "37,4%"],
    ["… termasuk iklan bertanda pencilan (1.958)", "36,1%", "37,4%", "36,4%", "40,0%"],
    ["Kelurahan berbukit (1.193)", "34,1%", "35,7%", "34,1%", "37,3%"],
    ["Kelurahan datar/padat (678)", "34,2%", "34,9%", "35,1%", "38,3%"],
    ["Iklan di batas berbukit ↔ datar (349)", "37,9%", "40,1%", "39,5%", "44,2%"],
    ["Kelurahan dengan 15+ iklan (1.530)", "32,7%", "33,0%", "32,7%", "35,2%"],
    ["Kelurahan dengan 5–14 iklan (280)", "41,1%", "44,7%", "41,2%", "46,6%"],
    ["Kelurahan dengan 1–4 iklan (61)", "63,3%", "73,4%", "68,7%", "74,1%"],
    ["Muka jalan arteri, dinilai di ruas jalan (48)", "68,6%", "74,6%", "75,4%", "89,4%"],
  ];
  return (
    <>
      <h3 id="per-kelurahan">3a. Harga per kelurahan (model 2026-10-7)</h3>
      <p>
        Masukan pengguna: banyak estimasi salah karena kelurahan perbukitan/pinggiran tercampur dengan kampung padat di sebelahnya. Model sebelumnya (2026-10-6) memakai pembanding terdekat lintas batas
        kelurahan dan median wilayah berbobot jarak (lebar 1,5 km), sehingga harga bisa “merembes” melewati batas. Sejak 2026-10-7:
      </p>
      <ul>
        <li>Pembanding dan median wilayah hanya dari kelurahan titik itu. Di dalam kelurahan, pembanding tetap diberi bobot jarak.</li>
        <li>
          Bila data kelurahan sedikit, estimasi <b>disusutkan bertingkat</b> ke median kecamatan, lalu kota — bukan meminjam iklan kelurahan tetangga. Panel menampilkan tingkat yang dipakai
          (kelurahan / kelurahan + kecamatan / kecamatan / kota) dan jumlah iklannya.
        </li>
        <li>Lapisan utama peta = choropleth median kelurahan bertingkat itu (bidang acuan 150 m², jalan lingkungan); kelurahan berdata tipis diarsir putus-putus. Tabel lengkap 177 kelurahan ada di halaman Data zona.</li>
        <li>
          Faktor akses, luas, kampus dan pusat kota tetap: semuanya diestimasi dengan efek tetap kelurahan (perbandingan di dalam kelurahan), dan faktor akses hasil deteksi OSM dikalibrasi ulang dengan
          estimator baru (bias per tier ≈ 0). Premi koridor arteri tetap memakai iklan muka jalan di sepanjang ruas yang sama (dibatasi: hanya ≤ 60 m dari ruas bernama, hanya untuk tier jalan utama,
          bobot jarak 1,5 km), karena membatasinya ke satu kelurahan menghapus sebagian besar manfaatnya (galat iklan muka jalan di ruas 75% → 87% leave-one-out).
        </li>
      </ul>
      <p>
        <b>Validasi jujur</b> (target sama, galat absolut median harga tampil; leave-one-out &amp; validasi silang blok spasial 2 km, 5 lipatan):
      </p>
      <div className="overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Himpunan uji</th>
              <th className="text-right">LOO 10-6</th>
              <th className="text-right">LOO 10-7</th>
              <th className="text-right">Blok 10-6</th>
              <th className="text-right">Blok 10-7</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r[0]}>
                <td>{r[0]}</td>
                {r.slice(1).map((v, i) => (
                  <td key={i} className="num text-right">
                    {v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-fg-muted">
        Hasilnya: pembatasan per kelurahan <b>sedikit menurunkan akurasi rata-rata</b> (leave-one-out +1,5 poin, blok spasial +3,1 poin), terutama di kelurahan berdata tipis dan di pusat kota (Semarang
        Selatan/Timur), dan data iklan tidak menunjukkan bahwa kelurahan berbukit sebelumnya dinilai lebih buruk daripada kelurahan datar. Bias median tetap ≈ 0 di semua kelompok harga
        (kuintil termahal: −0,07 → −0,03 log). Struktur ini dipakai karena sesuai cara pengguna membaca peta (satu harga acuan per kelurahan, tanpa rembesan lintas batas) — dengan konsekuensi yang
        disebut di atas. Kelurahan bertanda “kelurahan + kecamatan” atau “kecamatan” sebaiknya dibaca sebagai perkiraan kasar. Medan: DEM Copernicus 30 m, berbukit = lereng rata-rata ≥ 5° dan elevasi
        median ≥ 40 m (61 dari 177 kelurahan).
      </p>
    </>
  );
}

const FEAT_ID: Record<string, string> = {
  built_2500: "Area terbangun radius 2,5 km",
  built_1000: "Area terbangun radius 1 km",
  roaddens_500: "Kepadatan jalan 500 m",
  poi_comm_3000: "Jumlah toko/usaha radius 3 km",
  elev: "Ketinggian (di atas dataran pantai)",
  d_toll: "Jarak ke gerbang tol (makin jauh)",
  d_art: "Jarak ke jalan arteri (makin jauh)",
  d_cbd: "Jarak ke Simpang Lima (makin jauh)",
  bld_250: "Kerapatan bangunan 250 m (setelah area terbangun)",
  d_market: "Jarak ke pasar",
  tree_500: "Tutupan pohon 500 m",
  grass_500: "Rumput/lahan terbuka 500 m",
  health_1500: "Faskes radius 1,5 km",
  slope_250: "Lereng (makin curam)",
  d_river: "Jarak ke sungai",
  d_mall: "Jarak ke mal (makin jauh)",
  kel_poi_comm_1000: "Rata-rata toko/usaha di kelurahan",
  kec_poi_comm_1000: "Rata-rata toko/usaha di kecamatan",
  kec_tree_500: "Rata-rata tutupan pohon di kecamatan",
  kec_roaddens_500: "Rata-rata kepadatan jalan di kecamatan",
  kel_crop_500: "Sawah di kelurahan",
  kel_elev: "Rata-rata ketinggian kelurahan",
  kec_elev: "Rata-rata ketinggian kecamatan",
  kec_built_250: "Rata-rata area terbangun kecamatan",
  kec_slope_250: "Rata-rata lereng kecamatan",
};

function FeatureSection() {
  const ds = useDataset();
  const fp = ds.data?.model.featurePricing;
  if (!fp) return null;
  const T = (rows: (string | number)[][]) => (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={i === 0 ? "font-semibold" : "border-t border-line"}>
              {r.map((c, j) => (
                <td key={j} className={j ? "num py-1 text-right" : "py-1"}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  return (
    <>
      <h3 id="model-fitur">3b. Model fitur wilayah (model 2026-10-8)</h3>
      <p>
        Harga dasar di titik mana pun kini dihitung dari <b>karakteristik wilayahnya</b>, bukan dari iklan terdekat. Model aditif (spline + regresi ridge, dipilih lewat
        validasi silang blok spasial 2 km; gradient boosting juga diuji tetapi lebih buruk) dilatih dari <b>semua iklan kota</b> untuk memprediksi log harga ternormalisasi.
        Tidak ada harga yang diisi manual. Ukuran tanah, akses jalan, kampus dan muka jalan utama tetap dihitung oleh faktor penyesuaian di bagian 2 &amp; 4, jadi tidak masuk
        model fitur (tidak dihitung dua kali).
      </p>
      <p>Sumber fitur (semua data terbuka): ESA WorldCover 10 m (area terbangun, pohon, sawah, rumput, air), Copernicus DEM 30 m (ketinggian, lereng), OpenStreetMap
        (642 ribu bangunan, jalan, toko/pasar/mal, sekolah, faskes, gerbang tol, industri, sungai, garis pantai). Kelompok faktor yang ditampilkan di panel:</p>
      {T([
        ["Fitur (terukur di titik iklan)", "Pengaruh p10 → p90"],
        ...fp.features
          .filter((e) => Math.abs(e.effectPct) >= 5 && FEAT_ID[e.feature])
          .sort((a, b) => Math.abs(b.effectPct) - Math.abs(a.effectPct))
          .map((e) => [FEAT_ID[e.feature], `${e.effectPct >= 0 ? "+" : "−"}${Math.abs(e.effectPct).toFixed(0)}%`]),
      ])}
      <p className="text-xs text-fg-muted">Pengaruh parsial: perubahan harga bila satu fitur bergeser dari persentil 10 ke 90 sementara fitur lain tetap. Fitur saling berkorelasi, jadi baca per kelompok.</p>
      <p>
        Harga akhir = model fitur × koreksi kecamatan (residu iklan disusutkan setara {fp.mKec} iklan) × koreksi kelurahan (setara {fp.mKel} iklan). Kelurahan tanpa iklan
        memakai nilai fiturnya sendiri. Pembanding lokal tidak dipakai lagi untuk harga karena memperburuk validasi; iklan sekitar tetap ditampilkan sebagai acuan. Faktor
        rob/pesisir dan industri hampir tidak berpengaruh karena sangat sedikit iklan di wilayah itu — bukan berarti tidak penting.
      </p>
      <p>Validasi (MdAPE harga tampil, 1.871 iklan bersih; makin kecil makin baik):</p>
      {T([
        ["Uji", "2026-10-6", "2026-10-7", "2026-10-8"],
        ["Leave-one-out", "34,1%", "35,6%", "36,0%"],
        ["Blok spasial 2 km", "34,3%", "37,4%", "37,2%"],
        ["Tanpa kelurahan sendiri (LKO)", "34,6%", "42,9%", "38,8%"],
        ["Kelurahan 1–4 iklan (blok)", "68,7%", "74,1%", "63,4%"],
        ["Berbukit (LKO)", "34,0%", "42,6%", "40,3%"],
        ["Datar/padat (LKO)", "36,1%", "44,9%", "36,6%"],
        ["Bias kuintil termurah / termahal (LKO, log)", "+0,06 / −0,10", "+0,22 / −0,28", "+0,11 / −0,04"],
      ])}
      <p>
        Jujur: model 2026-10-8 lebih baik dari 2026-10-7 di uji blok (tipis, 0,2 poin) dan jelas lebih baik saat kelurahan sendiri disembunyikan (LKO), serta bias
        “tarik ke rata-rata” jauh berkurang. Namun model lama 2026-10-6 (pembanding terdekat lintas kelurahan) masih sedikit lebih akurat secara keseluruhan; harga di muka
        jalan arteri (mis. Majapahit) masih cenderung terlalu rendah di semua model.
      </p>
    </>
  );
}

function FrontageSection() {
  const ds = useDataset();
  const m = ds.data?.model;
  const fm = m?.frontage;
  if (!m || !fm) return null;
  const roads = Object.entries(fm.roads).filter(([, r]) => r.n >= 3).sort((a, b) => b[1].n - a[1].n);
  return (
    <>
      <h3 id="muka-jalan">3c. Premi muka jalan &amp; paparan rob (model 2026-10-9)</h3>
      <p>
        <b>Muka jalan.</b> Untuk tier "pinggir jalan utama" saja, harga dikalikan premi muka jalan: jalan arteri (OSM trunk/primary) ×{Math.exp(fm.cls.arteri ?? 0).toFixed(2)}
        {fm.shopCoef > 0 ? `, sedikit naik bila banyak toko/usaha dalam 250 m (koef. ${fm.shopCoef.toFixed(3)} per log toko)` : ""}, ditambah efek ruas bernama yang
        disusutkan (setara {fm.k} iklan). Jalan kolektor tidak mendapat premi kelas (faktor tier sudah dikalibrasi di sana). Dilatih dari iklan yang jelas bermuka jalan
        (teks/pin koridor arteri, teks “jalan utama/raya”); bidang dalam yang pinnya dekat arteri tidak mendapat premi kecuali tier jalan utama terdeteksi (≤ {fm.maxRoadM} m) atau dipilih.
      </p>
      {roads.length ? (
        <p className="text-xs text-fg-muted">
          Efek ruas (≥ 3 iklan): {roads.map(([, r]) => `${r.label} ${r.u >= 0 ? "+" : "−"}${Math.abs(Math.round((Math.exp(r.u) - 1) * 100))}% (n=${r.n})`).join(" · ")}
        </p>
      ) : null}
      <p>
        <b>Rob/genangan pesisir.</b> Indeks paparan gabungan: elevasi DEM rendah dekat pantai, zona rob yang dikenal (Semarang Utara, Genuk, Tugu, Gayamsari, Semarang Timur
        bagian utara), tambak/rawa/mangrove OSM, dan genangan berulang JRC Global Surface Water 1984–2021. Peta penurunan tanah (InSAR) yang terbit tidak tersedia sebagai
        data terbuka siap pakai, jadi tidak dipakai. Indeks masuk model sebagai suku linear dengan batasan monoton (hanya boleh menurunkan harga).
        {m.featurePricing?.linearMonotone?.length
          ? " Data mendukung efek negatif; koefisiennya disusutkan."
          : " Dengan batasan itu data tidak menunjukkan efek negatif yang dapat diandalkan (koefisien = 0): harga di pesisir dijelaskan oleh fitur lain (dataran rendah, kepadatan, toko). Karena itu panel tidak menampilkan faktor rob."}
      </p>
      <p>
        <b>Audit label.</b> Label kontribusi kini menggambarkan keadaan lokasi dibanding rata-rata lokasi iklan (mis. “dataran rendah”), bukan tanda angkanya. Untuk faktor
        yang arah harganya jelas (kepadatan, pusat kota, jalan besar, toko, lereng, rob), kontribusi yang tandanya bertentangan dengan makna label tidak ditampilkan.
      </p>
    </>
  );
}

function ZntSection() {
  const ds = useDataset();
  const z = ds.data?.model.znt;
  if (!z) return null;
  const kels = [...new Set(z.anchors.map((a) => a.kel))].join(", ");
  const nf = z.anchors.filter((a) => a.kind === "frontage").length;
  return (
    <>
      <h3 id="znt">3d. Batas bawah ZNT BPN (kalibrasi per kelurahan)</h3>
      <p>
        Peta tetap memperkirakan <b>harga pasar</b>. Nilai Tanah Zona (ZNT) BPN dari Bhumi dipakai hanya sebagai <b>batas bawah</b>: di sekitar titik yang sudah dibaca, harga
        tidak boleh di bawah pita bawah ZNT × {z.margin.toFixed(2)} (harga pasar umumnya ≥ ZNT). ZNT hanya tersedia sebagai pita (mis. 2–5 jt, 10–20 jt, &gt; 20 jt per m²) dan
        dibaca satu titik demi satu titik, jadi kalibrasi dilakukan per kelurahan. Saat ini: {z.anchors.length} titik baca di Kel. {kels} ({nf} di muka jalan utama).
      </p>
      <p>
        <b>Titik muka jalan</b> menahan harga tier "pinggir jalan utama" pada ruas yang sama, memakai titik baca <i>terdekat</i> di ruas itu (jadi ruas murah di sebelah
        ruas mahal tidak ikut naik): penuh sampai {z.frontR[0]} m dari titik baca, melemah sampai {z.frontR[1]} m. <b>Titik jalan lingkungan/gang</b> menahan harga dasar
        (semua tier) hanya di sekitar titik itu (penuh {z.areaR[0]} m, hilang di {z.areaR[1]} m; hanya titik terdekat), sehingga bidang dalam di zona murah tidak ikut naik.
        Titik baris kedua di zona jalur jalan (mis. GY-06, 64 m dari Gajah Raya) diberi radius sempit sendiri (25/60 m) agar pita jalur tidak menyebar ke blok dalam. Bila ≥ 3 titik lingkungan jatuh di zona & pita yang sama, batas berlaku di seluruh <b>poligon zona perkiraan</b> (selubung titik-titik itu + 40 m, melemah sampai{" "}
        {z.zoneR ?? 80} m di luarnya; titik baca zona lain yang lebih dekat tetap menang){z.zones?.length ? ` — saat ini ${z.zones.map((q) => `zona ${q.zone} (${q.ids.length} titik)`).join(", ")}` : ""}. Di luar kelurahan
        yang dibaca radius dikali {z.outsideScale ?? 1}. Margin dapat diturunkan per titik bila iklan di zona itu menunjukkan harga pasar dekat pita bawah (mis. perumahan zona
        1136 Jerakah: iklan ~9 jt/m², margin 1,0). ZNT tidak pernah menurunkan harga — titik dengan ZNT jauh di bawah peta (mis. tambak utara Jerakah 0,2–0,5 jt) dicatat
        sebagai kandidat koreksi, bukan diturunkan otomatis. Bila satu titik jatuh di batas dua zona, titik muka jalan memakai zona jalur jalan dan titik lingkungan memakai
        pita yang lebih rendah.
      </p>
      <p className="text-xs text-fg-muted">{z.note}</p>
    </>
  );
}
