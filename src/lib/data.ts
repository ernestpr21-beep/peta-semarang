import { useQuery, useQueries } from "@tanstack/react-query";
import type { Dataset } from "./model";
import type { GeoCollection } from "./geo";
import type { FacilityRaw } from "./facilities";
import type { Road } from "./access";
import { ROAD_TILE_DEG } from "./constants";

/** Basis URL aplikasi ("/" lokal, "/peta-semarang/" di GitHub Pages) */
export const BASE = import.meta.env.BASE_URL;
export const dataUrl = (p: string) => `${BASE}data/${p}`;

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return (await r.json()) as T;
}

export type KotaProps = { name: string };
export type KecProps = { name: string; area_km2?: number };
export type KelProps = { name: string; kecamatan: string };

export const useDataset = () => useQuery({ queryKey: ["dataset"], queryFn: () => getJson<Dataset>(dataUrl("dataset.json")), staleTime: Infinity });
export interface PointEst {
  name: string;
  lat: number;
  lng: number;
  kelurahan?: string;
  nUsed: number;
  nExact: number;
  radiusM: number;
  area?: number;
  lingkungan: { low: number; point: number; high: number };
  utama: { low: number; point: number; high: number };
  gang?: { low: number; point: number; high: number };
  tanpa?: { low: number; point: number; high: number };
}
export interface SizeVariant {
  env: Record<string, string>;
  rss: { bins: number | null; linear: number };
  looTitik: number;
  looAllLocated: number;
  groups: Record<string, { n: number; old: number; new: number }>;
  perKecamatan: Record<string, { n: number; old: number; new: number }>;
}
export interface TerrainEval {
  dem: string;
  nTitik: number;
  slopeQuantiles: Record<string, number>;
  refBand: string;
  withinKelurahan: { band: string; coef: number; se: number; n: number }[];
  withinKecamatan: { band: string; coef: number; se: number; n: number }[];
  looResidualByBand: { band: string; n: number; q25: number; median: number; q75: number }[];
  testPoint: { name: string; lat: number; lng: number; slopeDeg: number; elevM: number };
  decision: string;
}
export interface VStat {
  mdae: number;
  cov50: number;
  bias: number;
  w25: number;
}
/** Bukti analisis untuk halaman Metodologi (data-pipeline/analysis/build_evidence.py) */
export interface Evidence {
  locationQuality: { levels: Record<string, number>; sharedPin: number; textConflict: number; kecTextOnly: number; kecOnlyByKecamatan: Record<string, number> };
  campus: {
    text: { group: string; n: number; median: number; restKec: string[]; restN: number; restMedian: number }[];
    perCampus: { campus: string; nNear: number; near: number; nFar: number; far: number }[];
    bands: { from: number; to: number | null; n: number; median: number }[];
    regression: Record<string, { from: number; to: number; coef: number; se: number; n: number }[]>;
    tembalangText: { kecOnlyN: number; kecOnlyMedian: number; kecOnlyArea: number; kelExactN: number; kelExactMedian: number; kecExactN: number; kecExactMedian: number };
  };
  frontage: Record<string, Record<string, [number, number]>>;
  beforeAfter: Record<string, { n: number; old: VStat; new: VStat }> & { perKecamatan?: Record<string, { n: number; old: VStat; new: VStat }> };
  points: { before: PointEst[]; after: PointEst[] };
  v3?: {
    sizeVariants: Record<string, SizeVariant>;
    terrain: TerrainEval;
    beforeAfter: Record<string, { n: number; old: VStat; new: VStat }> & { perKecamatan?: Record<string, { n: number; old: VStat; new: VStat }> };
    points: { before: PointEst[]; after: PointEst[] };
  };
}
export const useEvidence = () => useQuery({ queryKey: ["evidence"], queryFn: () => getJson<Evidence>(dataUrl("evidence.json")), staleTime: Infinity });
export const useKota = () => useQuery({ queryKey: ["kota"], queryFn: () => getJson<GeoCollection<KotaProps>>(dataUrl("kota.geojson")), staleTime: Infinity });
export const useKecamatan = () => useQuery({ queryKey: ["kec"], queryFn: () => getJson<GeoCollection<KecProps>>(dataUrl("kecamatan.geojson")), staleTime: Infinity });
export const useKelurahan = () => useQuery({ queryKey: ["kel"], queryFn: () => getJson<GeoCollection<KelProps>>(dataUrl("kelurahan.geojson")), staleTime: Infinity });
export const useFacilities = () =>
  useQuery({ queryKey: ["fac"], queryFn: () => getJson<{ osmBase: string; rows: FacilityRaw[] }>(dataUrl("facilities.json")), staleTime: Infinity });

/** Ubin jalan OSM 0,01° di sekitar titik (3×3) — dipakai untuk deteksi akses. */
export function roadTileKeys(lat: number, lng: number) {
  const ix = Math.floor(lng / ROAD_TILE_DEG);
  const iy = Math.floor(lat / ROAD_TILE_DEG);
  const keys: string[] = [];
  for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) keys.push(`${ix + dx}_${iy + dy}`);
  return keys;
}

async function getTile(key: string): Promise<Road[]> {
  const r = await fetch(dataUrl(`roads/${key}.json`));
  if (r.status === 404) return [];
  if (!r.ok) throw new Error(`ubin jalan ${key}: HTTP ${r.status}`);
  const ct = r.headers.get("content-type") ?? "";
  if (!ct.includes("json")) return []; // fallback SPA (ubin tidak ada)
  return (await r.json()) as Road[];
}

export function useRoadsAround(lat: number | null, lng: number | null) {
  const keys = lat == null || lng == null ? [] : roadTileKeys(lat, lng);
  const results = useQueries({
    queries: keys.map((k) => ({ queryKey: ["road", k], queryFn: () => getTile(k), staleTime: Infinity })),
  });
  const loading = results.some((r) => r.isLoading);
  const error = results.find((r) => r.isError)?.error ?? null;
  const seen = new Set<Road>();
  const roads: Road[] = [];
  if (!loading && !error) for (const r of results) for (const road of r.data ?? []) if (!seen.has(road)) { seen.add(road); roads.push(road); }
  return { loading: keys.length > 0 && loading, error, roads: loading || error ? null : roads };
}

export interface ReverseResult {
  label: string;
  road?: string;
  suburb?: string;
}

export function useReverseGeocode(lat: number | null, lng: number | null) {
  return useQuery({
    queryKey: ["rev", lat?.toFixed(5), lng?.toFixed(5)],
    enabled: lat != null && lng != null,
    staleTime: Infinity,
    retry: 1,
    queryFn: async (): Promise<ReverseResult> => {
      const u = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1&accept-language=id`;
      const r = await fetch(u, { headers: { Accept: "application/json" } });
      if (!r.ok) throw new Error(`Nominatim ${r.status}`);
      const j = await r.json();
      const a = j.address ?? {};
      const parts = [a.road ?? a.pedestrian ?? a.footway, a.neighbourhood ?? a.hamlet, a.village ?? a.suburb ?? a.quarter, a.city_district, a.city ?? a.town]
        .filter(Boolean)
        .filter((v: string, i: number, arr: string[]) => arr.indexOf(v) === i);
      return { label: parts.join(", ") || j.display_name || "", road: a.road, suburb: a.village ?? a.suburb };
    },
  });
}

export interface SearchHit {
  lat: number;
  lng: number;
  label: string;
  sub: string;
}

const VB = "110.25,-7.14,110.53,-6.90";
export async function searchPlaces(q: string, signal?: AbortSignal): Promise<SearchHit[]> {
  // 1. Photon (Komoot) — cepat, ramah autocomplete
  try {
    const u = `https://photon.komoot.io/api/?q=${encodeURIComponent(q)}&limit=8&lat=-6.99&lon=110.42&bbox=${VB}`;
    const r = await fetch(u, { signal });
    if (r.ok) {
      const j = await r.json();
      const hits: SearchHit[] = (j.features ?? []).map((f: { geometry: { coordinates: [number, number] }; properties: Record<string, string> }) => {
        const p = f.properties;
        const label = p.name ?? [p.street, p.housenumber].filter(Boolean).join(" ") ?? "";
        const sub = [p.street && p.name ? p.street : null, p.district ?? p.locality, p.city ?? p.county].filter(Boolean).join(", ");
        return { lat: f.geometry.coordinates[1], lng: f.geometry.coordinates[0], label: label || sub, sub };
      });
      if (hits.length) return hits;
    }
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
  }
  // 2. Nominatim cadangan
  const u = `https://nominatim.openstreetmap.org/search?format=jsonv2&q=${encodeURIComponent(q)}&viewbox=${VB}&bounded=1&limit=8&accept-language=id`;
  const r = await fetch(u, { signal });
  if (!r.ok) throw new Error(`Nominatim ${r.status}`);
  const j = (await r.json()) as { lat: string; lon: string; display_name: string; name?: string }[];
  return j.map((x) => ({ lat: Number(x.lat), lng: Number(x.lon), label: x.name || x.display_name.split(",")[0], sub: x.display_name.split(",").slice(1, 4).join(",").trim() }));
}
