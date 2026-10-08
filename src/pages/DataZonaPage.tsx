import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import { useDataset } from "@/lib/data";
import type { AreaStat, Comparable } from "@/lib/model";
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

export function DataZonaPage() {
  const ds = useDataset();
  const [level, setLevel] = useState<"kecamatan" | "kelurahan">("kecamatan");
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    if (!ds.data) return [];
    const list = level === "kecamatan" ? ds.data.kecamatan : ds.data.kelurahan;
    const s = q.trim().toLowerCase();
    return s ? list.filter((r) => r.name.toLowerCase().includes(s) || r.kec.toLowerCase().includes(s)) : list;
  }, [ds.data, level, q]);

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
            downloadCsv(`harga-${level}-semarang.csv`, [
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
      <StatTable rows={rows} showKec={level === "kelurahan"} />
      <p className="text-fg-muted">
        *Median &amp; kuartil <b>ternormalisasi</b>: harga per m² untuk bidang acuan {meta.refArea} m², akses jalan lingkungan, setelah koreksi selisih antarportal dan waktu. Kolom "median penawaran asli" = harga/m²
        apa adanya. Angka oranye = kurang dari 5 iklan (kurang andal). {meta.kelurahanTotal - meta.kelurahanCovered} kelurahan belum punya iklan sama sekali — estimasi di sana bertumpu pada pembanding dari kelurahan
        tetangga.
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
