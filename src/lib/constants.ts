export const APP_NAME = "Peta Semarang";
export const PRICE_LABEL = "Estimasi kisaran harga pasar";
export const DISCLAIMER =
  "Estimasi kisaran harga pasar — bukan NJOP, bukan nilai ZNT/appraisal BPN, bukan harga transaksi resmi. Dihitung dari harga penawaran iklan tanah di sekitar titik.";

export const CITY_CENTER: [number, number] = [-6.9932, 110.4203];
export const SIMPANG_LIMA: [number, number] = [-6.990464, 110.422918];
export const TUGU_MUDA: [number, number] = [-6.984098, 110.409428];
/** Batas peta: Kota Semarang + buffer */
export const MAX_BOUNDS: [[number, number], [number, number]] = [
  [-7.22, 110.15],
  [-6.84, 110.63],
];
export const VIEWBOX = { minLng: 110.25, minLat: -7.14, maxLng: 110.53, maxLat: -6.9 };

export const RADIUS_OPTIONS = [250, 500, 1000, 2000] as const;
export type RadiusM = (typeof RADIUS_OPTIONS)[number];

export type BasemapId = "streets" | "satellite" | "hybrid";

export const ROAD_TILE_DEG = 0.01;
