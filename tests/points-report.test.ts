// Menulis estimasi di titik sekitar kampus + titik kontrol ke data/points_<label>.json (perbandingan sebelum/sesudah).
import { it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { estimateAt } from "./estimate.test";
import type { PriceEstimateResult } from "../src/lib/estimate";

export const POINTS: [string, number, number, number?][] = [
  ["Jl. Prof. Soedarto (depan Undip)", -7.05561, 110.43728],
  ["Jl. Banjarsari Raya", -7.05877, 110.43529],
  ["Jl. Tirto Agung (Pedalangan)", -7.05412, 110.43067],
  ["Jl. Ngesrep Timur V", -7.04851, 110.4244],
  ["Jl. Mulawarman Raya", -7.06382, 110.43814],
  ["Jl. Sumurboto Utara", -7.05092, 110.42745],
  ["Jl. Baskoro Raya", -7.05479, 110.43673],
  ["Jl. Timoho Raya", -7.06016, 110.44208],
  ["Tembalang (titik uji lama)", -7.0535, 110.4386],
  ["Sekaran (dekat Unnes)", -7.0505, 110.3925],
  ["CBD: Simpang Lima (tengah)", -6.990464, 110.422918],
  ["CBD: Simpang Lima (tepi Pandanaran)", -6.98995, 110.42226],
  ["CBD: Jl. Pandanaran (barat)", -6.98701, 110.41552],
  ["CBD: Jl. Pandanaran (timur)", -6.98882, 110.42008],
  ["CBD: Jl. Pemuda", -6.97566, 110.41821],
  ["CBD: Jl. Gajah Mada", -6.97945, 110.42111],
  ["CBD: Jl. Ahmad Yani", -6.99204, 110.42694],
  ["CBD: Jl. Pahlawan", -6.99435, 110.42062],
  ["CBD: Jl. MT Haryono (Peterongan)", -6.97997, 110.4314],
  ["CBD: Jl. MH Thamrin", -6.9857, 110.41762],
  ["CBD: Jl. Imam Bonjol", -6.97294, 110.41613],
  ["Koridor: Jl. Sultan Agung", -7.01304, 110.41751],
  ["Koridor: Jl. Setiabudi", -7.04368, 110.42154],
  ["Koridor: Jl. Majapahit", -7.003, 110.44993],
  ["Koridor: Jl. Siliwangi", -6.9873, 110.371],
  ["Kontrol: Pedurungan", -7.0019, 110.4661],
  ["Kontrol: Gunungpati", -7.0886, 110.3734],
  ["Kontrol: Mijen", -7.0596, 110.307],
  ["Kontrol: Genuk", -6.9594, 110.472],
  ["Kontrol: Banyumanik", -7.0647, 110.4178],
  // titik gang (kampung padat / perbukitan)
  ["Gang: Candisari Gg. V (titik uji pengguna, 44 m²)", -7.010649, 110.421304, 44],
  ["Gang: Candisari Gg. V (luas acuan 150 m²)", -7.010649, 110.421304],
  ["Gang: Jomblang (Candisari)", -7.0102, 110.4268],
  ["Gang: Bendan Duwur (Gajahmungkur)", -7.0182, 110.4038],
  ["Gang: Lempongsari", -7.0005, 110.4105],
  ["Gang: Bustaman (Purwodinatan)", -6.9737, 110.4289],
  ["Gang: Peterongan", -6.9918, 110.4335],
  ["Gang: Tembalang kampung", -7.0572, 110.4405],
];

// hanya dijalankan bila POINTS_LABEL di-set (mis. POINTS_LABEL=after npx vitest run tests/points-report.test.ts)
it.skipIf(!process.env.POINTS_LABEL)("tulis estimasi titik", () => {
  const label = process.env.POINTS_LABEL as string;
  const out = POINTS.map(([name, lat, lng, area]) => {
    const { r, k } = estimateAt(lat, lng, area ?? 150);
    const p = r as PriceEstimateResult;
    const t = (x: { low: number; high: number; point: number }) => ({ low: Math.round(x.low), point: Math.round(x.point), high: Math.round(x.high) });
    return {
      name, lat, lng, area: area ?? 150, kelurahan: k?.name, nUsed: p.nUsed, nExact: p.nExact, radiusM: p.radiusM,
      utama: t(p.tiers.utama), lingkungan: t(p.tiers.lingkungan), gang: t(p.tiers.gang), tanpa: t(p.tiers.tanpa),
    };
  });
  fs.writeFileSync(path.resolve(import.meta.dirname, `../data/points_${label}.json`), JSON.stringify(out, null, 1));
});
