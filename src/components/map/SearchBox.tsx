import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Search, X } from "lucide-react";
import { toast } from "sonner";
import { parseLatLng } from "@/lib/geo";
import { searchPlaces, type SearchHit } from "@/lib/data";
import { formatCoord } from "@/lib/utils";
import { useAppStore } from "@/lib/store";

export function SearchBox() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchHit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const setClicked = useAppStore((s) => s.setClicked);
  const setSearchMarker = useAppStore((s) => s.setSearchMarker);
  const coord = useMemo(() => parseLatLng(q), [q]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (coord) {
      setResults([]);
      setError(null);
      setOpen(true);
      return;
    }
    const t = q.trim();
    if (t.length < 3) {
      setResults([]);
      setError(null);
      setOpen(false);
      return;
    }
    const handle = window.setTimeout(async () => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      setLoading(true);
      setError(null);
      try {
        const hits = await searchPlaces(t, ac.signal);
        setResults(hits);
        setOpen(true);
        if (!hits.length) setError("Tidak ada hasil di sekitar Kota Semarang.");
      } catch (e) {
        if ((e as Error).name !== "AbortError") {
          setError("Pencarian gagal (Photon/Nominatim). Coba lagi.");
          setOpen(true);
        }
      } finally {
        setLoading(false);
      }
    }, 400);
    return () => window.clearTimeout(handle);
  }, [q, coord]);

  function goTo(lat: number, lng: number, label: string) {
    setClicked({ lat, lng });
    setSearchMarker({ lat, lng, label });
    setOpen(false);
    toast.message("Lokasi ditemukan", { description: `${formatCoord(lat)}, ${formatCoord(lng)}` });
  }

  return (
    <div className="pointer-events-auto absolute left-3 top-3 z-[600] w-[min(calc(100%-4.5rem),24rem)] md:left-4 md:top-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-muted" />
        <input
          type="search"
          autoComplete="off"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              if (coord) goTo(coord[0], coord[1], `${formatCoord(coord[0])}, ${formatCoord(coord[1])}`);
              else if (results[0]) goTo(results[0].lat, results[0].lng, results[0].label);
            }
            if (e.key === "Escape") setOpen(false);
          }}
          placeholder="Cari alamat, tempat, atau tempel lat, lng"
          className="h-11 w-full rounded-lg border border-border bg-surface/95 pl-9 pr-9 text-sm shadow-md outline-none backdrop-blur-sm placeholder:text-fg-subtle focus:border-ring"
          aria-label="Cari lokasi di Kota Semarang"
          onFocus={() => {
            if (results.length || coord) setOpen(true);
          }}
        />
        {loading ? (
          <Loader2 className="absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin text-fg-muted" />
        ) : q ? (
          <button
            type="button"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm p-1 text-fg-muted hover:text-fg"
            onClick={() => {
              setQ("");
              setResults([]);
              setOpen(false);
            }}
            aria-label="Hapus pencarian"
          >
            <X className="size-4" />
          </button>
        ) : null}
      </div>
      {open && (coord || results.length > 0 || error) ? (
        <ul className="mt-1.5 max-h-72 overflow-auto rounded-lg border border-border bg-surface/95 py-1 shadow-md backdrop-blur-sm">
          {coord ? (
            <li>
              <button
                type="button"
                className="flex w-full flex-col items-start px-3 py-2 text-left hover:bg-surface-2"
                onClick={() => goTo(coord[0], coord[1], `${formatCoord(coord[0])}, ${formatCoord(coord[1])}`)}
              >
                <span className="text-sm font-medium">Pergi ke koordinat</span>
                <span className="font-mono text-xs text-fg-muted">
                  {formatCoord(coord[0])}, {formatCoord(coord[1])}
                </span>
              </button>
            </li>
          ) : null}
          {results.map((r) => (
            <li key={`${r.lat}-${r.lng}-${r.label}`}>
              <button type="button" className="flex w-full flex-col items-start px-3 py-2 text-left hover:bg-surface-2" onClick={() => goTo(r.lat, r.lng, r.label)}>
                <span className="text-sm text-fg">{r.label}</span>
                {r.sub ? <span className="text-[11px] text-fg-muted">{r.sub}</span> : null}
                <span className="font-mono text-[11px] text-fg-subtle">
                  {formatCoord(r.lat)}, {formatCoord(r.lng)}
                </span>
              </button>
            </li>
          ))}
          {error ? <li className="px-3 py-2 text-xs text-fg-muted">{error}</li> : null}
        </ul>
      ) : null}
    </div>
  );
}
