/** Tipe data bersama untuk dataset harga (public/data/*.json). */
export type AccessTier = "utama" | "lingkungan" | "gang" | "tanpa";
export const TIER_ORDER: AccessTier[] = ["utama", "lingkungan", "gang", "tanpa"];

export interface Comparable {
  id: string;
  lat: number;
  lng: number;
  /** Harga penawaran asli per m² (Rp) */
  ppm: number;
  /** Harga per m² yang sudah dinormalisasi ke bidang acuan (luas acuan, akses jalan lingkungan, residensial) */
  pn: number;
  tier: AccessTier | null;
  tierSrc: "teks" | "osm" | null;
  area: number;
  /** YYYY-MM tanggal iklan dibuat/diperbarui */
  date: string;
  src: string;
  /** null bila lokasi iklan hanya diketahui sampai kecamatan */
  kel: string | null;
  kec: string;
  /** true = koordinat iklan spesifik (pin); false = perkiraan */
  exact: boolean;
  /** tingkat ketepatan lokasi: titik (pin iklan), kel (pusat kelurahan teks), kec (hanya kecamatan — tidak dipakai sebagai pembanding titik) */
  loc?: "titik" | "kel" | "kec";
  url: string;
  title: string;
}

export interface TierInfo {
  label: string;
  short: string;
  desc: string;
  /** pengali relatif terhadap jalan lingkungan (=1) */
  factor: number;
  lo: number;
  hi: number;
  /** jumlah iklan yang menyebut kondisi akses ini */
  n: number;
  /** "data" = dari regresi data; "campuran" = data + prior; "prior" = rujukan praktik penilaian */
  basis: "data" | "campuran" | "prior";
  dataFactor: number | null;
  /** jumlah iklan berkoordinat tepat per kelas akses hasil deteksi OSM (diagnostik) */
  nOsm: number;
  prior: number;
  priorNote: string;
}

export interface AutoAccessStats {
  n: number;
  medianAbsErrPct: number;
  biasLog: number;
  within25pct: number;
  coverage50pct: number;
  biasByDetectedTier: Partial<Record<AccessTier, number>>;
}

export interface PriceModel {
  version: string;
  asOf: string;
  refArea: number;
  sizeElasticity: number;
  sizeElasticitySE: number;
  /** kurva luas (menggantikan elastisitas tunggal): koefisien log per simpul luas, diinterpolasi terhadap log luas */
  sizeCurve?: {
    knots: {
      minM2: number;
      maxM2: number | null;
      area: number;
      coefRaw: number;
      se: number;
      coef: number;
      slopeRaw?: number;
      slopeSE?: number;
      slope?: number;
      n: number;
    }[];
    refBin: [number, number];
    levelCenter?: number;
    zMin?: number;
    zMax?: number;
    priorSD: number;
    rss: { bins: number | null; linear: number };
    note: string;
  };
  /** pengali σ menurut luas bidang (kalibrasi leave-one-out) */
  spreadBySize?: {
    classes: { minM2: number; maxM2: number | null; scale: number; scaleRaw: number | null; n: number }[];
    calibration: {
      crossFitCoverage50: { withScale: number; without: number; n: number }[];
      coverageByClassWithout: (number | null)[];
      coverageByClassWith: (number | null)[];
    };
    note: string;
  };
  /** batas atas rentang tier lebih rendah dibatasi pada titik estimasi tier di atasnya */
  tierCaps?: {
    gang: { ref: AccessTier; mult: number };
    tanpa: { ref: AccessTier; mult: number };
    gangCheck: {
      n: number;
      q25LogVsLingPoint: number | null;
      medianLogVsLingPoint: number | null;
      q75LogVsLingPoint: number | null;
      shareAboveLingPoint: number | null;
      withoutCap: { coverage50: number; aboveHigh: number } | null;
      withCap: { coverage50: number; aboveHigh: number } | null;
      capMult: number;
    };
    note: string;
  };
  /** faktor akses untuk tier hasil deteksi OSM (belum dipastikan pengguna) — dikalibrasi dari iklan, lihat Metodologi */
  autoAccess?: {
    factors: Record<AccessTier, number>;
    cbdScale: number;
    sdLog: number;
    n: Record<AccessTier, number>;
    medianRaw: Record<AccessTier, number>;
    validation: {
      before: AutoAccessStats;
      after: AutoAccessStats;
      note: string;
    };
    note: string;
  };
  /** premi koridor jalan arteri bernama (2026-10-5): residu iklan muka jalan per ruas, lihat Metodologi */
  corridor?: {
    k: number;
    bwM: number;
    minWeight: number;
    maxRoadM: number;
    aliases: Record<string, string>;
    /** kunci = nama jalan ternormalisasi; pts = [lat, lng, residu log terhadap estimasi tier utama] */
    roads: Record<string, { label: string; n: number; pts: [number, number, number][] }>;
    validation: {
      frontage: Record<string, { n: number; medianAbsErrPct: number; biasLog: number }>;
      display: { before: AutoAccessStats; after: AutoAccessStats; nWithPremium: number };
    };
    note: string;
  };
  /** prior wilayah halus (median berbobot jarak) menggantikan median kelurahan */
  smoothPrior?: { bwM: number; maxM: number; minN: number; note: string };
  commercialFactor: number;
  recencyHalfLifeYears: number;
  tiers: Record<AccessTier, TierInfo>;
  trendPerYear: number;
  trendRaw: number;
  trendSE: number;
  sourceEffect: number;
  sourceAdj: Record<string, number>;
  unknownTierFactor: number;
  cityMedianPn: number;
  citySpreadLog: number;
  /** jumlah pembanding efektif minimum sebelum radius diperbesar */
  minEffComparables?: number;
  locLevels?: Record<string, number>;
  /** pengali harga dasar menurut jarak ke kampus terdekat (pita jarak) */
  campus?: {
    minHa: number;
    priorSD: number;
    nCampuses: number;
    bands: { minM: number; maxM: number; coef: number; coefRaw: number; se: number; n: number }[];
    note: string;
  };
  /** premi tambahan muka jalan utama di pusat kota: exp(coef · exp(−d/scaleM)) */
  cbdFrontage?: {
    center: [number, number];
    centerName: string;
    scaleM: number;
    coef: number;
    coefRaw: number;
    coefSE: number;
    shrink: number;
    priorSD: number;
    nUtamaWithin3L: number;
    rssByScale: Record<string, number>;
    rssFlat: number;
    note: string;
  };
  regression: {
    n: number;
    r2Within: number;
    sigma: number;
    nOsm: number;
    r2WithinOsm: number;
    coefText: Record<string, [number, number]>;
    coefOsm: Record<string, [number, number]>;
    countsText: Record<string, number>;
    countsOsm: Record<string, number>;
    note: string;
  };
  validation: {
    n: number;
    medianAbsErrPct_model: number;
    medianAbsErrPct_kelurahanMedian: number;
    medianAbsErrPct_kecamatanMedian_raw: number;
    within25pct_model: number;
    coverage50pct: number;
    biasLog?: number;
    target?: string;
    allLocated?: ValidationStats;
    nKecamatanOnly?: number;
  };
}

export interface ValidationStats {
  n: number;
  medianAbsErrPct_model: number;
  medianAbsErrPct_kelurahanMedian: number;
  medianAbsErrPct_kecamatanMedian_raw: number;
  within25pct_model: number;
  coverage50pct: number;
  biasLog: number;
}

export interface AreaStat {
  name: string;
  kec: string;
  n: number;
  nExact: number;
  /** median harga ternormalisasi per m² */
  median: number;
  p25: number;
  p75: number;
  /** median harga penawaran asli */
  medianRaw: number;
  dateMin: string;
  dateMax: string;
  sources: Record<string, number>;
}

export interface Dataset {
  meta: {
    generatedAt: string;
    refArea: number;
    counts: { raw: number; clean: number; bySource: Record<string, number> };
    dateMin: string;
    dateMax: string;
    sources: { id: string; name: string; url: string; scrapedAt: string; rawCount: number; cleanCount: number; note: string }[];
    blocked: { name: string; reason: string }[];
    osmExtract: string;
    flags: Record<string, number>;
    dateSources: Record<string, number>;
    kelurahanCovered: number;
    kelurahanTotal: number;
  };
  comparables: Comparable[];
  /** poligon kampus (OSM, ≥ 2 ha) untuk faktor kedekatan kampus; cincin [lat, lng] */
  campuses?: { name: string; areaHa: number; rings: number[][][] }[];
  kelurahan: AreaStat[];
  kecamatan: AreaStat[];
  model: PriceModel;
}
