import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { estimatePrice, findAreaStat, type PriceEstimateResult } from "../src/lib/estimate";
import { detectAccess, type Road } from "../src/lib/access";
import { findFeature, type GeoCollection } from "../src/lib/geo";
import { computeLocationScore, SCORE_SEARCH_RADIUS } from "../src/lib/score";
import { facilitiesNear, type FacilityRaw } from "../src/lib/facilities";
import type { Dataset } from "../src/lib/model";

const PUB = path.resolve(import.meta.dirname, "../public/data");
const ds = JSON.parse(fs.readFileSync(path.join(PUB, "dataset.json"), "utf8")) as Dataset;
const kota = JSON.parse(fs.readFileSync(path.join(PUB, "kota.geojson"), "utf8")) as GeoCollection<{ name: string }>;
const kel = JSON.parse(fs.readFileSync(path.join(PUB, "kelurahan.geojson"), "utf8")) as GeoCollection<{ name: string; kecamatan: string }>;
const fac = JSON.parse(fs.readFileSync(path.join(PUB, "facilities.json"), "utf8")) as { rows: FacilityRaw[] };

function roadsAround(lat: number, lng: number): Road[] {
  const ix = Math.floor(lng / 0.01);
  const iy = Math.floor(lat / 0.01);
  const out: Road[] = [];
  for (const dx of [-1, 0, 1])
    for (const dy of [-1, 0, 1]) {
      const p = path.join(PUB, "roads", `${ix + dx}_${iy + dy}.json`);
      if (fs.existsSync(p)) out.push(...(JSON.parse(fs.readFileSync(p, "utf8")) as Road[]));
    }
  return out;
}

export function estimateAt(lat: number, lng: number, area = 150) {
  const k = findFeature(lat, lng, kel)?.properties;
  const r = estimatePrice({
    lat,
    lng,
    insideCity: Boolean(findFeature(lat, lng, kota)),
    comps: ds.comparables,
    model: ds.model,
    kelStat: findAreaStat(ds.kelurahan, k?.name ?? null, k?.kecamatan),
    kecStat: findAreaStat(ds.kecamatan, k?.kecamatan ?? null),
    area,
  });
  return { r, k, access: detectAccess(lat, lng, roadsAround(lat, lng)) };
}

const PLACES = {
  simpangLima: [-6.990464, 110.422918],
  tembalang: [-7.0535, 110.4386], // sekitar Undip Tembalang
  gunungpati: [-7.0886, 110.3734], // Gunungpati (pinggiran selatan-barat)
  tugu: [-6.9706, 110.3216], // Kec. Tugu (Mangkang)
} as const;

describe("estimasi harga per lokasi", () => {
  const res = Object.fromEntries(Object.entries(PLACES).map(([k, [lat, lng]]) => [k, estimateAt(lat, lng)]));
  it("semua lokasi di dalam kota & punya estimasi", () => {
    for (const [k, v] of Object.entries(res)) expect(v.r.available, k).toBe(true);
  });
  const ling = (k: string) => (res[k].r as PriceEstimateResult).tiers.lingkungan.point;
  it("Simpang Lima jauh lebih mahal daripada Tembalang, Gunungpati, Tugu", () => {
    expect(ling("simpangLima")).toBeGreaterThan(ling("tembalang") * 1.5);
    expect(ling("simpangLima")).toBeGreaterThan(ling("gunungpati") * 2);
    expect(ling("simpangLima")).toBeGreaterThan(ling("tugu") * 1.5);
  });
  it("Tembalang lebih mahal daripada Gunungpati", () => {
    expect(ling("tembalang")).toBeGreaterThan(ling("gunungpati"));
  });
  it("keempat lokasi menghasilkan angka berbeda (bukan satu median kota)", () => {
    const vals = Object.keys(PLACES).map(ling);
    expect(new Set(vals).size).toBe(vals.length);
  });
  it("rentang mengikuti data (tidak selalu ±20%)", () => {
    const widths = Object.keys(PLACES).map((k) => {
      const t = (res[k].r as PriceEstimateResult).tiers.lingkungan;
      return Math.round((t.high / t.low) * 100);
    });
    expect(new Set(widths).size).toBeGreaterThan(1);
  });
  it("menampilkan jumlah & jarak pembanding", () => {
    const r = res.tembalang.r as PriceEstimateResult;
    expect(r.nUsed).toBeGreaterThanOrEqual(8);
    expect(r.medianDistanceM).toBeGreaterThan(0);
    expect(r.used[0].distanceM).toBeLessThanOrEqual(r.used[r.used.length - 1].distanceM);
  });
});

describe("akses jalan vs tanpa akses", () => {
  it("urutan harga: jalan utama > lingkungan > gang > tanpa akses", () => {
    const r = estimateAt(...PLACES.tembalang).r as PriceEstimateResult;
    expect(r.tiers.utama.point).toBeGreaterThan(r.tiers.lingkungan.point);
    expect(r.tiers.lingkungan.point).toBeGreaterThan(r.tiers.gang.point);
    expect(r.tiers.gang.point).toBeGreaterThan(r.tiers.tanpa.point);
    expect(r.tiers.tanpa.point / r.tiers.lingkungan.point).toBeLessThan(0.75);
  });
  it("deteksi OSM: titik di Jl. Pahlawan = jalan utama", () => {
    expect(estimateAt(-6.99575, 110.4202).access.tier).toBe("utama");
  });
  it("deteksi OSM: titik di tengah sawah/kebun jauh dari jalan = tanpa akses", () => {
    const a = detectAccess(-7.0, 110.4, [{ c: "lingkungan", hw: "residential", g: [-7.002, 110.4, -7.002, 110.41] }]);
    expect(a.tier).toBe("tanpa");
    const b = detectAccess(-7.0, 110.4, [{ c: "lingkungan", hw: "residential", g: [-7.0001, 110.399, -7.0001, 110.41] }]);
    expect(b.tier).toBe("lingkungan");
    const c = detectAccess(-7.0, 110.4, [{ c: "setapak", hw: "footway", g: [-7.0001, 110.399, -7.0001, 110.41] }]);
    expect(c.tier).toBe("gang");
  });
});

describe("skor lokasi", () => {
  it("tanpa fasilitas → skor fasilitas 0 (bug lama: 100)", () => {
    const s = computeLocationScore(-7.0, 110.4, []);
    for (const p of s.parts.filter((p) => p.id !== "pusat")) expect(p.score).toBe(0);
    expect(s.total).toBeLessThanOrEqual(20);
  });
  it("Simpang Lima skornya tinggi, pinggiran lebih rendah", () => {
    const sc = (lat: number, lng: number) => computeLocationScore(lat, lng, facilitiesNear(fac.rows, lat, lng, SCORE_SEARCH_RADIUS)).total;
    expect(sc(...PLACES.simpangLima)).toBeGreaterThan(75);
    expect(sc(...PLACES.simpangLima)).toBeGreaterThan(sc(...PLACES.gunungpati));
  });
});

describe("label & aturan", () => {
  it("tidak pernah menyebut NJOP sebagai nama harga", async () => {
    const { PRICE_LABEL } = await import("../src/lib/constants");
    expect(PRICE_LABEL.toLowerCase()).toContain("estimasi kisaran harga pasar");
    expect(PRICE_LABEL.toLowerCase()).not.toContain("njop");
  });
});
