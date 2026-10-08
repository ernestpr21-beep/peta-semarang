// Audit: deteksi akses OSM (aturan aplikasi) di titik iklan → ACCESS_OUT (JSON). Hanya bila ACCESS_IN & ACCESS_OUT di-set.
import { it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { detectAccess, type Road } from "../src/lib/access";

const PUB = path.resolve(import.meta.dirname, "../public/data");
it.skipIf(!process.env.ACCESS_OUT)("akses di titik iklan", () => {
  const pts = JSON.parse(fs.readFileSync(process.env.ACCESS_IN as string, "utf8")) as { id: string; lat: number; lng: number }[];
  const tiles = new Map<string, Road[]>();
  const tile = (ix: number, iy: number) => {
    const k = `${ix}_${iy}`;
    if (!tiles.has(k)) {
      const p = path.join(PUB, "roads", `${k}.json`);
      tiles.set(k, fs.existsSync(p) ? (JSON.parse(fs.readFileSync(p, "utf8")) as Road[]) : []);
    }
    return tiles.get(k)!;
  };
  const out = pts.map(({ id, lat, lng }) => {
    const ix = Math.floor(lng / 0.01), iy = Math.floor(lat / 0.01);
    const roads: Road[] = [];
    for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) roads.push(...tile(ix + dx, iy + dy));
    const a = detectAccess(lat, lng, roads);
    const n = a.nearest;
    const r = (x?: { distanceM: number }) => (x ? Math.round(x.distanceM) : null);
    let why = a.tier as string;
    if (a.tier === "gang") why = a.reason.includes("lebar tercatat") ? "gang-lebar<3" : a.reason.includes("bidang dalam") ? "gang-dalam(30-60m)" : "gang-terpetakan";
    return { id, tier: a.tier, why, dMain: r(n.utama), dLing: r(n.lingkungan), dGang: r(n.gang), dPath: r(n.setapak), dDrive: r(a.nearestDrivable ?? undefined) };
  });
  fs.writeFileSync(process.env.ACCESS_OUT as string, JSON.stringify(out));
}, 600000);
