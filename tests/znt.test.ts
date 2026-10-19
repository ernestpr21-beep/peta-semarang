// Batas bawah ZNT BPN (ronde 1: Kel. Jatingaleh) — harga pasar ≥ pita bawah ZNT × margin di titik baca; tidak pernah menurunkan harga.
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { estimatePrice, findAreaStat, type PriceEstimateResult } from "../src/lib/estimate";
import { detectAccess, type Road } from "../src/lib/access";
import { findFeature, nearestCampus, type GeoCollection } from "../src/lib/geo";
import type { Dataset, FeatureGrid } from "../src/lib/model";
import { featureAt } from "../src/lib/data";

const PUB = path.resolve(import.meta.dirname, "../public/data");
const ds = JSON.parse(fs.readFileSync(path.join(PUB, "dataset.json"), "utf8")) as Dataset;
const kel = JSON.parse(fs.readFileSync(path.join(PUB, "kelurahan.geojson"), "utf8")) as GeoCollection<{ name: string; kecamatan: string }>;
const fgRaw = JSON.parse(fs.readFileSync(path.join(PUB, "feature-grid.json"), "utf8")) as FeatureGrid;
const fg = { ...fgRaw, pos: new Map(fgRaw.idx.map((v, i) => [v, i] as [number, number])) };
const roadsAround = (lat: number, lng: number) => {
  const out: Road[] = [];
  for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) {
    const p = path.join(PUB, "roads", `${Math.floor(lng / 0.01) + dx}_${Math.floor(lat / 0.01) + dy}.json`);
    if (fs.existsSync(p)) out.push(...(JSON.parse(fs.readFileSync(p, "utf8")) as Road[]));
  }
  return out;
};
function at(lat: number, lng: number, withZnt = true) {
  const k = findFeature(lat, lng, kel)?.properties;
  const acc = detectAccess(lat, lng, roadsAround(lat, lng));
  const f = featureAt(fg, lat, lng);
  const model = withZnt ? ds.model : { ...ds.model, znt: undefined };
  const r = estimatePrice({ lat, lng, insideCity: true, comps: ds.comparables, model, kelStat: findAreaStat(ds.kelurahan, k?.name ?? null, k?.kecamatan),
    kecStat: findAreaStat(ds.kecamatan, k?.kecamatan ?? null), kel: k?.name ?? null, kec: k?.kecamatan ?? null, area: 150, campus: nearestCampus(lat, lng, ds.campuses),
    feature: f, shop: f?.sh ?? null, frontRoad: acc.nearest.utama ?? null, zoneStat: ds.zones?.find((z) => z.name === k?.name && z.kec === k?.kecamatan) ?? null }) as PriceEstimateResult;
  return r.autoTiers[acc.tier];
}
const z = ds.model.znt!;
describe("batas bawah ZNT", () => {
  it("ada jangkar ronde Jatingaleh", () => {
    expect(z.anchors.filter((a) => a.kel === "Jatingaleh").length).toBeGreaterThanOrEqual(15);
  });
  it("harga yang ditampilkan di setiap titik baca ≥ pita bawah ZNT", () => {
    for (const a of z.anchors) expect(at(a.lat, a.lng).point, a.id).toBeGreaterThanOrEqual(a.lo);
  });
  it("muka jalan > 20 jt (Setiabudi/Teuku Umar/Wahidin) ≥ 20 jt × margin", () => {
    for (const a of z.anchors.filter((a) => a.kind === "frontage" && a.lo >= 2e7)) expect(at(a.lat, a.lng).point, a.id).toBeGreaterThanOrEqual(a.lo * z.margin * 0.97);
  });
  it("ZNT tidak pernah menurunkan harga; jalan lingkungan di zona 2–5 jt tidak berubah", () => {
    for (const a of z.anchors) expect(at(a.lat, a.lng).point, a.id).toBeGreaterThanOrEqual(at(a.lat, a.lng, false).point);
    for (const a of z.anchors.filter((a) => a.kind === "area" && a.lo <= 2e6)) expect(at(a.lat, a.lng).point, a.id).toBe(at(a.lat, a.lng, false).point);
  });
  it("jauh dari titik baca tidak terpengaruh", () => {
    expect(at(-6.990464, 110.422918).point).toBe(at(-6.990464, 110.422918, false).point); // Simpang Lima (belum dikalibrasi)
  });
});
