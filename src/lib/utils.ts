import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function normalizeName(s: string | null | undefined): string {
  return (s ?? "")
    .toLowerCase()
    .replace(/\(.*?\)/g, "")
    .replace(/^(kel\.|kelurahan|kec\.|kecamatan|desa)\s+/g, "")
    .replace(/[^a-z0-9]/g, "");
}

export function formatCoord(n: number) {
  return n.toFixed(6);
}

const rupiah = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });

export function formatRupiah(n: number) {
  return `Rp ${rupiah.format(Math.round(n))}`;
}

/** Ringkas: Rp 3,4 jt · Rp 850 rb · Rp 12,5 jt */
export function formatRupiahShort(n: number) {
  if (!Number.isFinite(n)) return "—";
  if (n >= 1e9) return `Rp ${(n / 1e9).toLocaleString("id-ID", { maximumFractionDigits: 2 })} M`;
  if (n >= 1e6) return `Rp ${(n / 1e6).toLocaleString("id-ID", { maximumFractionDigits: n >= 1e7 ? 1 : 2 })} jt`;
  if (n >= 1e3) return `Rp ${Math.round(n / 1e3).toLocaleString("id-ID")} rb`;
  return `Rp ${Math.round(n)}`;
}

/** Bulatkan harga ke 2 angka penting (mis. 3.456.000 → 3.500.000) agar tidak memberi kesan presisi palsu. */
export function roundSig(n: number, sig = 2) {
  if (!Number.isFinite(n) || n <= 0) return n;
  const p = Math.pow(10, Math.floor(Math.log10(n)) - sig + 1);
  return Math.round(n / p) * p;
}

export function formatDistance(m: number) {
  if (m < 1000) return `${Math.round(m)} m`;
  return `${(m / 1000).toLocaleString("id-ID", { maximumFractionDigits: 1 })} km`;
}

export function formatMonth(ym: string) {
  const [y, m] = ym.split("-").map(Number);
  const names = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  if (!y || !m) return ym;
  return `${names[m - 1]} ${y}`;
}

/** Rentang ringkas: "Rp 2,3–3,9 jt" (satuan sama) atau "Rp 850 rb – Rp 1,2 jt". */
export function formatRupiahRange(lo: number, hi: number) {
  const a = formatRupiahShort(lo);
  const b = formatRupiahShort(hi);
  const ua = a.split(" ").pop();
  const ub = b.split(" ").pop();
  if (ua === ub && ["jt", "rb", "M"].includes(ua ?? "")) return `${a.slice(0, -(ua!.length + 1))}–${b.slice(3)}`;
  return `${a} – ${b}`;
}
