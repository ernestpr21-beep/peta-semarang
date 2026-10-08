import { distToSegment, localProjector } from "./geo";
import type { AccessTier } from "./model";

/** Kelas jalan ringkas pada ubin OSM (lihat data-pipeline/build_app_data.py) */
export type RoadClass =
  | "tol" // motorway / motorway_link — tidak memberi akses langsung ke bidang
  | "utama" // trunk, primary, secondary, tertiary (+ link)
  | "lingkungan" // unclassified, residential, living_street, road, service umum
  | "gang" // service=alley, jalan lingkungan lebar < 3 m
  | "setapak"; // footway, path, steps, pedestrian, track, cycleway

export interface Road {
  c: RoadClass;
  n?: string; // nama
  w?: number; // lebar (m) jika ada di OSM
  hw: string; // tag highway asli
  g: number[]; // [lat1,lng1,lat2,lng2,...] (5 desimal)
}

export interface NearestRoad {
  cls: RoadClass;
  name: string | null;
  highway: string;
  width: number | null;
  distanceM: number;
}

export interface AccessDetection {
  tier: AccessTier;
  reason: string;
  nearest: Partial<Record<RoadClass, NearestRoad>>;
  /** jalan terdekat yang bisa dilalui mobil (utama/lingkungan) */
  nearestDrivable: NearestRoad | null;
  roadsChecked: number;
}

/** Ambang jarak (m) dari titik klik ke as jalan. Titik klik dianggap berada di dalam bidang. */
export const ACCESS_THRESHOLDS = {
  frontage: 30, // ≤ 30 m dari as jalan → kemungkinan besar bidang berbatasan langsung (muka jalan)
  narrow: 25, // ≤ 25 m dari gang/setapak
  inner: 60, // 30–60 m dari jalan mobil → kemungkinan bidang dalam (butuh jalan masuk/gang)
};

export function nearestRoads(lat: number, lng: number, roads: Road[]): Partial<Record<RoadClass, NearestRoad>> {
  const proj = localProjector(lat, lng);
  const best: Partial<Record<RoadClass, NearestRoad>> = {};
  for (const r of roads) {
    const g = r.g;
    let dmin = Infinity;
    let [px, py] = proj(g[0], g[1]);
    for (let i = 2; i < g.length; i += 2) {
      const [qx, qy] = proj(g[i], g[i + 1]);
      // cepat: lewati segmen yang jelas jauh
      if (!(Math.min(px, qx) > 400 || Math.max(px, qx) < -400 || Math.min(py, qy) > 400 || Math.max(py, qy) < -400)) {
        const d = distToSegment(px, py, qx, qy);
        if (d < dmin) dmin = d;
      }
      px = qx;
      py = qy;
    }
    if (dmin === Infinity) continue;
    const cur = best[r.c];
    if (!cur || dmin < cur.distanceM) {
      best[r.c] = { cls: r.c, name: r.n ?? null, highway: r.hw, width: r.w ?? null, distanceM: dmin };
    }
  }
  return best;
}

export function detectAccess(lat: number, lng: number, roads: Road[]): AccessDetection {
  const nearest = nearestRoads(lat, lng, roads);
  const T = ACCESS_THRESHOLDS;
  const utama = nearest.utama;
  const ling = nearest.lingkungan;
  const narrow = [nearest.gang, nearest.setapak].filter(Boolean).sort((a, b) => a!.distanceM - b!.distanceM)[0] ?? null;
  const drivable = [utama, ling].filter(Boolean).sort((a, b) => a!.distanceM - b!.distanceM)[0] ?? null;
  const nm = (r: NearestRoad | null | undefined) => (r?.name ? `${r.name}` : r ? `jalan tanpa nama (${r.highway})` : "");
  const m = (r: NearestRoad | null | undefined) => (r ? `${Math.round(r.distanceM)} m` : "");

  let tier: AccessTier;
  let reason: string;
  if (utama && utama.distanceM <= T.frontage) {
    tier = "utama";
    reason = `${m(utama)} dari ${nm(utama)} (jalan utama/kolektor OSM)`;
  } else if (ling && ling.distanceM <= T.frontage) {
    if (ling.width != null && ling.width < 3) {
      tier = "gang";
      reason = `${m(ling)} dari ${nm(ling)} — lebar tercatat ${ling.width} m (< 3 m)`;
    } else {
      tier = "lingkungan";
      reason = `${m(ling)} dari ${nm(ling)} (jalan lingkungan yang bisa dilalui mobil)`;
    }
  } else if (narrow && narrow.distanceM <= T.narrow) {
    tier = "gang";
    reason = `${m(narrow)} dari gang/jalan setapak (${narrow.highway}); jalan mobil terdekat ${drivable ? m(drivable) : "> 300 m"}`;
  } else if (drivable && drivable.distanceM <= T.inner) {
    tier = "gang";
    reason = `jalan mobil terdekat ${m(drivable)} — titik kemungkinan bidang dalam yang perlu jalan masuk/gang`;
  } else {
    tier = "tanpa";
    reason = drivable
      ? `tidak ada jalan/gang OSM dalam ${T.inner} m (jalan mobil terdekat ${m(drivable)})`
      : "tidak ada jalan OSM dalam radius pencarian";
  }
  return { tier, reason, nearest, nearestDrivable: drivable, roadsChecked: roads.length };
}
