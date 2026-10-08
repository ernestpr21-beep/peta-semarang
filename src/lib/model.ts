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

export interface PriceModel {
  version: string;
  asOf: string;
  refArea: number;
  sizeElasticity: number;
  sizeElasticitySE: number;
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
