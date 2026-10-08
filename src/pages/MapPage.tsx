import { MapView } from "@/components/map/MapView";
import { SearchBox } from "@/components/map/SearchBox";
import { LayerControl } from "@/components/map/LayerControl";
import { ClickPanel } from "@/components/map/ClickPanel";
import { MobileSheet } from "@/components/map/MobileSheet";
import { useAppStore } from "@/lib/store";
import { SIMPANG_LIMA } from "@/lib/constants";
import { Navigation } from "lucide-react";
import { useIsMobile } from "@/hooks/useIsMobile";

export function MapPage() {
  const flyTo = useAppStore((s) => s.flyTo);
  const clicked = useAppStore((s) => s.clicked);
  const setPanelOpen = useAppStore((s) => s.setPanelOpen);
  const mobile = useIsMobile();
  return (
    <main className="relative flex h-[calc(100svh-3.5rem)] min-h-0">
      <div className="relative min-h-0 min-w-0 flex-1 overflow-hidden">
        <MapView />
        <SearchBox />
        <LayerControl />
        <button
          type="button"
          onClick={() => flyTo({ lat: SIMPANG_LIMA[0], lng: SIMPANG_LIMA[1] }, 14)}
          className="pointer-events-auto absolute bottom-8 right-3 z-[500] flex h-10 items-center gap-1.5 rounded-full border border-border bg-surface/95 px-3.5 text-xs font-medium shadow-md backdrop-blur-sm hover:bg-surface-2 md:right-4"
        >
          <Navigation className="size-3.5 text-primary" /> Ke pusat kota
        </button>
        {clicked ? (
          <button
            type="button"
            onClick={() => setPanelOpen(true)}
            className="pointer-events-auto absolute bottom-20 left-1/2 z-[500] -translate-x-1/2 rounded-full bg-primary px-4 py-2 text-xs font-medium text-primary-foreground shadow-md md:hidden"
          >
            Lihat detail lokasi
          </button>
        ) : null}
        <div className="pointer-events-none absolute bottom-8 left-3 z-[500] max-w-[min(60vw,22rem)] md:left-4">
          <p className="pointer-events-auto rounded-lg border border-border bg-surface/90 px-3 py-1.5 text-[11px] leading-snug text-fg-muted shadow-sm">
            Estimasi kisaran harga pasar dari iklan — <b>bukan NJOP</b>, bukan ZNT/appraisal BPN.
          </p>
        </div>
      </div>
      {!mobile ? (
        <aside className="flex w-[400px] shrink-0 flex-col border-l border-border bg-surface">
          <ClickPanel />
        </aside>
      ) : null}
      <MobileSheet />
    </main>
  );
}
