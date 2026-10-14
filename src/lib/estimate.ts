import { haversineMeters } from "./geo";
import type { AccessTier, AreaStat, Comparable, KelurahanZoneStat, PriceModel } from "./model";
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
  /** harga bila tier berasal dari deteksi OSM (belum dipastikan): faktor akses terkalibrasi (model.autoAccess); sama dengan tiers bila tidak ada */
  autoTiers: Record<AccessTier, TierPrice>;
  /** faktor akses otomatis yang dipakai per tier (termasuk premi pusat kota untuk utama) */
  autoFactors: Record<AccessTier, number>;
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
  priorLevel: "sekitar" | "kelurahan" | "kecamatan" | "kota";
  /** penetapan harga berbasis kelurahan (model ≥ 2026-10-7): tingkat fallback & jumlah iklan */
  zone: KelurahanZone | null;
  /** model fitur wilayah (2026-10-8): rincian kontribusi fitur & koreksi wilayah */
  feature: FeatureBreakdown | null;
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
  /** premi koridor jalan arteri untuk tier utama (sudah termasuk di tiers.utama & autoTiers.utama); null bila tidak berlaku */
  corridor: CorridorPremium | null;
  campus: { name: string; distanceM: number } | null;
  dateMin: string;
  dateMax: string;
}

export interface FeatureBreakdown {
  /** harga dasar dari fitur saja (tanpa koreksi wilayah) */
  featureValue: number;
  kecPct: number;
  kelPct: number;
  /** koreksi lokal dalam kelurahan (2026-10-9) */
  localPct?: number;
  nKel: number;
  contributions: { key: string; label: string; pct: number }[];
}

export type ZoneLevel = "kelurahan" | "kelurahan+kecamatan" | "kecamatan" | "kota";
export interface KelurahanZone {
  level: ZoneLevel;
  kel: string | null;
  kec: string | null;
  /** iklan di kelurahan ini (berlokasi titik/kelurahan) */
  nKel: number;
  effKel: number;
  /** iklan di kecamatan (termasuk yang hanya diketahui kecamatannya) */
  nKec: number;
  kelMedian: number | null;
  kecMedian: number | null;
  /** median kecamatan setelah disusutkan ke kota */
  kecValue: number;
  /** median kelurahan setelah disusutkan ke kecamatan (= prior & nilai peta) */
  value: number;
}

const _nn = new WeakMap<Comparable, [string, string]>();
function compNames(c: Comparable): [string, string] {
  let v = _nn.get(c);
  if (!v) {
    v = [c.kel ? normalizeName(c.kel) : "", normalizeName(c.kec ?? "")];
    _nn.set(c, v);
  }
  return v;
}
export function sameKelurahan(c: Comparable, kel: string | null, kec: string | null) {
  if (!kel) return false;
  const [a, b] = compNames(c);
  return a === normalizeName(kel) && (!kec || !b || b === normalizeName(kec));
}

/** Median kelurahan bertingkat: kelurahan → (susut) kecamatan → (susut) kota. Dihitung dari pembanding yang diberikan
 *  (sehingga validasi leave-one-out/blok spasial ikut mengeluarkan iklan uji dari median). */
export function kelurahanZone(model: PriceModel, comps: Comparable[], kel: string | null, kec: string | null): KelurahanZone {
  const kp = model.kelurahanPricing!;
  const city = Math.log(model.cityMedianPn);
  const nkec = kec ? normalizeName(kec) : null;
  const kc = nkec ? comps.filter((c) => compNames(c)[1] === nkec) : [];
  const kl = kel ? comps.filter((c) => locWeight(c) > 0 && sameKelurahan(c, kel, kec)) : [];
  const kecMed = kc.length ? weightedQuantile(kc.map((c) => Math.log(c.pn)), kc.map(() => 1), 0.5) : null;
  const kecV = kecMed == null ? city : (kc.length * kecMed + kp.mKec * city) / (kc.length + kp.mKec);
  const eff = kl.reduce((s, c) => s + locWeight(c), 0);
  const kelMed = kl.length ? weightedQuantile(kl.map((c) => Math.log(c.pn)), kl.map(locWeight), 0.5) : null;
  const v = kelMed == null ? kecV : (eff * kelMed + kp.mKel * kecV) / (eff + kp.mKel);
  const level: ZoneLevel = kl.length && eff >= kp.minKel ? "kelurahan" : kl.length ? "kelurahan+kecamatan" : kc.length ? "kecamatan" : "kota";
  return {
    level,
    kel,
    kec,
    nKel: kl.length,
    effKel: eff,
    nKec: kc.length,
    kelMedian: kelMed == null ? null : Math.exp(kelMed),
    kecMedian: kecMed == null ? null : Math.exp(kecMed),
    kecValue: Math.exp(kecV),
    value: Math.exp(v),
  };
}

export interface CorridorPremium {
  key: string;
  label: string;
  factor: number;
  nEff: number;
  /** jumlah iklan muka jalan ruas ini yang ikut terboboti */
  nUsed: number;
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

/** Nama jalan ternormalisasi — sama dengan nn() di data-pipeline/corridor.py */
export function corridorKey(name: string, aliases: Record<string, string> = {}) {
  let s = name.normalize("NFKD").toLowerCase();
  s = s.replace(/\b(jalan|jl|jln|raya|ruas)\b\.?/g, " ");
  s = s
    .replace(/brigadir jenderal/g, "brigjen")
    .replace(/letnan jenderal/g, "letjen")
    .replace(/mayor jenderal/g, "mayjen")
    .replace(/kiai haji/g, "kh")
    .replace(/dokter/g, "dr");
  s = s.replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
  return aliases[s] ?? s;
}

type RoadNear = { name: string | null; distanceM: number };

function corridorOne(model: PriceModel, key: string, lat: number, lng: number) {
  const cm = model.corridor!;
  const road = cm.roads[key];
  if (!road) return null;
  const vals: number[] = [];
  const ws: number[] = [];
  for (const [a, b, v] of road.pts) {
    const w = Math.exp(-0.5 * (haversineMeters(lat, lng, a, b) / cm.bwM) ** 2);
    if (w > cm.minWeight) {
      vals.push(v);
      ws.push(w);
    }
  }
  if (!ws.length) return null;
  const tot = ws.reduce((s, w) => s + w, 0);
  const nEff = tot ** 2 / ws.reduce((s, w) => s + w * w, 0);
  return { key, label: road.label, prem: (nEff * weightedQuantile(vals, ws, 0.5)) / (nEff + cm.k), nEff, nUsed: ws.length };
}

/**
 * Premi koridor jalan arteri di titik (lat, lng). `roads` = jalan utama bernama di dekat titik (atau satu jalan utama terdekat).
 * Model 2026-10-6 (blend): semua ruas koridor ≤ maxRoadM dipakai, premi digabung berbobot nEff — di persimpangan, ruas dengan
 * bukti sedikit tidak menimpa ruas arteri yang buktinya banyak. Tanpa blend: hanya ruas terdekat.
 */
export function corridorPremium(model: PriceModel, lat: number, lng: number, roads?: RoadNear | RoadNear[] | null): CorridorPremium | null {
  const cm = model.corridor;
  if (!cm || !roads) return null;
  let list = (Array.isArray(roads) ? roads : [roads]).filter((r) => r.name && r.distanceM <= cm.maxRoadM).sort((a, b) => a.distanceM - b.distanceM);
  if (!cm.blend) list = list.slice(0, 1);
  const parts = [...new Set(list.map((r) => corridorKey(r.name as string, cm.aliases)))]
    .map((k) => corridorOne(model, k, lat, lng))
    .filter((x): x is NonNullable<typeof x> => !!x);
  if (!parts.length) return null;
  const nEff = parts.reduce((s, p) => s + p.nEff, 0);
  const prem = parts.reduce((s, p) => s + p.prem * p.nEff, 0) / nEff;
  return {
    key: parts.map((p) => p.key).join("+"),
    label: parts.map((p) => p.label).join(" / "),
    factor: Math.exp(prem),
    nEff,
    nUsed: parts.reduce((s, p) => s + p.nUsed, 0),
  };
}

/** Premi muka jalan 2026-10-9: kelas jalan + toko sepanjang jalan + efek ruas bernama (disusutkan). Hanya tier utama. */
export function frontagePremium(model: PriceModel, road: { name: string | null; highway: string; distanceM: number } | null | undefined, shop: number | null | undefined): CorridorPremium | null {
  const fm = model.frontage;
  if (!fm || !road || road.distanceM > fm.maxRoadM) return null;
  const cls = fm.classOf[road.highway] ?? "lain";
  const key = road.name ? corridorKey(road.name, fm.aliases) : null;
  const r = key ? fm.roads[key] : undefined;
  const prem = (fm.cls[cls] ?? 0) + (cls === "arteri" ? fm.shopCoef * ((shop ?? fm.shopRef) - fm.shopRef) : 0) + (r?.u ?? 0);
  return { key: r ? (key as string) : cls, label: r?.label ?? road.name ?? fm.clsLabel[cls] ?? "jalan utama", factor: Math.exp(prem), nEff: r?.n ?? 0, nUsed: r?.n ?? 0 };
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
  /** nama kelurahan & kecamatan titik (point-in-polygon) — dipakai bila model berbasis kelurahan */
  kel?: string | null;
  kec?: string | null;
  /** validasi: log harga dasar dari luar (mis. prediksi luar-lipatan model fitur) */
  baseLogOverride?: number;
  /** model fitur: nilai sel grid 150 m di titik (log F & kontribusi kelompok fitur, log) */
  feature?: { f: number; c: number[]; s?: number[]; sh?: number } | null;
  /** statistik zona kelurahan titik (dataset.zones) */
  zoneStat?: KelurahanZoneStat | null;
  area?: number;
  /** kampus terdekat (jarak ke poligon); dipakai untuk faktor kedekatan kampus */
  campus?: { name: string; distanceM: number } | null;
  /** jalan utama OSM bernama di dekat titik (nama & jarak; satu atau beberapa) — untuk premi koridor jalan arteri */
  mainRoad?: RoadNear | RoadNear[] | null;
  /** 2026-10-9: jalan utama terdekat (kelas OSM) & intensitas toko 250 m — untuk premi muka jalan */
  frontRoad?: { name: string | null; highway: string; distanceM: number } | null;
  shop?: number | null;
  /** audit: log premi muka jalan luar-lipatan (menggantikan perhitungan premi) */
  corridorLogOverride?: number | null;
}): PriceResult {
  const { lat, lng, comps, model } = opts;
  if (!opts.insideCity) return { available: false, reason: "Titik di luar Kota Semarang — estimasi tidak dihitung." };
  if (!comps.length) return { available: false, reason: "Data estimasi tidak tersedia." };

  // 1. Jarak ke semua pembanding (iklan yang lokasinya hanya diketahui sampai kecamatan tidak dipakai)
  const MIN_EFF = model.minEffComparables ?? MIN_EFF_DEFAULT;
  const kp = model.kelurahanPricing;
  const kelName = opts.kel ?? opts.kelStat?.name ?? null;
  const kecName = opts.kec ?? opts.kecStat?.name ?? null;
  // model berbasis kelurahan: pembanding HANYA dari kelurahan yang sama (tidak meminjam dari kelurahan tetangga)
  const all = comps.filter((c) => locWeight(c) > 0 && (!kp || sameKelurahan(c, kelName, kecName))).map((c) => ({ c, d: haversineMeters(lat, lng, c.lat, c.lng) }));
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
  const sp = kp ? undefined : model.smoothPrior;
  const spComps = sp ? all.filter((x) => x.d <= sp.maxM) : [];
  const zone = kp ? kelurahanZone(model, comps, kelName, kecName) : null;
  if (zone) {
    priorLevel = zone.level === "kota" ? "kota" : zone.level === "kecamatan" ? "kecamatan" : "kelurahan";
    priorName = zone.level === "kecamatan" || zone.level === "kota" ? (zone.level === "kota" ? "Kota Semarang" : zone.kec ?? "") : zone.kel ?? "";
    priorMedian = zone.value;
  } else if (sp && spComps.length >= sp.minN) {
    // prior halus: median berbobot jarak (Gauss) — tidak melompat di batas kelurahan
    priorLevel = "sekitar";
    priorName = `pembanding ≤ ${sp.maxM / 1000} km`;
    priorMedian = Math.exp(
      weightedQuantile(
        spComps.map((x) => Math.log(x.c.pn)),
        spComps.map((x) => Math.exp(-0.5 * (x.d / sp.bwM) ** 2) * locWeight(x.c)),
        0.5,
      ),
    );
  } else if (opts.kelStat && opts.kelStat.n >= 3) {
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
  // kelurahan dengan data tipis: median lokal (sedikit iklan) tidak boleh mengalahkan median zona yang sudah disusutkan
  const PS = zone && zone.level !== "kelurahan" && kp?.weakLocalStrength ? Math.max(kp.weakLocalStrength, kp.localStrength ?? PRIOR_STRENGTH) : (kp?.localStrength ?? PRIOR_STRENGTH);
  // model fitur wilayah (2026-10-8): harga dasar dari karakteristik lokasi + koreksi kecamatan/kelurahan; pembanding hanya ditampilkan
  const fp = model.featurePricing;
  const zs = fp ? opts.zoneStat ?? null : null;
  let feature: FeatureBreakdown | null = null;
  let muFeat: number | null = null;
  let localAdj = 0;
  if (fp && zs) {
    const fLog = opts.feature?.f ?? Math.log(zs.featureValue ?? zs.value);
    muFeat = fLog + (zs.kecOff ?? 0) + (zs.kelOff ?? 0);
    // 2026-10-9: koreksi lokal dalam kelurahan dari residu iklan titik terdekat di kelurahan yang sama (disusutkan)
    const lc = fp.local;
    if (lc && opts.kel) {
      const near = opts.comps
        .filter((c) => c.fr != null && c.kel === opts.kel && c.kec === opts.kec)
        .map((c) => ({ d: haversineMeters(lat, lng, c.lat, c.lng), v: (c.fr as number) - (zs.kecOff ?? 0) - (zs.kelOff ?? 0) }))
        .sort((a, b) => a.d - b.d)
        .slice(0, lc.k);
      if (near.length) {
        const ws = near.map((x) => 1 / (1 + (x.d / lc.bwM) ** 2));
        const tot = ws.reduce((a, b) => a + b, 0);
        const ne = (tot * tot) / ws.reduce((a, b) => a + b * b, 0);
        localAdj = (weightedQuantile(near.map((x) => x.v), ws, 0.5) * ne) / (ne + lc.mLoc);
        muFeat += localAdj;
      }
    }
    sLocal = zs.sdLog ?? fp.cityResidSd;
    const contrib = opts.feature?.c ?? zs.contrib ?? [];
    const side = opts.feature?.s ?? zs.side;
    feature = {
      featureValue: Math.exp(fLog),
      kecPct: Math.exp(zs.kecOff ?? 0) - 1,
      kelPct: Math.exp(zs.kelOff ?? 0) - 1,
      localPct: Math.exp(localAdj) - 1,
      nKel: zs.n,
      contributions: fp.groups
        .map((g, i) => ({ key: g.key, label: (side ? side[i] ?? 1 : (contrib[i] ?? 0)) >= 0 ? g.pos : g.neg, pct: Math.exp(contrib[i] ?? 0) - 1 }))
        .filter((x) => Math.abs(x.pct) >= 0.02)
        .sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct)),
    };
  }
  const mu = opts.baseLogOverride ?? muFeat ?? (muLocal == null ? muPrior : (nEff * muLocal + PS * muPrior) / (nEff + PS));
  const priorShare = muFeat != null ? 1 : muLocal == null ? 1 : PS / (nEff + PS);
  const se = muFeat != null ? sLocal / Math.sqrt(Math.max(1, (zs?.effKel ?? 0) + 5)) : sLocal / Math.sqrt(Math.max(1, nEff + PS * 0.5));
  const sigma = Math.sqrt(sLocal * sLocal + se * se);

  const area = opts.area ?? model.refArea;
  // tingkat harga wilayah (median mentah kelurahan bila ≥ 3 iklan, selain itu kecamatan) — sama dengan pipeline
  const level = opts.kelStat && opts.kelStat.n >= 3 ? opts.kelStat.medianRaw : opts.kecStat?.medianRaw;
  const sf = sizeFactor(model, area, sizeLevelZ(model, level));
  // pembanding sudah dinormalisasi ke "jauh dari kampus" → kalikan kembali faktor kampus di titik ini
  const campusF = campusFactor(model, opts.campus?.distanceM);
  const basePoint = Math.exp(mu) * campusF;

  const cbd = cbdFrontageFactor(model, lat, lng);
  const corridor =
    opts.corridorLogOverride != null
      ? { key: "audit", label: "", factor: Math.exp(opts.corridorLogOverride), nEff: 0, nUsed: 0 }
      : model.frontage
        ? frontagePremium(model, opts.frontRoad, opts.shop)
        : corridorPremium(model, lat, lng, opts.mainRoad);
  const corrF = corridor?.factor ?? 1;
  const ss = spreadScale(model, area);
  const tiers = {} as Record<AccessTier, TierPrice>;
  const raw = {} as Record<AccessTier, number>;
  for (const t of TIER_ORDER) {
    const ti = model.tiers[t];
    // ketidakpastian faktor akses ikut melebarkan rentang
    const sigT0 = Math.log(ti.hi / ti.lo) / (2 * 1.96);
    const sigT = t === "utama" ? Math.sqrt(sigT0 * sigT0 + cbd.sdLog * cbd.sdLog) : sigT0;
    const sig = Math.sqrt(sigma * sigma + sigT * sigT) * ss;
    const point = basePoint * ti.factor * (t === "utama" ? cbd.factor * corrF : 1) * sf;
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

  // tier hasil deteksi OSM: faktor terkalibrasi + σ tambahan (kondisi akses sebenarnya belum diketahui)
  const aa = model.autoAccess;
  const autoTiers = {} as Record<AccessTier, TierPrice>;
  const autoFactors = {} as Record<AccessTier, number>;
  for (const t of TIER_ORDER) {
    if (!aa) {
      autoTiers[t] = tiers[t];
      autoFactors[t] = model.tiers[t].factor * (t === "utama" ? cbd.factor * corrF : 1);
      continue;
    }
    const f = aa.factors[t] * (t === "utama" ? Math.pow(cbd.factor, aa.cbdScale) * corrF : 1);
    const sig = Math.sqrt(sigma * sigma + aa.sdLog * aa.sdLog) * ss;
    const point = basePoint * f * sf;
    autoFactors[t] = f;
    autoTiers[t] = { tier: t, point: roundSig(point, 2), low: roundSig(point * Math.exp(-Z50 * sig), 2), high: roundSig(point * Math.exp(Z50 * sig), 2) };
  }

  const nExact = used.filter((u) => u.c.exact).length;
  const nearestM = all[0]?.d ?? Infinity;
  const dists = used.map((u) => u.distanceM).sort((a, b) => a - b);
  const medianDistanceM = dists.length ? dists[Math.floor(dists.length / 2)] : nearestM;

  let confidence: PriceEstimateResult["confidence"] = "rendah";
  let confidenceReason = "";
  if (feature && zs) {
    confidence = zs.n >= 10 ? "tinggi" : zs.n > 0 ? "sedang" : "rendah";
    confidenceReason =
      zs.n > 0
        ? `model fitur wilayah + koreksi dari ${zs.n} iklan di Kel. ${zs.name}`
        : `belum ada iklan di Kel. ${zs.name}; harga dari karakteristik wilayahnya (model fitur) + koreksi Kec. ${zs.kec}`;
  } else if (zone && zone.level !== "kelurahan") {
    confidenceReason =
      zone.level === "kelurahan+kecamatan"
        ? `hanya ${zone.nKel} iklan di Kel. ${zone.kel}; disusutkan ke median Kec. ${zone.kec}`
        : zone.level === "kecamatan"
          ? `belum ada iklan di ${zone.kel ? "Kel. " + zone.kel : "kelurahan ini"}; memakai median Kec. ${zone.kec}`
          : "tidak ada iklan di kelurahan maupun kecamatan; memakai median kota";
  } else if (nEff >= 8 && medianDistanceM <= 1000 && sLocal <= 0.55) {
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
    autoTiers,
    autoFactors,
    spreadLog: sLocal,
    nUsed: used.length,
    nEff,
    nExact,
    radiusM: radius,
    nearestM,
    medianDistanceM,
    priorShare,
    priorLevel,
    zone,
    feature,
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
    corridor,
    campus: opts.campus ?? null,
    dateMin: dates[0] ?? "",
    dateMax: dates[dates.length - 1] ?? "",
  };
}
