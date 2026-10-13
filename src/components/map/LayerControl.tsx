import { useState } from "react";
import { Layers, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import type { BasemapId } from "@/lib/constants";
import { PRICE_LEGEND } from "./priceColor";

const BASEMAPS: { id: BasemapId; label: string }[] = [
  { id: "streets", label: "Jalan" },
  { id: "satellite", label: "Satelit" },
  { id: "hybrid", label: "Hibrid" },
];

export function LayerControl() {
  const basemap = useAppStore((s) => s.basemap);
  const setBasemap = useAppStore((s) => s.setBasemap);
  const showComps = useAppStore((s) => s.showComparables);
  const setShowComps = useAppStore((s) => s.setShowComparables);
  const showPrice = useAppStore((s) => s.showPriceLayer);
  const setShowPrice = useAppStore((s) => s.setShowPriceLayer);
  const [open, setOpen] = useState(false);

  return (
    <>
    {showPrice && !open ? (
      <div className="pointer-events-none absolute bottom-24 right-3 z-[500] rounded-md border border-border bg-surface/90 px-2 py-1.5 text-[10px] shadow-sm backdrop-blur-sm md:bottom-8 md:right-4">
        <p className="mb-0.5 font-medium text-fg">Median Rp/m² per kelurahan</p>
        <ul className="space-y-0.5">
          {PRICE_LEGEND.map((l) => (
            <li key={l.label} className="flex items-center gap-1.5 text-fg-muted">
              <span className="h-2.5 w-3.5 rounded-sm" style={{ background: l.color, opacity: 0.8 }} />
              {l.label}
            </li>
          ))}
        </ul>
      </div>
    ) : null}
    <div className="pointer-events-auto absolute right-3 top-3 z-[600] flex flex-col items-end gap-1.5 md:right-4 md:top-4">
      <div className="flex items-center gap-1 rounded-lg border border-border bg-surface/95 p-1 shadow-md backdrop-blur-sm">
        <div className="hidden items-center gap-1 sm:flex">
          {BASEMAPS.map((l) => (
            <button
              key={l.id}
              type="button"
              onClick={() => setBasemap(l.id)}
              className={cn("h-8 rounded-md px-2.5 text-xs font-medium", basemap === l.id ? "bg-primary text-primary-foreground" : "text-fg-muted hover:bg-surface-2 hover:text-fg")}
            >
              {l.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          aria-label="Lapisan peta"
          title="Lapisan peta"
          className={cn("flex size-8 items-center justify-center rounded-md", open ? "bg-surface-2 text-fg" : "text-fg-muted hover:bg-surface-2")}
        >
          {open ? <X className="size-4" /> : <Layers className="size-4" />}
        </button>
      </div>
      {open ? (
        <div className="w-60 space-y-3 rounded-lg border border-border bg-surface/95 p-3 text-xs shadow-md backdrop-blur-sm">
          <div className="flex gap-1 sm:hidden">
            {BASEMAPS.map((l) => (
              <button
                key={l.id}
                type="button"
                onClick={() => setBasemap(l.id)}
                className={cn("h-8 flex-1 rounded-md text-xs font-medium", basemap === l.id ? "bg-primary text-primary-foreground" : "bg-surface-2 text-fg-muted")}
              >
                {l.label}
              </button>
            ))}
          </div>
          <label className="flex cursor-pointer items-start gap-2">
            <input type="checkbox" className="mt-0.5 accent-[var(--primary)]" checked={showComps} onChange={(e) => setShowComps(e.target.checked)} />
            <span>
              <span className="font-medium text-fg">Titik data pembanding</span>
              <span className="block text-fg-muted">Iklan tanah (tampil mulai zoom 13). Garis putus = lokasi perkiraan.</span>
            </span>
          </label>
          <label className="flex cursor-pointer items-start gap-2">
            <input type="checkbox" className="mt-0.5 accent-[var(--primary)]" checked={showPrice} onChange={(e) => setShowPrice(e.target.checked)} />
            <span>
              <span className="font-medium text-fg">Median harga per kelurahan</span>
              <span className="block text-fg-muted">Lapisan utama. Bidang acuan 150 m², akses jalan lingkungan. Nilai dari model fitur wilayah + koreksi data kelurahan. Arsir putus-putus = belum ada iklan (murni dari fitur).</span>
            </span>
          </label>
          <div>
            <p className="mb-1 font-medium text-fg">Warna harga / m²</p>
            <ul className="grid grid-cols-2 gap-x-2 gap-y-0.5">
              {PRICE_LEGEND.map((l) => (
                <li key={l.label} className="flex items-center gap-1.5 text-fg-muted">
                  <span className="size-2.5 rounded-full" style={{ background: l.color }} />
                  {l.label}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </div>
    </>
  );
}
