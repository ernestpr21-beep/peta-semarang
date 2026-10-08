// Audit: estimasi model pada kisi (bawaan 250 m) di seluruh Kota Semarang → GRID_OUT (JSON). Hanya bila GRID_OUT di-set.
import { it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { estimatePrice, findAreaStat, type PriceEstimateResult } from "../src/lib/estimate";
import { detectAccess, nearestRoads, type Road } from "../src/lib/access";
import { findFeature, nearestCampus, type GeoCollection } from "../src/lib/geo";
import type { Dataset } from "../src/lib/model";

const PUB = path.resolve(import.meta.dirname, "../public/data");
const DS_PATH = process.env.GRID_DATASET ?? path.join(PUB, "dataset.json");

it.skipIf(!process.env.GRID_OUT)(
  "kisi estimasi",
  () => {
    const ds = JSON.parse(fs.readFileSync(DS_PATH, "utf8")) as Dataset;
    const kota = JSON.parse(fs.readFileSync(path.join(PUB, "kota.geojson"), "utf8")) as GeoCollection<{ name: string }>;
    const kel = JSON.parse(fs.readFileSync(path.join(PUB, "kelurahan.geojson"), "utf8")) as GeoCollection<{ name: string; kecamatan: string }>;
    const tiles = new Map<string, Road[]>();
    const tile = (ix: number, iy: number) => {
      const k = `${ix}_${iy}`;
      if (!tiles.has(k)) {
        const p = path.join(PUB, "roads", `${k}.json`);
        tiles.set(k, fs.existsSync(p) ? (JSON.parse(fs.readFileSync(p, "utf8")) as Road[]) : []);
      }
      return tiles.get(k)!;
    };
    const roadsAround = (lat: number, lng: number) => {
      const ix = Math.floor(lng / 0.01), iy = Math.floor(lat / 0.01);
      const out: Road[] = [];
      for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) out.push(...tile(ix + dx, iy + dy));
      return out;
    };
    const step = Number(process.env.GRID_STEP ?? 250);
    const dLat = step / 110574, dLng = step / (111320 * Math.cos((7 * Math.PI) / 180));
    let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
    const scan = (c: unknown): void => {
      if (Array.isArray(c) && typeof c[0] === "number") {
        const [x, y] = c as number[];
        minLng = Math.min(minLng, x); maxLng = Math.max(maxLng, x); minLat = Math.min(minLat, y); maxLat = Math.max(maxLat, y);
      } else if (Array.isArray(c)) c.forEach(scan);
    };
    kota.features.forEach((f) => scan((f.geometry as { coordinates: unknown }).coordinates));
    const out: Record<string, unknown>[] = [];
    for (let lat = minLat + dLat / 2; lat < maxLat; lat += dLat)
      for (let lng = minLng + dLng / 2; lng < maxLng; lng += dLng) {
        if (!findFeature(lat, lng, kota)) continue;
        const k = findFeature(lat, lng, kel)?.properties;
        const roads = roadsAround(lat, lng);
        const near = nearestRoads(lat, lng, roads);
        // kepadatan jalan: jumlah ruas jalan mobil/gang yang titiknya berada ≤ 200 m
        let nSeg = 0;
        for (const r of roads) {
          if (!(r.c === "lingkungan" || r.c === "gang" || r.c === "utama")) continue;
          for (let i = 0; i < r.g.length; i += 2) {
            const dy = (r.g[i] - lat) * 110574, dx = (r.g[i + 1] - lng) * 110500;
            if (dx * dx + dy * dy < 40000) { nSeg++; break; }
          }
        }
        const kelStat = findAreaStat(ds.kelurahan, k?.name ?? null, k?.kecamatan);
        const r = estimatePrice({
          lat, lng, insideCity: true, comps: ds.comparables, model: ds.model, kelStat, kecStat: findAreaStat(ds.kecamatan, k?.kecamatan ?? null),
          area: 150, campus: nearestCampus(lat, lng, ds.campuses),
        }) as PriceEstimateResult;
        if (!r.available) continue;
        const acc = detectAccess(lat, lng, roads);
        out.push({
          lat: +lat.toFixed(5), lng: +lng.toFixed(5), kel: k?.name ?? null, kec: k?.kecamatan ?? null,
          ling: r.tiers.lingkungan.point, lo: r.tiers.lingkungan.low, hi: r.tiers.lingkungan.high, utama: r.tiers.utama.point,
          nUsed: r.nUsed, nEff: +r.nEff.toFixed(1), radius: r.radiusM, nearestM: Math.round(r.nearestM), medDistM: Math.round(r.medianDistanceM),
          priorLevel: r.priorLevel, priorShare: +r.priorShare.toFixed(2), conf: r.confidence, localMedian: r.localMedian, kelMedian: kelStat?.median ?? null, kelN: kelStat?.n ?? 0,
          campusF: +(r.campusFactor ?? 1).toFixed(3), campusD: r.campus ? Math.round(r.campus.distanceM) : null, campusName: r.campus?.name ?? null,
          shown: r.autoTiers[acc.tier].point, shownLo: r.autoTiers[acc.tier].low, shownHi: r.autoTiers[acc.tier].high,
          tier: acc.tier, dMain: near.utama ? Math.round(near.utama.distanceM) : null, dLing: near.lingkungan ? Math.round(near.lingkungan.distanceM) : null,
          dGang: near.gang ? Math.round(near.gang.distanceM) : null, nSeg,
        });
      }
    fs.writeFileSync(process.env.GRID_OUT as string, JSON.stringify(out));
  },
  600000,
);
