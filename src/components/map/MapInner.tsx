import { useEffect, useMemo, useState } from "react";
import { Circle, CircleMarker, GeoJSON, MapContainer, Marker, Pane, Polygon, ScaleControl, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { toast } from "sonner";
import { Crosshair, LocateFixed, Minus, Plus } from "lucide-react";
import { CITY_CENTER, MAX_BOUNDS, SIMPANG_LIMA } from "@/lib/constants";
import { useAppStore } from "@/lib/store";
import { useDataset, useKecamatan, useKelurahan, useKota } from "@/lib/data";
import type { GeoCollection } from "@/lib/geo";
import { findAreaStat } from "@/lib/estimate";
import { formatCoord, formatRupiahShort, normalizeName } from "@/lib/utils";
import { useLocationDetails } from "@/hooks/useLocationDetails";
import { getBasemapLayers } from "./basemaps";
import { priceColor } from "./priceColor";

const pinIcon = L.divIcon({ className: "semarang-pin", html: '<div class="semarang-pin-dot"></div>', iconSize: [18, 18], iconAnchor: [9, 18] });
const facilityIcon = (g: string) => L.divIcon({ className: "semarang-pin", html: `<div class="facility-dot" data-g="${g}"></div>`, iconSize: [10, 10], iconAnchor: [5, 5] });
const canvas = L.canvas({ padding: 0.3 });

function MapEvents() {
  const setClicked = useAppStore((s) => s.setClicked);
  const setCursor = useAppStore((s) => s.setCursor);
  const setSearchMarker = useAppStore((s) => s.setSearchMarker);
  useMapEvents({
    click(e) {
      const t = e.originalEvent.target as HTMLElement | null;
      if (t?.closest(".leaflet-control, button, a, input")) return;
      setSearchMarker(null);
      setClicked({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
    mousemove(e) {
      setCursor({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
    mouseout() {
      setCursor(null);
    },
  });
  return null;
}

function FlyController() {
  const map = useMap();
  const clicked = useAppStore((s) => s.clicked);
  const focus = useAppStore((s) => s.focusTarget);
  useEffect(() => {
    if (!clicked) return;
    if (!map.getBounds().pad(-0.15).contains([clicked.lat, clicked.lng]) || map.getZoom() < 15)
      map.flyTo([clicked.lat, clicked.lng], Math.max(map.getZoom(), 16), { duration: 0.55 });
  }, [clicked, map]);
  useEffect(() => {
    if (focus) map.flyTo([focus.lat, focus.lng], focus.zoom ?? Math.max(map.getZoom(), 17), { duration: 0.6 });
  }, [focus, map]);
  return null;
}

function ZoomWatcher({ onZoom }: { onZoom: (z: number) => void }) {
  const map = useMapEvents({ zoomend: () => onZoom(map.getZoom()) });
  useEffect(() => onZoom(map.getZoom()), [map, onZoom]);
  return null;
}

function Controls() {
  const map = useMap();
  const flyTo = useAppStore((s) => s.flyTo);
  function locate() {
    if (!navigator.geolocation) return toast.error("Geolokasi tidak tersedia di peramban ini");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude: lat, longitude: lng } = pos.coords;
        const [[s, w], [n, e]] = MAX_BOUNDS;
        if (lat < s || lat > n || lng < w || lng > e) {
          toast.message("Lokasi Anda di luar cakupan peta Kota Semarang");
          return;
        }
        useAppStore.getState().setClicked({ lat, lng });
        useAppStore.getState().setSearchMarker({ lat, lng, label: "Lokasi saya" });
      },
      () => toast.error("Tidak bisa membaca lokasi"),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }
  const btn = "flex size-10 items-center justify-center rounded-md border border-border bg-surface/95 shadow-sm hover:bg-surface-2";
  return (
    <div className="pointer-events-auto absolute right-3 top-16 z-[500] flex flex-col gap-1 md:right-4">
      <button type="button" className={btn} onClick={() => map.zoomIn()} aria-label="Perbesar" title="Perbesar">
        <Plus className="size-4" />
      </button>
      <button type="button" className={btn} onClick={() => map.zoomOut()} aria-label="Perkecil" title="Perkecil">
        <Minus className="size-4" />
      </button>
      <button type="button" className={`${btn} mt-1`} onClick={locate} aria-label="Lokasi saya" title="Lokasi saya">
        <LocateFixed className="size-4" />
      </button>
      <button
        type="button"
        className={btn}
        onClick={() => flyTo({ lat: SIMPANG_LIMA[0], lng: SIMPANG_LIMA[1] }, 14)}
        aria-label="Ke pusat kota"
        title="Ke pusat kota (Simpang Lima)"
      >
        <Crosshair className="size-4" />
      </button>
    </div>
  );
}

function CursorHud() {
  const cursor = useAppStore((s) => s.cursor);
  const hover = useAppStore((s) => s.hoverKecamatan);
  if (!cursor) return null;
  return (
    <div className="pointer-events-none absolute bottom-16 left-3 z-[500] hidden rounded-md border border-border bg-surface/90 px-2 py-1 font-mono text-[11px] tabular-nums text-fg-muted shadow-sm backdrop-blur-sm md:left-4 md:block">
      {formatCoord(cursor.lat)}, {formatCoord(cursor.lng)}
      {hover ? <span className="ml-2 font-sans text-fg">{hover}</span> : null}
    </div>
  );
}

/** Topeng gelap di luar batas kota */
function CityMask({ kota, theme }: { kota: GeoCollection<{ name: string }>; theme: string }) {
  const positions = useMemo(() => {
    const world: [number, number][] = [
      [-8.5, 109],
      [-8.5, 112],
      [-5.5, 112],
      [-5.5, 109],
    ];
    const holes: [number, number][][] = [];
    for (const f of kota.features) {
      const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
      for (const p of polys) holes.push(p[0].map(([lng, lat]) => [lat, lng] as [number, number]));
    }
    return [world, ...holes];
  }, [kota]);
  return (
    <Polygon
      positions={positions}
      interactive={false}
      pathOptions={{ stroke: false, fillColor: theme === "dark" ? "#07090a" : "#1c1f24", fillOpacity: theme === "dark" ? 0.45 : 0.18 }}
    />
  );
}

export default function MapInner() {
  const theme = useAppStore((s) => s.theme);
  const basemap = useAppStore((s) => s.basemap);
  const clicked = useAppStore((s) => s.clicked);
  const searchMarker = useAppStore((s) => s.searchMarker);
  const radiusM = useAppStore((s) => s.radiusM);
  const showComps = useAppStore((s) => s.showComparables);
  const showPrice = useAppStore((s) => s.showPriceLayer);
  const hover = useAppStore((s) => s.hoverKecamatan);
  const setHover = useAppStore((s) => s.setHoverKecamatan);
  const layers = useMemo(() => getBasemapLayers(basemap, theme), [basemap, theme]);
  const kota = useKota();
  const kec = useKecamatan();
  const kel = useKelurahan();
  const ds = useDataset();
  const details = useLocationDetails();
  const [zoom, setZoom] = useState(12);
  const ink = theme === "dark" ? "#9fd0c8" : "#0f6e6a";

  const kelColor = useMemo(() => {
    const m = new Map<string, number>();
    if (ds.data) for (const s of ds.data.kelurahan) m.set(`${normalizeName(s.name)}|${normalizeName(s.kec)}`, s.median);
    return m;
  }, [ds.data]);

  const usedIds = useMemo(() => {
    const p = details.price;
    return new Set(p && p.available ? p.used.map((u) => u.c.id) : []);
  }, [details.price]);

  return (
    <MapContainer
      center={CITY_CENTER}
      zoom={12}
      minZoom={11}
      maxZoom={19}
      maxBounds={MAX_BOUNDS}
      maxBoundsViscosity={0.85}
      zoomControl={false}
      className="h-full w-full"
      style={{ background: "var(--bg)" }}
    >
      <Pane name="labels" style={{ zIndex: 450, pointerEvents: "none" }} />
      <TileLayer
        key={`${layers.base.url}-${layers.base.className ?? ""}`}
        url={layers.base.url}
        attribution={layers.base.attribution}
        maxZoom={19}
        maxNativeZoom={layers.base.maxZoom}
        className={layers.base.className}
        {...(layers.base.subdomains ? { subdomains: layers.base.subdomains } : {})}
      />
      {(layers.overlays ?? []).map((o) => (
        <TileLayer key={o.url} url={o.url} attribution={o.attribution} pane="labels" maxZoom={19} maxNativeZoom={o.maxZoom} />
      ))}
      {kota.data ? <CityMask kota={kota.data} theme={theme} /> : null}

      {showPrice && kel.data && ds.data ? (
        <GeoJSON
          key={`kel-${theme}`}
          data={kel.data as unknown as GeoJSON.FeatureCollection}
          style={(f) => {
            const p = f?.properties as { name: string; kecamatan: string };
            const v = kelColor.get(`${normalizeName(p.name)}|${normalizeName(p.kecamatan)}`);
            return { color: ink, weight: 0.6, fillColor: v ? priceColor(v) : "transparent", fillOpacity: v ? 0.45 : 0 };
          }}
          onEachFeature={(f, layer) => {
            const p = f.properties as { name: string; kecamatan: string };
            const st = ds.data ? findAreaStat(ds.data.kelurahan, p.name, p.kecamatan) : null;
            layer.bindTooltip(
              `<b>${p.name}</b> · ${p.kecamatan}<br/>${st ? `median ${formatRupiahShort(st.median)}/m² (n=${st.n})` : "belum ada data iklan"}`,
              { sticky: true },
            );
          }}
        />
      ) : null}

      {kec.data ? (
        <GeoJSON
          key={`kec-${theme}-${hover ?? ""}`}
          data={kec.data as unknown as GeoJSON.FeatureCollection}
          style={(f) => {
            const name = (f?.properties as { name: string }).name;
            const active = name === hover || name === details.kecamatan;
            return { color: ink, weight: active ? 2.2 : 1, fillColor: ink, fillOpacity: showPrice ? 0 : name === details.kecamatan ? 0.12 : name === hover ? 0.1 : 0.03 };
          }}
          onEachFeature={(f, layer) => {
            const name = (f.properties as { name: string }).name;
            layer.on({ mouseover: () => setHover(name), mouseout: () => setHover(null) });
          }}
        />
      ) : null}

      {showComps && ds.data && zoom >= 13
        ? ds.data.comparables.map((c) => {
            const used = usedIds.has(c.id);
            return (
              <CircleMarker
                key={c.id}
                renderer={canvas}
                center={[c.lat, c.lng]}
                radius={used ? 6 : zoom >= 15 ? 4.5 : 3.5}
                bubblingMouseEvents={false}
                pathOptions={{
                  color: used ? (theme === "dark" ? "#fff" : "#1c1f24") : theme === "dark" ? "#0e1210" : "#fffcf7",
                  weight: used ? 2 : 1,
                  fillColor: priceColor(c.pn),
                  fillOpacity: c.exact ? 0.9 : 0.45,
                  dashArray: c.exact ? undefined : "2 2",
                }}
                eventHandlers={{ click: () => window.open(c.url, "_blank", "noopener") }}
              >
                <Tooltip direction="top">
                  <div className="text-[11px] leading-snug">
                    <b>{formatRupiahShort(c.ppm)}/m²</b> · {c.area.toLocaleString("id-ID")} m²
                    <br />
                    {c.kel}, {c.kec} · {c.src} {c.date}
                    <br />
                    akses: {c.tier ?? "tidak disebut"} · {c.exact ? "titik iklan" : "perkiraan (pusat kelurahan)"}
                    <br />
                    <span style={{ opacity: 0.7 }}>klik untuk buka iklan</span>
                  </div>
                </Tooltip>
              </CircleMarker>
            );
          })
        : null}

      {clicked ? (
        <>
          <Circle center={[clicked.lat, clicked.lng]} radius={radiusM} interactive={false} pathOptions={{ color: ink, weight: 1, fillOpacity: 0.05, dashArray: "4 4" }} />
          <Marker position={[clicked.lat, clicked.lng]} icon={pinIcon} />
        </>
      ) : null}
      {searchMarker && (!clicked || searchMarker.lat !== clicked.lat || searchMarker.lng !== clicked.lng) ? (
        <Marker position={[searchMarker.lat, searchMarker.lng]} icon={pinIcon} />
      ) : null}
      {(details.facilities ?? []).slice(0, 40).map((f) => (
        <Marker key={f.id} position={[f.lat, f.lng]} icon={facilityIcon(f.group)}>
          <Tooltip direction="top">{f.name}</Tooltip>
        </Marker>
      ))}
      <ScaleControl position="bottomleft" imperial={false} />
      <MapEvents />
      <FlyController />
      <ZoomWatcher onZoom={setZoom} />
      <Controls />
      <CursorHud />
    </MapContainer>
  );
}
