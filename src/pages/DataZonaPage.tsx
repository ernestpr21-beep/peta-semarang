import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import { useDataset } from "@/lib/data";
import type { AreaStat, Comparable, KelurahanZoneStat } from "@/lib/model";
import { cn, formatMonth, formatRupiahRange, formatRupiahShort } from "@/lib/utils";
import { Button, Skeleton } from "@/components/ui/primitives";
import { PageShell } from "./PageShell";

function downloadCsv(name: string, rows: (string | number | boolean | null)[][]) {
  const esc = (v: string | number | boolean | null) => {
    const s = v == null ? "" : String(v);
    return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const blob = new Blob(["\ufeff" + rows.map((r) => r.map(esc).join(",")).join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

function StatTable({ rows, showKec }: { rows: AreaStat[]; showKec: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table>
        <thead>
          <tr>
            <th>{showKec ? "Kelurahan" : "Kecamatan"}</th>
            {showKec ? <th>Kecamatan</th> : null}
            <th className="text-right">Iklan</th>
            <th className="text-right">Median*</th>
            <th className="text-right">Kuartil 25–75%*</th>
            <th className="text-right">Median penawaran asli</th>
            <th>Periode</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={`${s.name}-${s.kec}`}>
              <td>{s.name}</td>
              {showKec ? <td className="text-fg-muted">{s.kec}</td> : null}
              <td className={cn("num text-right", s.n < 5 && "text-warn")}>
                {s.n}
                {s.nExact < s.n ? <span className="text-fg-subtle"> ({s.nExact} tepat)</span> : null}
              </td>
              <td className="num text-right">{formatRupiahShort(s.median)}</td>
              <td className="num text-right text-fg-muted">
                {formatRupiahRange(s.p25, s.p75)}
              </td>
              <td className="num text-right text-fg-muted">{formatRupiahShort(s.medianRaw)}</td>
              <td className="whitespace-nowrap text-fg-muted">
                {formatMonth(s.dateMin)}–{formatMonth(s.dateMax)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const LEVEL_LABEL: Record<KelurahanZoneStat["level"], string> = {
  kelurahan: "kelurahan",
  "kelurahan+kecamatan": "kelurahan + kecamatan",
  kecamatan: "kecamatan",
  kota: "kota",
};
type SortKey = "name" | "kec" | "value" | "low" | "high" | "n" | "level" | "terrain" | "featureValue";

function ZoneTable({ rows }: { rows: KelurahanZoneStat[] }) {
  const [sort, setSort] = useState<{ k: SortKey; desc: boolean }>({ k: "value", desc: true });
  const sorted = useMemo(() => {
    const out = [...rows];
    const val = (z: KelurahanZoneStat) => (sort.k === "terrain" ? (z.terrain ?? "") : sort.k === "level" ? ["kelurahan", "kelurahan+kecamatan", "kecamatan", "kota"].indexOf(z.level) : sort.k === "featureValue" ? (z.featureValue ?? 0) : z[sort.k]);
    out.sort((a, b) => {
      const x = val(a), y = val(b);
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "id");
      return sort.desc ? -c : c;
    });
    return out;
  }, [rows, sort]);
  const H = ({ k, children, right }: { k: SortKey; children: React.ReactNode; right?: boolean }) => (
    <th className={cn(right && "text-right")}>
      <button type="button" className="font-semibold hover:text-primary" onClick={() => setSort((s) => ({ k, desc: s.k === k ? !s.desc : k !== "name" && k !== "kec" }))}>
        {children}
        {sort.k === k ? (sort.desc ? " ↓" : " ↑") : ""}
      </button>
    </th>
  );
  return (
    <div className="overflow-x-auto">
      <table>
        <thead>
          <tr>
            <H k="name">Kelurahan</H>
            <H k="kec">Kecamatan</H>
            <H k="value" right>
              Median*
            </H>
            <H k="low" right>
              Rentang**
            </H>
            {rows[0]?.featureValue ? (
              <H k="featureValue" right>
                Dari fitur
              </H>
            ) : null}
            <H k="n" right>
              Iklan
            </H>
            <H k="level">Tingkat data</H>
            <H k="terrain">Medan</H>
          </tr>
        </thead>
        <tbody>
          {sorted.map((z) => (
            <tr key={`${z.name}-${z.kec}`}>
              <td>{z.name}</td>
              <td className="text-fg-muted">{z.kec}</td>
              <td className="num text-right">{formatRupiahShort(z.value)}</td>
              <td className={cn("num text-right text-fg-muted", z.rangeKind === "model" && "italic")}>{formatRupiahRange(z.low, z.high)}</td>
              {z.featureValue ? <td className="num text-right text-fg-muted">{formatRupiahShort(z.featureValue)}</td> : null}
              <td className={cn("num text-right", z.n < 5 && "text-warn")}>
                {z.n}
                {z.nExact < z.n ? <span className="text-fg-subtle"> ({z.nExact} tepat)</span> : null}
              </td>
              <td className={cn("whitespace-nowrap", z.level !== "kelurahan" && "text-warn")}>
                {LEVEL_LABEL[z.level]} · {z.confidence}
              </td>
              <td className="whitespace-nowrap text-fg-muted">{z.terrain ? `${z.terrain} (${z.slopeDeg}°, ${z.elevM} m)` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DataZonaPage() {
  const ds = useDataset();
  const [level, setLevel] = useState<"kecamatan" | "kelurahan">("kelurahan");
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    if (!ds.data) return [];
    const list = level === "kecamatan" ? ds.data.kecamatan : ds.data.kelurahan;
    const s = q.trim().toLowerCase();
    return s ? list.filter((r) => r.name.toLowerCase().includes(s) || r.kec.toLowerCase().includes(s)) : list;
  }, [ds.data, level, q]);
  const zoneRows = useMemo(() => {
    const zs = ds.data?.zones ?? [];
    const s = q.trim().toLowerCase();
    return s ? zs.filter((r) => r.name.toLowerCase().includes(s) || r.kec.toLowerCase().includes(s)) : zs;
  }, [ds.data, q]);
  const useZones = level === "kelurahan" && Boolean(ds.data?.zones?.length);

  if (!ds.data)
    return (
      <PageShell title="Data zona" wide>
        <Skeleton className="h-64 w-full" />
      </PageShell>
    );
  const { meta, comparables } = ds.data;
  const compRows = (cs: Comparable[]) => [
    ["id", "sumber", "url", "lat", "lng", "lokasi_tepat", "tingkat_lokasi", "kelurahan", "kecamatan", "luas_m2", "harga_per_m2", "harga_ternormalisasi_per_m2", "akses_teks", "tanggal"],
    ...cs.map((c) => [c.id, c.src, c.url, c.lat, c.lng, c.exact, c.loc ?? "", c.kel ?? "", c.kec, c.area, c.ppm, c.pn, c.tier, c.date]),
  ];

  return (
    <PageShell
      wide
      title="Data zona"
      lead={
        <>
          Ringkasan harga tanah per wilayah dari {meta.counts.clean.toLocaleString("id-ID")} iklan bersih ({formatMonth(meta.dateMin)}–{formatMonth(meta.dateMax)}). Ini <b>estimasi kisaran harga pasar</b> dari harga penawaran,
          bukan NJOP dan bukan ZNT BPN.
        </>
      }
    >
      <div className="not-prose my-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg border border-border bg-surface p-1">
          {(["kecamatan", "kelurahan"] as const).map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => setLevel(l)}
              className={cn("h-8 rounded-md px-3 text-xs font-medium capitalize", level === l ? "bg-primary text-primary-foreground" : "text-fg-muted hover:text-fg")}
            >
              {l}
            </button>
          ))}
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Cari nama wilayah…"
          className="h-10 w-56 rounded-md border border-border bg-surface px-3 text-sm outline-none focus:border-ring"
        />
        <Button
          variant="outline"
          size="sm"
          onClick={() =>
            useZones
              ? downloadCsv("harga-kelurahan-semarang.csv", [
                  ["kelurahan", "kecamatan", "median_rp_m2", "dari_model_fitur", "koreksi_kecamatan_log", "koreksi_kelurahan_log", "median_kelurahan_mentah", "median_kecamatan_tersusut", "rentang_bawah", "rentang_atas", "jenis_rentang", "n_iklan", "n_lokasi_tepat", "n_iklan_kecamatan", "tingkat_data", "keyakinan", "medan", "elevasi_m", "lereng_derajat"],
                  ...zoneRows.map((z) => [z.name, z.kec, z.value, z.featureValue ?? "", z.kecOff ?? "", z.kelOff ?? "", z.kelMedian, z.kecValue, z.low, z.high, z.rangeKind, z.n, z.nExact, z.nKec, z.level, z.confidence, z.terrain, z.elevM, z.slopeDeg]),
                ])
              : downloadCsv(`harga-${level}-semarang.csv`, [
              ["wilayah", "kecamatan", "n_iklan", "n_lokasi_tepat", "median_ternormalisasi", "p25", "p75", "median_penawaran_asli", "periode_awal", "periode_akhir"],
              ...rows.map((s) => [s.name, s.kec, s.n, s.nExact, s.median, s.p25, s.p75, s.medianRaw, s.dateMin, s.dateMax]),
            ])
          }
        >
          <Download className="size-3.5" /> CSV {level}
        </Button>
        <Button variant="outline" size="sm" onClick={() => downloadCsv("iklan-tanah-semarang-bersih.csv", compRows(comparables))}>
          <Download className="size-3.5" /> CSV semua iklan ({comparables.length})
        </Button>
      </div>
      {useZones ? (
        <>
          <ZoneTable rows={zoneRows} />
          <p className="text-fg-muted">
            Semua {ds.data.zones?.length} kelurahan.{" "}
            {ds.data.model.featurePricing ? (
              <>
                *Median = nilai lapisan peta: harga dari <b>model fitur wilayah</b> (kepadatan bangunan, jarak ke pusat kota &amp; jalan besar, toko/pasar, lereng,
                ketinggian, pesisir/rob, lahan hijau — dilatih dari semua iklan kota; median berbobot area terbangun di dalam kelurahan) × koreksi kecamatan (setara{" "}
                {ds.data.model.featurePricing.mKec} iklan) × koreksi kelurahan (setara {ds.data.model.featurePricing.mKel} iklan). Kolom "dari fitur" = sebelum koreksi. Kelurahan tanpa iklan
                memakai karakteristiknya sendiri, bukan median kecamatan. **Rentang = ±0,674σ model (50% tengah).
              </>
            ) : (
              <>
                *Median = nilai lapisan peta: median harga ternormalisasi iklan di kelurahan itu, disusutkan ke median kecamatan. **Rentang = kuartil 25–75% bila ≥ 3 iklan.
              </>
            )}{" "}
            Tingkat data: <b>kelurahan</b> = ≥ 5 iklan; <b>kelurahan + kecamatan</b> = 1–4 iklan; <b>kecamatan</b> = belum ada iklan. Medan dari DEM Copernicus 30 m (berbukit = lereng ≥ 5° dan elevasi ≥ 40 m).
          </p>
        </>
      ) : (
        <StatTable rows={rows} showKec={level === "kelurahan"} />
      )}
      <p className="text-fg-muted">
        *Median &amp; kuartil <b>ternormalisasi</b>: harga per m² untuk bidang acuan {meta.refArea} m², akses jalan lingkungan, setelah koreksi selisih antarportal dan waktu. Kolom "median penawaran asli" = harga/m²
        apa adanya. Angka oranye = kurang dari 5 iklan (kurang andal). {meta.kelurahanTotal - meta.kelurahanCovered} kelurahan belum punya iklan sama sekali — estimasi di sana {ds.data.model.featurePricing ? "dihitung dari karakteristik wilayahnya (model fitur)" : "memakai median kecamatannya"} (tidak meminjam
        pembanding dari kelurahan tetangga).
      </p>
      <h2>Sumber</h2>
      <ul>
        {meta.sources.map((s) => (
          <li key={s.id}>
            <a href={s.url} target="_blank" rel="noopener noreferrer">
              {s.name}
            </a>{" "}
            — {s.rawCount.toLocaleString("id-ID")} iklan diambil, {s.cleanCount.toLocaleString("id-ID")} lolos pembersihan; diambil {s.scrapedAt.slice(0, 10)}. {s.note}
          </li>
        ))}
      </ul>
    </PageShell>
  );
}
