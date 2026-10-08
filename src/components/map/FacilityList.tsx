import { useState } from "react";
import { MapPin } from "lucide-react";
import { RADIUS_OPTIONS } from "@/lib/constants";
import { GROUP_LABEL, GROUP_ORDER, travelTimeLabel, type Facility } from "@/lib/facilities";
import { useAppStore } from "@/lib/store";
import { cn, formatDistance } from "@/lib/utils";
import { Skeleton } from "@/components/ui/primitives";

export function FacilityList({ facilities }: { facilities: Facility[] | null }) {
  const radiusM = useAppStore((s) => s.radiusM);
  const setRadius = useAppStore((s) => s.setRadius);
  const flyTo = useAppStore((s) => s.flyTo);
  const [showAll, setShowAll] = useState(false);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1" role="tablist" aria-label="Radius fasilitas">
        {RADIUS_OPTIONS.map((r) => (
          <button
            key={r}
            type="button"
            role="tab"
            aria-selected={radiusM === r}
            onClick={() => setRadius(r)}
            className={cn("h-8 rounded-full px-2.5 text-xs font-medium", radiusM === r ? "bg-primary text-primary-foreground" : "bg-surface-2 text-fg-muted hover:text-fg")}
          >
            {formatDistance(r)}
          </button>
        ))}
      </div>
      {!facilities ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : (
        <>
          {GROUP_ORDER.map((g) => {
            const all = facilities.filter((f) => f.group === g);
            const list = showAll ? all : all.slice(0, 4);
            return (
              <section key={g}>
                <div className="mb-1 flex items-baseline justify-between">
                  <h4 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
                    <span className="facility-dot inline-block !size-2.5" data-g={g} />
                    {GROUP_LABEL[g]}
                  </h4>
                  <span className="text-[11px] text-fg-subtle">{all.length} titik</span>
                </div>
                {list.length === 0 ? (
                  <p className="text-xs text-fg-muted">Tidak ada dalam radius ini (menurut data OSM).</p>
                ) : (
                  <ul className="space-y-0.5">
                    {list.map((f) => (
                      <li key={f.id} className="flex items-start justify-between gap-2 rounded-md px-1 py-1 hover:bg-surface-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm text-fg">{f.name}</p>
                          <p className="text-[11px] text-fg-muted">
                            {f.kindLabel} · {formatDistance(f.distanceM)} · {travelTimeLabel(f.distanceM)}
                          </p>
                        </div>
                        <button
                          type="button"
                          className="flex size-8 shrink-0 items-center justify-center rounded-md hover:bg-surface"
                          aria-label={`Fokus ke ${f.name}`}
                          onClick={() => flyTo({ lat: f.lat, lng: f.lng })}
                        >
                          <MapPin className="size-3.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
          {facilities.length > 4 ? (
            <button type="button" className="h-9 w-full rounded-md border border-border text-sm hover:bg-surface-2" onClick={() => setShowAll(!showAll)}>
              {showAll ? "Tampilkan 4 terdekat per kelompok" : "Lihat semua"}
            </button>
          ) : null}
          <p className="text-[10.5px] text-fg-subtle">Jarak garis lurus; waktu tempuh perkiraan kasar.</p>
        </>
      )}
    </div>
  );
}
