// Audit: harga yang TAMPIL (tier hasil deteksi OSM, 150 m²) di titik bernama — dataset lama (CMP_OLD) vs dataset kini → CMP_OUT.
import { it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { estimatePrice, findAreaStat, type PriceEstimateResult } from "../src/lib/estimate";
import { detectAccess, type Road } from "../src/lib/access";
import { findFeature, nearestCampus, type GeoCollection } from "../src/lib/geo";
import type { Dataset } from "../src/lib/model";

const PUB = path.resolve(import.meta.dirname, "../public/data");
const PLACES: [string, number, number, number?][] = JSON.parse(process.env.CMP_POINTS ? fs.readFileSync(process.env.CMP_POINTS, "utf8") : "[]");
it.skipIf(!process.env.CMP_OUT)("bandingkan titik", () => {
  const load = (p: string) => JSON.parse(fs.readFileSync(p, "utf8")) as Dataset;
  const dsOld = load(process.env.CMP_OLD as string), dsNew = load(path.join(PUB, "dataset.json"));
  const kota = JSON.parse(fs.readFileSync(path.join(PUB, "kota.geojson"), "utf8")) as GeoCollection<{ name: string }>;
  const kel = JSON.parse(fs.readFileSync(path.join(PUB, "kelurahan.geojson"), "utf8")) as GeoCollection<{ name: string; kecamatan: string }>;
  const roadsAround = (lat: number, lng: number) => {
    const out: Road[] = [];
    for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) {
      const p = path.join(PUB, "roads", `${Math.floor(lng / 0.01) + dx}_${Math.floor(lat / 0.01) + dy}.json`);
      if (fs.existsSync(p)) out.push(...(JSON.parse(fs.readFileSync(p, "utf8")) as Road[]));
    }
    return out;
  };
  const est = (ds: Dataset, lat: number, lng: number, area: number) => {
    const k = findFeature(lat, lng, kel)?.properties;
    return estimatePrice({ lat, lng, insideCity: Boolean(findFeature(lat, lng, kota)), comps: ds.comparables, model: ds.model,
      kelStat: findAreaStat(ds.kelurahan, k?.name ?? null, k?.kecamatan), kecStat: findAreaStat(ds.kecamatan, k?.kecamatan ?? null), area, campus: nearestCampus(lat, lng, ds.campuses) }) as PriceEstimateResult;
  };
  const out = PLACES.map(([name, lat, lng, area]) => {
    const a = area ?? 150;
    const acc = detectAccess(lat, lng, roadsAround(lat, lng));
    const o = est(dsOld, lat, lng, a), n = est(dsNew, lat, lng, a);
    const t = acc.tier;
    const used = n.used.filter((u) => u.distanceM <= 1000);
    const med = used.length ? used.map((u) => u.c.ppm).sort((x, y) => x - y)[Math.floor(used.length / 2)] : null;
    return { name, lat, lng, area: a, kel: findFeature(lat, lng, kel)?.properties.name, detected: t, reason: acc.reason,
      oldShown: o.tiers[t], newShown: n.autoTiers[t], newManualLing: n.tiers.lingkungan, newManualDetected: n.tiers[t], oldLing: o.tiers.lingkungan,
      compsWithin1km: used.length, compsMedianRawPpm: med, nUsed: n.nUsed, radiusM: n.radiusM, priorOld: o.priorLevel, priorNew: n.priorLevel };
  });
  fs.writeFileSync(process.env.CMP_OUT as string, JSON.stringify(out, null, 1));
});
