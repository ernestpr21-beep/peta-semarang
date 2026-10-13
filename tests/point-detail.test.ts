// Audit: rincian estimasi (deteksi akses, semua tier, pembanding) di titik-titik → DETAIL_OUT. Hanya bila DETAIL_IN & DETAIL_OUT di-set.
import { it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { estimatePrice, findAreaStat, type PriceEstimateResult } from "../src/lib/estimate";
import { detectAccess, namedMainRoadsWithin, type Road } from "../src/lib/access";
import { findFeature, nearestCampus, type GeoCollection } from "../src/lib/geo";
import type { Dataset, FeatureGrid } from "../src/lib/model";
import { featureAt } from "../src/lib/data";

const PUB = path.resolve(import.meta.dirname, "../public/data");
it.skipIf(!process.env.DETAIL_OUT)("rincian titik", () => {
  const pts = JSON.parse(fs.readFileSync(process.env.DETAIL_IN as string, "utf8")) as [string, number, number, number?][];
  const ds = JSON.parse(fs.readFileSync(process.env.DETAIL_DATASET ?? path.join(PUB, "dataset.json"), "utf8")) as Dataset;
  const kel = JSON.parse(fs.readFileSync(path.join(PUB, "kelurahan.geojson"), "utf8")) as GeoCollection<{ name: string; kecamatan: string }>;
  const fgp = path.join(PUB, "feature-grid.json");
  const fgRaw = ds.model.featurePricing && fs.existsSync(fgp) ? (JSON.parse(fs.readFileSync(fgp, "utf8")) as FeatureGrid) : null;
  const fg = fgRaw ? { ...fgRaw, pos: new Map(fgRaw.idx.map((v, i) => [v, i] as [number, number])) } : undefined;
  const roadsAround = (lat: number, lng: number) => {
    const out: Road[] = [];
    for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) {
      const p = path.join(PUB, "roads", `${Math.floor(lng / 0.01) + dx}_${Math.floor(lat / 0.01) + dy}.json`);
      if (fs.existsSync(p)) out.push(...(JSON.parse(fs.readFileSync(p, "utf8")) as Road[]));
    }
    return out;
  };
  const out = pts.map(([name, lat, lng, area]) => {
    const k = findFeature(lat, lng, kel)?.properties;
    const rd = roadsAround(lat, lng);
    const acc = detectAccess(lat, lng, rd);
    const u = acc.nearest.utama;
    const near = process.env.DETAIL_NEAREST_ONLY ? (u ? [{ name: u.name, distanceM: u.distanceM }] : []) : namedMainRoadsWithin(lat, lng, rd, ds.model.corridor?.maxRoadM ?? 60);
    const r = estimatePrice({ lat, lng, insideCity: true, comps: ds.comparables, model: ds.model, kelStat: findAreaStat(ds.kelurahan, k?.name ?? null, k?.kecamatan),
      kecStat: findAreaStat(ds.kecamatan, k?.kecamatan ?? null), kel: k?.name ?? null, kec: k?.kecamatan ?? null, area: area ?? 150, campus: nearestCampus(lat, lng, ds.campuses),
      mainRoad: near, feature: featureAt(fg, lat, lng), zoneStat: ds.zones?.find((z) => z.name === k?.name && z.kec === k?.kecamatan) ?? null }) as PriceEstimateResult;
    return { name, lat, lng, kel: k?.name, kec: k?.kecamatan, detected: acc.tier, reason: acc.reason, nearestUtama: acc.nearest.utama,
      shown: r.autoTiers[acc.tier], tiers: r.tiers, autoFactors: r.autoFactors, cbdFactor: r.cbdFactor, corridor: r.corridor, campusFactor: r.campusFactor, basePoint: r.basePoint,
      zone: r.zone, feature: r.feature, confidence: r.confidence, localMedian: r.localMedian, priorMedian: r.priorMedian, priorShare: r.priorShare, nUsed: r.nUsed, radiusM: r.radiusM,
      used: r.used.map((u) => ({ id: u.c.id, d: Math.round(u.distanceM), w: +u.weight.toFixed(3), ppm: u.c.ppm, pn: u.c.pn, area: u.c.area, tier: u.c.tier, exact: u.c.exact, loc: u.c.loc, kel: u.c.kel, date: u.c.date, title: u.c.title })) };
  });
  fs.writeFileSync(process.env.DETAIL_OUT as string, JSON.stringify(out, null, 1));
});
