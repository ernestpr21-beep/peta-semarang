import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { LocationScore } from "@/lib/score";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/primitives";

export function ScoreCard({ data }: { data: LocationScore | null }) {
  const [open, setOpen] = useState(false);
  if (!data)
    return (
      <div className="space-y-2" aria-busy="true">
        <p className="text-xs text-fg-muted">Menghitung skor dari fasilitas OSM…</p>
        <Skeleton className="h-24 w-full" />
      </div>
    );
  const tone = data.total >= 75 ? "text-good" : data.total >= 45 ? "text-fg" : "text-warn";
  return (
    <div className="space-y-3">
      <p className={cn("font-mono text-3xl font-medium tabular-nums", tone)}>
        {data.total}
        <span className="ml-1 text-sm text-fg-muted">/ 100</span>
      </p>
      <ul className="space-y-2">
        {data.parts.map((p) => (
          <li key={p.id}>
            <div className="mb-0.5 flex justify-between text-xs">
              <span className="text-fg">{p.label}</span>
              <span className="font-mono tabular-nums text-fg-muted">
                {p.score.toFixed(1)}/{p.max}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-primary" style={{ width: `${(p.score / p.max) * 100}%` }} />
            </div>
            <p className="mt-0.5 text-[11px] text-fg-subtle">{p.detail}</p>
          </li>
        ))}
      </ul>
      <button type="button" onClick={() => setOpen(!open)} className="flex items-center gap-1 text-[11px] font-medium text-primary">
        <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} /> Cara hitung skor
      </button>
      {open ? (
        <p className="text-[11px] leading-relaxed text-fg-muted">
          Empat aspek fasilitas (pendidikan, kesehatan, transportasi, komersial) masing-masing 0–20: 70% dari jarak fasilitas terdekat (penuh bila dekat, nol bila jauh) + 30% dari jumlah fasilitas dalam
          1 km. Hanya fasilitas yang benar-benar ada di data OpenStreetMap yang dihitung — aspek tanpa fasilitas dalam 3 km bernilai 0. Aspek kelima: jarak ke Simpang Lima. Data OSM bisa belum lengkap,
          terutama di pinggiran kota.
        </p>
      ) : null}
    </div>
  );
}
