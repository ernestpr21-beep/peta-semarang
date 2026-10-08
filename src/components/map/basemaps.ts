import type { BasemapId } from "@/lib/constants";

export interface TileSpec {
  url: string;
  attribution: string;
  maxZoom?: number;
  subdomains?: string;
  className?: string;
}

const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> kontributor (ODbL)';
const ESRI_ATTR = 'Citra &copy; <a href="https://www.esri.com/">Esri</a> — Maxar, Earthstar Geographics, GIS User Community';

/** Semua sumber ubin gratis tanpa kunci API. Mode gelap peta jalan = ubin OSM yang dibalik warnanya lewat CSS. */
export function getBasemapLayers(id: BasemapId, theme: "light" | "dark"): { base: TileSpec; overlays?: TileSpec[] } {
  if (id === "streets")
    return { base: { url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png", attribution: OSM_ATTR, maxZoom: 19, className: theme === "dark" ? "tiles-invert" : undefined } };
  const sat: TileSpec = {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: ESRI_ATTR,
    maxZoom: 19,
  };
  if (id === "satellite") return { base: sat };
  return {
    base: sat,
    overlays: [
      { url: "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}", attribution: "Label &copy; Esri", maxZoom: 19 },
      { url: "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", attribution: "", maxZoom: 19 },
    ],
  };
}
