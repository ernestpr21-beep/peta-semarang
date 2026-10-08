import { haversineMeters } from "./geo";

export type FacilityGroup = "pendidikan" | "kesehatan" | "transportasi" | "komersial" | "publik" | "ibadah";

export const GROUP_ORDER: FacilityGroup[] = ["pendidikan", "kesehatan", "transportasi", "komersial", "publik", "ibadah"];

export const GROUP_LABEL: Record<FacilityGroup, string> = {
  pendidikan: "Pendidikan",
  kesehatan: "Kesehatan",
  transportasi: "Transportasi",
  komersial: "Komersial",
  publik: "Layanan publik",
  ibadah: "Ibadah",
};

export const KIND_LABEL: Record<string, string> = {
  paud: "PAUD / TK",
  sd: "SD / MI",
  smp: "SMP / MTs",
  sma: "SMA / SMK / MA",
  sekolah: "Sekolah",
  kampus: "Kampus",
  rs: "Rumah sakit",
  puskesmas: "Puskesmas",
  klinik: "Klinik / dokter",
  apotek: "Apotek",
  halte: "Halte / BRT",
  stasiun: "Stasiun",
  terminal: "Terminal",
  tol: "Gerbang tol",
  bandara: "Bandara",
  pelabuhan: "Pelabuhan",
  pasar: "Pasar",
  minimarket: "Minimarket",
  supermarket: "Supermarket",
  mall: "Mal",
  bank: "Bank",
  spbu: "SPBU",
  kantor: "Kantor pemerintahan",
  kelurahan: "Kantor kelurahan",
  kecamatan: "Kantor kecamatan",
  polisi: "Polisi",
  pemadam: "Pemadam kebakaran",
  masjid: "Masjid / musala",
  gereja: "Gereja",
  ibadah: "Tempat ibadah",
};

export interface FacilityRaw {
  /** [lat, lng, group, kind, name, osmRef] */
  0: number;
  1: number;
  2: FacilityGroup;
  3: string;
  4: string;
  5: string;
}

export interface Facility {
  id: string;
  lat: number;
  lng: number;
  group: FacilityGroup;
  kind: string;
  kindLabel: string;
  name: string;
  distanceM: number;
}

export function facilitiesNear(rows: FacilityRaw[], lat: number, lng: number, radiusM: number): Facility[] {
  const dLat = radiusM / 111000 + 0.001;
  const dLng = radiusM / (111000 * Math.cos((lat * Math.PI) / 180)) + 0.001;
  const out: Facility[] = [];
  for (const r of rows) {
    if (Math.abs(r[0] - lat) > dLat || Math.abs(r[1] - lng) > dLng) continue;
    const d = haversineMeters(lat, lng, r[0], r[1]);
    if (d > radiusM) continue;
    out.push({
      id: r[5],
      lat: r[0],
      lng: r[1],
      group: r[2],
      kind: r[3],
      kindLabel: KIND_LABEL[r[3]] ?? r[3],
      name: r[4] || KIND_LABEL[r[3]] || r[3],
      distanceM: d,
    });
  }
  return out.sort((a, b) => a.distanceM - b.distanceM);
}

/** Estimasi waktu tempuh kasar: jalan kaki 4,5 km/j (≤ 1,2 km), motor/mobil kota 20 km/j selebihnya. Jarak garis lurus × 1,3. */
export function travelTimeLabel(distanceM: number) {
  const d = distanceM * 1.3;
  if (d <= 1200) return `±${Math.max(1, Math.round(d / 75))} mnt jalan kaki`;
  return `±${Math.max(1, Math.round(d / 333))} mnt berkendara`;
}
