// Audit 2026-10-6: validasi bersama beberapa versi model pada himpunan uji yang sama (leave-one-out & validasi silang blok spasial).
// Hanya bila VAL_EVAL, VAL_VARIANTS (json: [{name, dataset, k?, bwM?}]) dan VAL_OUT di-set.
import { it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { estimatePrice, findAreaStat, type PriceEstimateResult } from "../src/lib/estimate";
import { detectAccess, namedMainRoadsWithin, type Road } from "../src/lib/access";
import { nearestCampus, type GeoCollection, findFeature } from "../src/lib/geo";
import type { Dataset, PriceModel } from "../src/lib/model";

const PUB = path.resolve(import.meta.dirname, "../public/data");
type Ev = { id: string; lat: number; lng: number; area: number; ppm: number; date: string; src: string; kel: string; kec: string; outlier: boolean; txtTier: string; corr: string | null; corrHow: string | null; proj: [number, number] | null; group: string[] };
it.skipIf(!process.env.VAL_OUT)("validasi bersama", () => {
  const ev = JSON.parse(fs.readFileSync(process.env.VAL_EVAL as string, "utf8")) as Ev[];
  const variants = JSON.parse(process.env.VAL_VARIANTS as string) as { name: string; dataset: string; k?: number; bwM?: number; noCorridor?: boolean }[];
  const kel = JSON.parse(fs.readFileSync(path.join(PUB, "kelurahan.geojson"), "utf8")) as GeoCollection<{ name: string; kecamatan: string }>;
  const tiles = new Map<string, Road[]>();
  const roadsAround = (lat: number, lng: number) => {
    const out: Road[] = [];
    for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) {
      const k = `${Math.floor(lng / 0.01) + dx}_${Math.floor(lat / 0.01) + dy}`;
      if (!tiles.has(k)) { const p = path.join(PUB, "roads", `${k}.json`); tiles.set(k, fs.existsSync(p) ? (JSON.parse(fs.readFileSync(p, "utf8")) as Road[]) : []); }
      out.push(...tiles.get(k)!);
    }
    return out;
  };
  const KX = 110500, KY = 110574;
  const fold = (lat: number, lng: number) => {
    const bx = Math.floor((lng * KX) / 2000), by = Math.floor((lat * KY) / 2000);
    let h = (bx * 73856093) ^ (by * 19349663);
    h = Math.imul(h ^ (h >>> 13), 0x5bd1e995);
    return Math.abs(h ^ (h >>> 15)) % 5;
  };
  // fitur titik (tidak bergantung versi)
  const feat = ev.map((e) => {
    const rd = roadsAround(e.lat, e.lng);
    const acc = detectAccess(e.lat, e.lng, rd);
    const u = acc.nearest.utama;
    const k = findFeature(e.lat, e.lng, kel)?.properties;
    let atRoad = null as null | { tier: typeof acc.tier; near: ReturnType<typeof namedMainRoadsWithin>; nearest: { name: string | null; distanceM: number }[] };
    if (e.proj) {
      const rd2 = roadsAround(e.proj[0], e.proj[1]);
      const a2 = detectAccess(e.proj[0], e.proj[1], rd2);
      const u2 = a2.nearest.utama;
      atRoad = { tier: a2.tier, near: namedMainRoadsWithin(e.proj[0], e.proj[1], rd2, 60), nearest: u2 ? [{ name: u2.name, distanceM: u2.distanceM }] : [] };
    }
    return { atRoad, tier: acc.tier, near: namedMainRoadsWithin(e.lat, e.lng, rd, 60), nearest: u ? [{ name: u.name, distanceM: u.distanceM }] : [], kelName: k?.name ?? null, kecName: k?.kecamatan ?? null,
      campus: null as ReturnType<typeof nearestCampus>, fold: fold(e.lat, e.lng) };
  });
  const result: Record<string, unknown> = {};
  for (const v of variants) {
    const ds = JSON.parse(fs.readFileSync(v.dataset, "utf8")) as Dataset;
    const m0 = ds.model;
    const months = (d: string) => { const [y, mo] = d.split("-").map(Number); const [ya, ma] = m0.asOf.split("-").map(Number); return Math.max(0, ((ya - y) * 12 + (ma - mo)) / 12); };
    const compFold = ds.comparables.map((c) => fold(c.lat, c.lng));
    for (const mode of ["loo", "cv"] as const) {
      const rows = ev.map((e, i) => {
        const f = feat[i];
        const g = new Set(e.group.concat([e.id]));
        const comps = ds.comparables.filter((c, j) => !g.has(c.id) && (mode === "loo" || compFold[j] !== f.fold));
        let model: PriceModel = m0;
        if (m0.corridor && !v.noCorridor) {
          const roads: NonNullable<PriceModel["corridor"]>["roads"] = {};
          for (const [k, r] of Object.entries(m0.corridor.roads)) {
            const keep = r.pts.map((p, j) => !g.has(r.ids?.[j] ?? "") && (mode === "loo" || fold(p[0], p[1]) !== f.fold));
            const pts = r.pts.filter((_, j) => keep[j]);
            if (pts.length) roads[k] = { ...r, pts };
          }
          model = { ...m0, corridor: { ...m0.corridor, roads, k: v.k ?? m0.corridor.k, bwM: v.bwM ?? m0.corridor.bwM } };
        } else if (v.noCorridor) model = { ...m0, corridor: undefined };
        if (!f.campus) f.campus = nearestCampus(e.lat, e.lng, ds.campuses);
        const r = estimatePrice({ lat: e.lat, lng: e.lng, insideCity: true, comps, model, kelStat: findAreaStat(ds.kelurahan, f.kelName, f.kecName), kecStat: findAreaStat(ds.kecamatan, f.kecName),
          area: e.area, campus: f.campus, mainRoad: model.corridor?.blend ? f.near : f.nearest }) as PriceEstimateResult;
        if (!r.available) return null;
        const y = Math.log(e.ppm * Math.exp(m0.trendPerYear * months(e.date)) * (m0.sourceAdj?.[e.src as "lamudi" | "pinhome"] ?? 1));
        const sh = r.autoTiers[f.tier];
        let eRoadAuto: number | null = null, eRoadMan: number | null = null;
        if (f.atRoad && e.proj) {
          const r2 = estimatePrice({ lat: e.proj[0], lng: e.proj[1], insideCity: true, comps, model, kelStat: findAreaStat(ds.kelurahan, f.kelName, f.kecName), kecStat: findAreaStat(ds.kecamatan, f.kecName),
            area: e.area, campus: f.campus, mainRoad: model.corridor?.blend ? f.atRoad.near : f.atRoad.nearest }) as PriceEstimateResult;
          eRoadAuto = Math.log(r2.autoTiers[f.atRoad.tier].point) - y;
          eRoadMan = Math.log(r2.tiers.utama.point) - y;
        }
        return { eRoadAuto, eRoadMan, id: e.id, eShown: Math.log(sh.point) - y, cov: y >= Math.log(sh.low) && y <= Math.log(sh.high), eManU: Math.log(r.tiers.utama.point) - y, eAutoU: Math.log(r.autoTiers.utama.point) - y,
          corr: r.corridor?.factor ?? 1, tier: f.tier };
      });
      result[`${v.name}|${mode}`] = rows;
    }
  }
  fs.writeFileSync(process.env.VAL_OUT as string, JSON.stringify(result));
}, 3_600_000);
