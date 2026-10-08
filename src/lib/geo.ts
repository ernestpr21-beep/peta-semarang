export type LatLng = [number, number];

const R = 6371008.8;
const toRad = (d: number) => (d * Math.PI) / 180;

export function haversineMeters(lat1: number, lng1: number, lat2: number, lng2: number) {
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

/** Proyeksi equirectangular lokal (meter) — akurat untuk jarak < beberapa km. */
export function localProjector(lat0: number, lng0: number) {
  const kx = (Math.PI / 180) * R * Math.cos(toRad(lat0));
  const ky = (Math.PI / 180) * R;
  return (lat: number, lng: number): [number, number] => [(lng - lng0) * kx, (lat - lat0) * ky];
}

/** Jarak titik (0,0) ke segmen AB dalam meter (koordinat sudah diproyeksikan). */
export function distToSegment(ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  let t = len2 > 0 ? -(ax * dx + ay * dy) / len2 : 0;
  t = Math.max(0, Math.min(1, t));
  const x = ax + t * dx;
  const y = ay + t * dy;
  return Math.sqrt(x * x + y * y);
}

type Ring = number[][]; // [lng, lat]
type PolygonCoords = Ring[];
export interface GeoFeature<P> {
  type: "Feature";
  properties: P;
  geometry: { type: "Polygon"; coordinates: PolygonCoords } | { type: "MultiPolygon"; coordinates: PolygonCoords[] };
}
export interface GeoCollection<P> {
  type: "FeatureCollection";
  features: GeoFeature<P>[];
}

function pointInRing(lng: number, lat: number, ring: Ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-15) + xi) inside = !inside;
  }
  return inside;
}

function pointInPolygon(lng: number, lat: number, poly: PolygonCoords) {
  if (!poly.length || !pointInRing(lng, lat, poly[0])) return false;
  for (let i = 1; i < poly.length; i++) if (pointInRing(lng, lat, poly[i])) return false;
  return true;
}

export function pointInFeature<P>(lat: number, lng: number, f: GeoFeature<P>) {
  const g = f.geometry;
  if (g.type === "Polygon") return pointInPolygon(lng, lat, g.coordinates);
  return g.coordinates.some((p) => pointInPolygon(lng, lat, p));
}

export function findFeature<P>(lat: number, lng: number, fc: GeoCollection<P> | null | undefined) {
  if (!fc) return null;
  for (const f of fc.features) if (pointInFeature(lat, lng, f)) return f;
  return null;
}

export function featureBounds<P>(f: GeoFeature<P>): [[number, number], [number, number]] {
  let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
  const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
  for (const p of polys)
    for (const [lng, lat] of p[0]) {
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
    }
  return [[minLat, minLng], [maxLat, maxLng]];
}

/** Parse "lat, lng" (atau "lat lng"), terima koma desimal ala Indonesia bila dipisah titik koma. */
export function parseLatLng(input: string): LatLng | null {
  const s = input.trim().replace(/[()]/g, "");
  const m = s.match(/^(-?\d{1,2}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)$/);
  if (!m) return null;
  const fix = (x: string) => Number(x.replace(",", "."));
  // jika dipisah koma & desimal pakai titik → aman. Jika "−6,98 110,42" (koma desimal, spasi pemisah) juga ditangani.
  const lat = fix(m[1]);
  const lng = fix(m[2]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  return [lat, lng];
}

/** Jarak (m) dari titik ke poligon cincin [lat, lng][]; 0 bila di dalam. */
export function distanceToRingsM(lat: number, lng: number, rings: number[][][]) {
  const proj = localProjector(lat, lng);
  let best = Infinity;
  for (const ring of rings) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [yi, xi] = ring[i];
      const [yj, xj] = ring[j];
      if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-15) + xi) inside = !inside;
    }
    if (inside) return 0;
    for (let i = 1; i < ring.length; i++) {
      const [ax, ay] = proj(ring[i - 1][0], ring[i - 1][1]);
      const [bx, by] = proj(ring[i][0], ring[i][1]);
      best = Math.min(best, distToSegment(ax, ay, bx, by));
    }
  }
  return best;
}

/** Kampus terdekat (poligon OSM) dari titik. */
export function nearestCampus(lat: number, lng: number, campuses: { name: string; rings: number[][][] }[] | undefined) {
  let best: { name: string; distanceM: number } | null = null;
  for (const c of campuses ?? []) {
    // saringan kasar: lewati kampus yang titik pertamanya > 6 km
    const f = c.rings[0]?.[0];
    if (f && haversineMeters(lat, lng, f[0], f[1]) > 6000) continue;
    const d = distanceToRingsM(lat, lng, c.rings);
    if (!best || d < best.distanceM) best = { name: c.name, distanceM: d };
  }
  return best;
}
