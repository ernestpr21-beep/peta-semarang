import { haversineMeters } from "./geo";
import { SIMPANG_LIMA } from "./constants";
import type { Facility, FacilityGroup } from "./facilities";
import { formatDistance } from "./utils";

export interface ScorePart {
  id: string;
  label: string;
  score: number;
  max: number;
  detail: string;
  found: number;
}

export interface LocationScore {
  total: number;
  parts: ScorePart[];
}

/** Jarak "baik" dan "jauh" (meter) per aspek, serta target jumlah fasilitas dalam 1 km. */
export const SCORE_RULES: Record<"pendidikan" | "kesehatan" | "transportasi" | "komersial", { good: number; far: number; target: number; label: string }> = {
  pendidikan: { good: 400, far: 3000, target: 6, label: "Akses pendidikan" },
  kesehatan: { good: 600, far: 4000, target: 4, label: "Akses kesehatan" },
  transportasi: { good: 300, far: 2500, target: 4, label: "Akses transportasi" },
  komersial: { good: 400, far: 2500, target: 6, label: "Akses komersial" },
};

export const SCORE_SEARCH_RADIUS = 3000;

function lin(d: number, good: number, far: number) {
  if (d <= good) return 1;
  if (d >= far) return 0;
  return 1 - (d - good) / (far - good);
}

/**
 * Skor 0–100 hanya dari fasilitas yang BENAR-BENAR ditemukan di data OSM.
 * Tiap aspek 0–20 = 20 × (0,7 × skor jarak fasilitas terdekat + 0,3 × kepadatan dalam 1 km).
 * Jika tidak ada fasilitas sama sekali dalam radius pencarian → 0 (bukan 100).
 */
export function computeLocationScore(lat: number, lng: number, facilities: Facility[]): LocationScore {
  const parts: ScorePart[] = [];
  for (const g of Object.keys(SCORE_RULES) as (keyof typeof SCORE_RULES)[]) {
    const rule = SCORE_RULES[g];
    const list = facilities.filter((f) => f.group === (g as FacilityGroup));
    const nearest = list[0];
    const within1k = list.filter((f) => f.distanceM <= 1000).length;
    let score = 0;
    let detail: string;
    if (!nearest) {
      detail = `Tidak ada fasilitas ${rule.label.replace("Akses ", "")} di data OSM dalam ${formatDistance(SCORE_SEARCH_RADIUS)} → 0`;
    } else {
      const sd = lin(nearest.distanceM, rule.good, rule.far);
      const sc = Math.min(1, within1k / rule.target);
      score = 20 * (0.7 * sd + 0.3 * sc);
      detail = `Terdekat: ${nearest.name} (${formatDistance(nearest.distanceM)}); ${within1k} dalam 1 km`;
    }
    parts.push({ id: g, label: rule.label, score: Math.round(score * 10) / 10, max: 20, detail, found: list.length });
  }
  const cbd = haversineMeters(lat, lng, SIMPANG_LIMA[0], SIMPANG_LIMA[1]);
  parts.push({
    id: "pusat",
    label: "Posisi ke pusat kota",
    max: 20,
    score: Math.round(20 * lin(cbd, 1500, 15000) * 10) / 10,
    detail: `${formatDistance(cbd)} ke Simpang Lima (penuh ≤ 1,5 km, nol ≥ 15 km)`,
    found: 1,
  });
  return { total: Math.round(parts.reduce((s, p) => s + p.score, 0)), parts };
}
