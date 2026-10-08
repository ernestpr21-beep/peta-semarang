import { haversineMeters } from "./geo";
import type { AccessTier, AreaStat, Comparable, PriceModel } from "./model";
import { TIER_ORDER } from "./model";
import { normalizeName, roundSig } from "./utils";

export interface UsedComparable {
  c: Comparable;
  distanceM: number;
  weight: number;
}

export interface TierPrice {
  tier: AccessTier;
  point: number;
  low: number;
  high: number;
}

export interface PriceEstimateResult {
  available: true;
  /** harga titik bidang acuan (akses jalan lingkungan, luas acuan) */
  basePoint: number;
  tiers: Record<AccessTier, TierPrice>;
  /** sebaran log lokal (≈ σ) dari pembanding */
  spreadLog: number;
  nUsed: number;
  nEff: number;
  nExact: number;
  radiusM: number;
  nearestM: number;
  medianDistanceM: number;
  /** bobot prior kelurahan/kecamatan dalam % */
  priorShare: number;
  priorLevel: "kelurahan" | "kecamatan" | "kota";
  priorName: string;
  priorMedian: number;
  localMedian: number | null;
  halfWidthPct: { low: number; high: number };
  confidence: "tinggi" | "sedang" | "rendah";
  confidenceReason: string;
  used: UsedComparable[];
  area: number;
  sizeFactor: number;
  /** pengali premi jalan utama pusat kota yang dipakai di titik ini (1 = tidak ada) */
  cbdFactor: number;
  /** pengali kedekatan kampus yang dipakai (1 = tidak ada) */
  campusFactor: number;
  campus: { name: string; distanceM: number } | null;
  dateMin: string;
  dateMax: string;
}

export interface PriceUnavailable {
  available: false;
  reason: string;
}

export type PriceResult = PriceEstimateResult | PriceUnavailable;

const RADII = [400, 600, 800, 1000, 1500, 2000, 3000];
const MIN_EFF_DEFAULT = 10;
const MAX_USED = 30;
const PRIOR_STRENGTH = 3; // setara 3 pembanding
const Z50 = 0.674; // rentang 50% tengah
/** sebaran log minimum — dikalibrasi leave-one-out agar rentang 50% memuat ±50% iklan uji (lihat build_app_data.py) */
export const SPREAD_FLOOR = 0.25;

function weightedQuantile(values: number[], weights: number[], q: number) {
  const idx = values.map((_, i) => i).sort((a, b) => values[a] - values[b]);
  const total = weights.reduce((s, w) => s + w, 0);
  let acc = 0;
  for (const i of idx) {
    acc += weights[i];
    if (acc >= q * total) return values[i];
  }
  return values[idx[idx.length - 1]];
}

function monthsBetween(a: string, b: string) {
  const [ya, ma] = a.split("-").map(Number);
  const [yb, mb] = b.split("-").map(Number);
  return (yb - ya) * 12 + (mb - ma);
}

/** bobot ketepatan lokasi: pin iklan 1, pusat kelurahan 0,5; tingkat kecamatan tidak dipakai */
export function locWeight(c: Comparable) {
  if (c.loc === "kec") return 0;
  return c.exact ? 1 : 0.5;
}

/** Premi tambahan tier jalan utama di pusat kota (dari regresi; 1 bila model lama) */
export function cbdFrontageFactor(model: PriceModel, lat: number, lng: number) {
  const f = model.cbdFrontage;
  if (!f) return { factor: 1, sdLog: 0, distanceM: Infinity };
  const d = haversineMeters(lat, lng, f.center[0], f.center[1]);
  const k = Math.exp(-d / f.scaleM);
  const postSd = Math.sqrt(1 / (1 / (f.priorSD * f.priorSD) + 1 / (f.coefSE * f.coefSE)));
  return { factor: Math.exp(f.coef * k), sdLog: postSd * k, distanceM: d };
}

/** Pengali kedekatan kampus untuk jarak tertentu (1 bila > pita terjauh / tidak diketahui) */
export function campusFactor(model: PriceModel, distanceM: number | null | undefined) {
  if (!model.campus || distanceM == null || !Number.isFinite(distanceM)) return 1;
  const b = model.campus.bands.find((x) => distanceM >= x.minM && distanceM < x.maxM);
  return b ? Math.exp(b.coef) : 1;
}

/** z tingkat harga wilayah untuk kurva luas: log(median harga/m² mentah kelurahan (≥ 3 iklan) atau kecamatan / pusat) */
export function sizeLevelZ(model: PriceModel, level: number | null | undefined) {
  const sc = model.sizeCurve;
  if (!sc?.levelCenter || !level) return 0;
  return Math.max(sc.zMin ?? -Infinity, Math.min(sc.zMax ?? Infinity, Math.log(level / sc.levelCenter)));
}

export function sizeFactor(model: PriceModel, area: number, z = 0) {
  const a = Math.max(30, Math.min(50000, area));
  const ks = model.sizeCurve?.knots;
  if (!ks?.length) return Math.pow(a / model.refArea, model.sizeElasticity);
  // kurva luas: coef + slope·z, diinterpolasi linear terhadap log luas; di luar simpul terujung nilainya tetap
  const la = Math.log(a);
  const xs = ks.map((k) => Math.log(k.area));
  const at = (f: (k: { coef: number; slope?: number }) => number) => {
    if (la <= xs[0]) return f(ks[0]);
    if (la >= xs[xs.length - 1]) return f(ks[ks.length - 1]);
    let i = 0;
    while (la > xs[i + 1]) i++;
    return f(ks[i]) + ((f(ks[i + 1]) - f(ks[i])) * (la - xs[i])) / (xs[i + 1] - xs[i]);
  };
  return Math.exp(at((k) => k.coef) + at((k) => k.slope ?? 0) * z);
}

/** pengali lebar rentang menurut luas bidang (bidang kecil lebih seragam, bidang sangat luas lebih beragam) */
export function spreadScale(model: PriceModel, area: number) {
  const cls = model.spreadBySize?.classes;
  if (!cls?.length) return 1;
  const c = cls.find((k) => area >= k.minM2 && (k.maxM2 == null || area < k.maxM2));
  return c?.scale ?? 1;
}

export function findAreaStat(list: AreaStat[], name: string | null, kec?: string | null) {
  if (!name) return null;
  const n = normalizeName(name);
  const k = kec ? normalizeName(kec) : null;
  return list.find((s) => normalizeName(s.name) === n && (!k || normalizeName(s.kec) === k)) ?? list.find((s) => normalizeName(s.name) === n) ?? null;
}

export function estimatePrice(opts: {
  lat: number;
  lng: number;
  insideCity: boolean;
  comps: Comparable[];
  model: PriceModel;
  kelStat: AreaStat | null;
  kecStat: AreaStat | null;
  area?: number;
  /** kampus terdekat (jarak ke poligon); dipakai untuk faktor kedekatan kampus */
  campus?: { name: string; distanceM: number } | null;
}): PriceResult {
  const { lat, lng, comps, model } = opts;
  if (!opts.insideCity) return { available: false, reason: "Titik di luar Kota Semarang — estimasi tidak dihitung." };
  if (!comps.length) return { available: false, reason: "Data estimasi tidak tersedia." };

  // 1. Jarak ke semua pembanding (iklan yang lokasinya hanya diketahui sampai kecamatan tidak dipakai)
  const MIN_EFF = model.minEffComparables ?? MIN_EFF_DEFAULT;
  const all = comps.filter((c) => locWeight(c) > 0).map((c) => ({ c, d: haversineMeters(lat, lng, c.lat, c.lng) }));
  all.sort((a, b) => a.d - b.d);

  // 2. Radius adaptif: perbesar sampai jumlah pembanding efektif cukup
  const recency = (c: Comparable) => Math.pow(0.5, Math.max(0, monthsBetween(c.date, model.asOf)) / 12 / model.recencyHalfLifeYears);
  let radius = RADII[RADII.length - 1];
  let chosen: { c: Comparable; d: number }[] = [];
  for (const r of RADII) {
    const inR = all.filter((x) => x.d <= r);
    const eff = inR.reduce((s, x) => s + locWeight(x.c), 0);
    radius = r;
    chosen = inR;
    if (eff >= MIN_EFF) break;
  }
  chosen = chosen.slice(0, MAX_USED);

  // 3. Bobot: jarak (kernel Cauchy), ketepatan lokasi, umur iklan
  const h = Math.max(250, radius / 2.5);
  const used: UsedComparable[] = chosen.map(({ c, d }) => {
    const w = (1 / (1 + (d / h) ** 2)) * locWeight(c) * recency(c);
    return { c, distanceM: d, weight: w };
  });

  // 4. Prior wilayah: kelurahan (jika cukup data) → kecamatan → kota
  let priorLevel: PriceEstimateResult["priorLevel"] = "kota";
  let priorName = "Kota Semarang";
  let priorMedian = model.cityMedianPn;
  if (opts.kelStat && opts.kelStat.n >= 3) {
    priorLevel = "kelurahan";
    priorName = opts.kelStat.name;
    priorMedian = opts.kelStat.median;
  } else if (opts.kecStat && opts.kecStat.n >= 3) {
    priorLevel = "kecamatan";
    priorName = opts.kecStat.name;
    priorMedian = opts.kecStat.median;
  }
  const muPrior = Math.log(priorMedian);

  let muLocal: number | null = null;
  let sLocal = model.citySpreadLog;
  let nEff = 0;
  const wsum = used.reduce((s, u) => s + u.weight, 0);
  if (used.length) {
    const vals = used.map((u) => Math.log(u.c.pn));
    const ws = used.map((u) => u.weight);
    muLocal = weightedQuantile(vals, ws, 0.5);
    const dev = vals.map((v) => Math.abs(v - (muLocal as number)));
    // sebaran: bobot diratakan (akar bobot) agar 1–2 pembanding sangat dekat tidak mendominasi lebar rentang
    // (dikalibrasi leave-one-out: cakupan rentang 50% lebih dekat ke 50%, lihat analysis/compare_versions.py)
    const mad = weightedQuantile(dev, ws.map(Math.sqrt), 0.5);
    nEff = wsum ** 2 / ws.reduce((s, w) => s + w * w, 0);
    // sebaran lokal: MAD terboboti (×1.4826 ≈ σ), dicampur sebaran kota jika data sedikit
    const sRaw = Math.max(SPREAD_FLOOR, 1.4826 * mad);
    const k = Math.min(1, nEff / 6);
    sLocal = k * sRaw + (1 - k) * model.citySpreadLog;
  }

  // 5. Penyusutan (shrinkage) ke prior wilayah
  const mu = muLocal == null ? muPrior : (nEff * muLocal + PRIOR_STRENGTH * muPrior) / (nEff + PRIOR_STRENGTH);
  const priorShare = muLocal == null ? 1 : PRIOR_STRENGTH / (nEff + PRIOR_STRENGTH);
  const se = sLocal / Math.sqrt(Math.max(1, nEff + PRIOR_STRENGTH * 0.5));
  const sigma = Math.sqrt(sLocal * sLocal + se * se);

  const area = opts.area ?? model.refArea;
  // tingkat harga wilayah (median mentah kelurahan bila ≥ 3 iklan, selain itu kecamatan) — sama dengan pipeline
  const level = opts.kelStat && opts.kelStat.n >= 3 ? opts.kelStat.medianRaw : opts.kecStat?.medianRaw;
  const sf = sizeFactor(model, area, sizeLevelZ(model, level));
  // pembanding sudah dinormalisasi ke "jauh dari kampus" → kalikan kembali faktor kampus di titik ini
  const campusF = campusFactor(model, opts.campus?.distanceM);
  const basePoint = Math.exp(mu) * campusF;

  const cbd = cbdFrontageFactor(model, lat, lng);
  const ss = spreadScale(model, area);
  const tiers = {} as Record<AccessTier, TierPrice>;
  const raw = {} as Record<AccessTier, number>;
  for (const t of TIER_ORDER) {
    const ti = model.tiers[t];
    // ketidakpastian faktor akses ikut melebarkan rentang
    const sigT0 = Math.log(ti.hi / ti.lo) / (2 * 1.96);
    const sigT = t === "utama" ? Math.sqrt(sigT0 * sigT0 + cbd.sdLog * cbd.sdLog) : sigT0;
    const sig = Math.sqrt(sigma * sigma + sigT * sigT) * ss;
    const point = basePoint * ti.factor * (t === "utama" ? cbd.factor : 1) * sf;
    raw[t] = point;
    let high = point * Math.exp(Z50 * sig);
    // gang / tanpa akses: batas atas tidak melebihi titik estimasi tier di atasnya (lokasi & luas sama)
    const cap = t === "gang" || t === "tanpa" ? model.tierCaps?.[t] : undefined;
    if (cap && raw[cap.ref] != null) high = Math.max(point, Math.min(high, raw[cap.ref] * cap.mult));
    tiers[t] = {
      tier: t,
      point: roundSig(point, 2),
      low: roundSig(point * Math.exp(-Z50 * sig), 2),
      high: roundSig(high, 2),
    };
  }

  const nExact = used.filter((u) => u.c.exact).length;
  const nearestM = all[0]?.d ?? Infinity;
  const dists = used.map((u) => u.distanceM).sort((a, b) => a - b);
  const medianDistanceM = dists.length ? dists[Math.floor(dists.length / 2)] : nearestM;

  let confidence: PriceEstimateResult["confidence"] = "rendah";
  let confidenceReason = "";
  if (nEff >= 8 && medianDistanceM <= 1000 && sLocal <= 0.55) {
    confidence = "tinggi";
    confidenceReason = `${used.length} pembanding, median jarak ${Math.round(medianDistanceM)} m`;
  } else if (nEff >= 4 && medianDistanceM <= 2000) {
    confidence = "sedang";
    confidenceReason = `${used.length} pembanding dalam ${radius >= 1000 ? radius / 1000 + " km" : radius + " m"}`;
  } else {
    confidenceReason = used.length
      ? `hanya ${used.length} pembanding (radius ${radius / 1000} km); bertumpu pada median ${priorLevel}`
      : `tidak ada pembanding dekat; memakai median ${priorLevel}`;
  }

  const dates = used.map((u) => u.c.date).sort();
  const sig = sigma * ss;
  return {
    available: true,
    basePoint,
    tiers,
    spreadLog: sLocal,
    nUsed: used.length,
    nEff,
    nExact,
    radiusM: radius,
    nearestM,
    medianDistanceM,
    priorShare,
    priorLevel,
    priorName,
    priorMedian,
    localMedian: muLocal == null ? null : Math.exp(muLocal),
    halfWidthPct: { low: 1 - Math.exp(-Z50 * sig), high: Math.exp(Z50 * sig) - 1 },
    confidence,
    confidenceReason,
    used: used.sort((a, b) => a.distanceM - b.distanceM),
    area,
    sizeFactor: sf,
    cbdFactor: cbd.factor,
    campusFactor: campusF,
    campus: opts.campus ?? null,
    dateMin: dates[0] ?? "",
    dateMax: dates[dates.length - 1] ?? "",
  };
}
