// Menulis contoh estimasi ke data/sample_estimates.json (untuk README/laporan).
import { it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { estimateAt } from "./estimate.test";
import type { PriceEstimateResult } from "../src/lib/estimate";

const SAMPLES: [string, number, number][] = [
  ["Simpang Lima (tengah lapangan)", -6.990464, 110.422918],
  ["Simpang Lima (tepi, Jl. Pandanaran)", -6.98995, 110.42226],
  ["Jl. Pandanaran (Tugu Muda–Simpang Lima)", -6.98701, 110.41552],
  ["Tembalang (dekat Undip)", -7.0535, 110.4386],
  ["Banyumanik", -7.0647, 110.4178],
  ["Ngaliyan", -7.0007, 110.3466],
  ["Gunungpati", -7.0886, 110.3734],
  ["Mijen", -7.0596, 110.3070],
  ["Tugu (Mangkang)", -6.9706, 110.3216],
  ["Genuk", -6.9594, 110.4720],
  ["Pedurungan", -7.0019, 110.4661],
];

it("tulis contoh estimasi", () => {
  const out = SAMPLES.map(([name, lat, lng]) => {
    const { r, k, access } = estimateAt(lat, lng);
    const p = r as PriceEstimateResult;
    return {
      name,
      lat,
      lng,
      kelurahan: k?.name,
      kecamatan: k?.kecamatan,
      detectedAccess: access.tier,
      accessReason: access.reason,
      nUsed: p.nUsed,
      radiusM: p.radiusM,
      nearestM: Math.round(p.nearestM),
      medianDistanceM: Math.round(p.medianDistanceM),
      confidence: p.confidence,
      tiers: p.tiers,
    };
  });
  fs.writeFileSync(path.resolve(import.meta.dirname, "../data/sample_estimates.json"), JSON.stringify(out, null, 1));
});
