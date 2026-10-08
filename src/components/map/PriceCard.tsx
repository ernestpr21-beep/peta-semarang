import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { ChevronDown, ExternalLink, Info, Route, TriangleAlert } from "lucide-react";
import type { PriceResult } from "@/lib/estimate";
import type { AccessDetection } from "@/lib/access";
import { TIER_ORDER, type AccessTier, type PriceModel } from "@/lib/model";
import { PRICE_LABEL } from "@/lib/constants";
import { useAppStore } from "@/lib/store";
import { cn, formatDistance, formatMonth, formatRupiah, formatRupiahRange, formatRupiahShort } from "@/lib/utils";
import { Chip, Skeleton } from "@/components/ui/primitives";

const AREA_PRESETS = [100, 150, 300, 500, 1000, 5000];
const TIER_COLOR: Record<AccessTier, string> = {
  utama: "var(--tier-utama)",
  lingkungan: "var(--tier-lingkungan)",
  gang: "var(--tier-gang)",
  tanpa: "var(--tier-tanpa)",
};
const CONF_STYLE = { tinggi: "text-good border-good/40", sedang: "text-fg border-border-strong", rendah: "text-warn border-warn/50" } as const;

function pct(f: number) {
  const v = Math.round((f - 1) * 100);
  return v === 0 ? "acuan" : `${v > 0 ? "+" : "−"}${Math.abs(v)}%`;
}

export function PriceSkeleton() {
  return (
    <div className="space-y-2" aria-busy="true">
      <p className="text-xs text-fg-muted">Memuat data pembanding, jalan &amp; batas wilayah…</p>
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-28 w-full" />
    </div>
  );
}

export function PriceCard({ price, access, tier, tierIsManual, model }: { price: PriceResult; access: AccessDetection | null; tier: AccessTier | null; tierIsManual: boolean; model: PriceModel }) {
  const area = useAppStore((s) => s.area);
  const setArea = useAppStore((s) => s.setArea);
  const setTier = useAppStore((s) => s.setTierOverride);
  const [showComps, setShowComps] = useState(false);
  const [showFactors, setShowFactors] = useState(false);

  if (!price.available) {
    return (
      <div className="flex gap-2 rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-fg">
        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" />
        {price.reason}
      </div>
    );
  }
  const t = tier ?? "lingkungan";
  // tier hasil deteksi OSM belum pasti → harga utama memakai faktor akses terkalibrasi (lihat Metodologi)
  const isAuto = !tierIsManual && !!model.autoAccess;
  const main = isAuto ? price.autoTiers[t] : price.tiers[t];
  const accessFactor = isAuto ? price.autoFactors[t] : model.tiers[t].factor * (t === "utama" ? price.cbdFactor : 1);
  const ti = model.tiers[t];
  const noAccess = price.tiers.tanpa;
  const withAccess = price.tiers[t === "tanpa" ? "lingkungan" : t];

  return (
    <div className="space-y-3">
      {/* Kondisi akses */}
      <div className="rounded-lg border border-border bg-surface-2/60 p-2.5">
        <div className="flex items-start gap-2">
          <Route className="mt-0.5 size-4 shrink-0" style={{ color: TIER_COLOR[t] }} />
          <div className="min-w-0 flex-1">
            <p className="text-[11px] uppercase tracking-wide text-fg-subtle">{tierIsManual ? "Kondisi akses (dipilih manual)" : "Kondisi akses terdeteksi (OSM)"}</p>
            <p className="text-sm font-semibold" style={{ color: TIER_COLOR[t] }}>
              {ti.label}
            </p>
            {access && !tierIsManual ? <p className="text-[11px] leading-snug text-fg-muted">{access.reason}</p> : null}
            {access && tierIsManual ? <p className="text-[11px] text-fg-muted">Deteksi OSM: {model.tiers[access.tier].short}</p> : null}
          </div>
        </div>
        <div className="mt-2 grid grid-cols-4 gap-1" role="radiogroup" aria-label="Pilih kondisi akses">
          {TIER_ORDER.map((k) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={t === k}
              onClick={() => setTier(access && access.tier === k ? null : k)}
              className={cn("rounded-md border px-1 py-1 text-[10.5px] font-medium leading-tight", t === k ? "border-transparent text-white" : "border-border bg-surface text-fg-muted hover:text-fg")}
              style={t === k ? { background: TIER_COLOR[k] } : undefined}
            >
              {model.tiers[k].short}
            </button>
          ))}
        </div>
        {isAuto ? (
          <p className="mt-1.5 text-[10.5px] leading-snug text-fg-subtle">
            Deteksi otomatis dari jarak ke jalan OSM <b>belum memastikan</b> kondisi akses (banyak gang kampung belum terpetakan). Harga utama memakai faktor akses terkalibrasi untuk titik
            dengan deteksi serupa (×{price.autoFactors[t].toFixed(2)}); pilih kondisi akses bila Anda tahu kondisinya.
          </p>
        ) : (
          <p className="mt-1.5 text-[10.5px] leading-snug text-fg-subtle">Deteksi otomatis dari jarak ke jalan OSM — cek di lapangan/citra satelit dan ubah bila perlu.</p>
        )}
      </div>

      {/* Harga utama */}
      <div className="rounded-lg border border-border bg-surface p-3 shadow-sm">
        <div className="flex items-center justify-between gap-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-fg-subtle">{PRICE_LABEL}</p>
          <span className={cn("rounded-full border px-2 py-0.5 text-[10.5px] font-medium", CONF_STYLE[price.confidence])}>Keyakinan {price.confidence}</span>
        </div>
        <p className="mt-1 font-mono text-2xl font-medium tabular-nums leading-tight">
          {formatRupiahRange(main.low, main.high)}
          <span className="ml-1 text-sm text-fg-muted">/m²</span>
        </p>
        <p className="text-xs text-fg-muted">
          titik tengah <span className="num text-fg">{formatRupiah(main.point)}</span>/m² · tanah kosong {isAuto ? "kondisi akses belum dipastikan" : ti.short.toLowerCase()}
        </p>
        <div className="mt-2 flex items-center justify-between gap-2 rounded-md bg-surface-2 px-2.5 py-1.5 text-xs">
          <span className="text-fg-muted">Total {area.toLocaleString("id-ID")} m²</span>
          <span className="num font-medium">
            {formatRupiahRange(main.low * area, main.high * area)}
          </span>
        </div>
        <div className="mt-2">
          <p className="mb-1 text-[11px] text-fg-subtle">Luas bidang (memengaruhi harga/m²)</p>
          <div className="flex flex-wrap items-center gap-1">
            {AREA_PRESETS.map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setArea(a)}
                className={cn("h-7 rounded-full px-2 text-[11px] font-medium", area === a ? "bg-primary text-primary-foreground" : "bg-surface-2 text-fg-muted hover:text-fg")}
              >
                {a.toLocaleString("id-ID")}
              </button>
            ))}
            <input
              type="number"
              min={30}
              max={50000}
              aria-label="Luas bidang m²"
              value={area}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (Number.isFinite(v) && v >= 1) setArea(Math.min(50000, Math.round(v)));
              }}
              className="h-7 w-20 rounded-md border border-border bg-surface px-1.5 text-[11px] num"
            />
            <span className="text-[11px] text-fg-muted">m²</span>
          </div>
        </div>
      </div>

      {/* Ada akses vs tanpa akses */}
      <div>
        <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-fg-subtle">Perbandingan menurut akses jalan</p>
        <ul className="overflow-hidden rounded-lg border border-border">
          {TIER_ORDER.map((k) => {
            const tp = price.tiers[k];
            const mt = model.tiers[k];
            const active = !isAuto && k === t;
            return (
              <li
                key={k}
                className={cn("flex items-center justify-between gap-2 border-b border-border px-2.5 py-2 last:border-b-0", active ? "bg-surface-2" : "bg-surface")}
                style={active ? { boxShadow: `inset 3px 0 0 ${TIER_COLOR[k]}` } : undefined}
              >
                <div className="min-w-0">
                  <p className={cn("text-xs", active ? "font-semibold" : "font-medium")}>
                    <span className="mr-1.5 inline-block size-2 rounded-full align-middle" style={{ background: TIER_COLOR[k] }} />
                    {mt.label}
                  </p>
                  <p className="text-[10.5px] text-fg-subtle">
                    faktor ×{mt.factor.toFixed(2)} ({pct(mt.factor)}) · {mt.basis === "data" ? "dari data" : mt.basis === "campuran" ? "data + rujukan" : "rujukan (data iklan minim)"}
                  </p>
                </div>
                <p className="num shrink-0 text-right text-xs">
                  {formatRupiahRange(tp.low, tp.high)}
                </p>
              </li>
            );
          })}
        </ul>
        <p className="mt-1.5 text-[11px] leading-snug text-fg-muted">
          {t === "tanpa" && !isAuto ? (
            <>
              Tanpa akses ≈ <b>{Math.round((1 - noAccess.point / withAccess.point) * 100)}% lebih murah</b> daripada bidang yang punya akses jalan lingkungan di lokasi yang sama.
            </>
          ) : (
            <>
              Bila bidang ini <b>tidak punya akses jalan</b> (terkurung): {formatRupiahRange(noAccess.low, noAccess.high)}/m², sekitar{" "}
              {Math.round((1 - noAccess.point / main.point) * 100)}% di bawah {isAuto ? "harga utama" : `kondisi ${ti.short.toLowerCase()}`}.
            </>
          )}{" "}
          <Link to="/metodologi" hash="akses" className="text-primary underline underline-offset-2">
            Dasar faktor
          </Link>
        </p>
      </div>

      {/* Dasar perhitungan */}
      <div className="rounded-lg border border-border p-2.5 text-xs">
        <p className="leading-relaxed text-fg">
          Dihitung dari <b>{price.nUsed} iklan pembanding</b> dalam radius {formatDistance(price.radiusM)} (terdekat {formatDistance(price.nearestM)}, median jarak{" "}
          {formatDistance(price.medianDistanceM)}; {price.nExact} berkoordinat tepat){price.dateMin ? `, iklan ${formatMonth(price.dateMin)}–${formatMonth(price.dateMax)}` : ""}.
        </p>
        <p className="mt-1 text-fg-muted">{price.confidenceReason}. Rentang = 50% tengah sebaran pembanding (−{Math.round(price.halfWidthPct.low * 100)}% / +{Math.round(price.halfWidthPct.high * 100)}%), bukan ±20% tetap.</p>
        <button type="button" onClick={() => setShowFactors(!showFactors)} className="mt-2 flex items-center gap-1 text-[11px] font-medium text-primary">
          <ChevronDown className={cn("size-3.5 transition-transform", showFactors && "rotate-180")} /> Faktor perhitungan
        </button>
        {showFactors ? (
          <table className="mt-1.5 w-full text-[11px]">
            <tbody className="[&_td]:py-0.5 [&_td:last-child]:text-right [&_td:last-child]:font-mono">
              <tr>
                <td className="text-fg-muted">Median lokal pembanding (dinormalisasi*)</td>
                <td>{price.localMedian ? formatRupiahShort(price.localMedian) : "—"}</td>
              </tr>
              <tr>
                <td className="text-fg-muted">
                  {price.priorLevel === "sekitar"
                    ? `Median wilayah sekitar (berbobot jarak, ${price.priorName})`
                    : `Median ${price.priorLevel} ${price.priorLevel !== "kota" ? price.priorName : ""}`}{" "}
                  (bobot {Math.round(price.priorShare * 100)}%)
                </td>
                <td>{formatRupiahShort(price.priorMedian)}</td>
              </tr>
              {price.campusFactor !== 1 && price.campus ? (
                <tr>
                  <td className="text-fg-muted">
                    × kedekatan kampus ({price.campus.name}, {price.campus.distanceM < 1 ? "di dalam area" : formatDistance(price.campus.distanceM)})
                  </td>
                  <td>×{price.campusFactor.toFixed(2)}</td>
                </tr>
              ) : null}
              <tr>
                <td className="text-fg-muted">Harga dasar bidang acuan</td>
                <td>{formatRupiahShort(price.basePoint)}</td>
              </tr>
              <tr>
                <td className="text-fg-muted">× faktor akses ({isAuto ? `deteksi OSM: ${ti.short.toLowerCase()}, terkalibrasi` : ti.short}{t === "utama" && price.cbdFactor > 1.01 ? ", termasuk premi pusat kota" : ""})</td>
                <td>×{accessFactor.toFixed(2)}</td>
              </tr>
              <tr>
                <td className="text-fg-muted">× faktor luas ({area.toLocaleString("id-ID")} m²)</td>
                <td>×{price.sizeFactor.toFixed(2)}</td>
              </tr>
              <tr className="border-t border-border">
                <td className="font-medium">Titik tengah</td>
                <td className="font-medium">{formatRupiahShort(main.point)}</td>
              </tr>
            </tbody>
          </table>
        ) : null}
        {showFactors ? (
          <p className="mt-1 text-[10.5px] text-fg-subtle">
            *Tiap iklan dinormalisasi ke bidang acuan {model.refArea} m², akses jalan lingkungan, per {formatMonth(model.asOf)}, dan selisih tingkat harga antarportal dinetralkan.
          </p>
        ) : null}
      </div>

      {/* Daftar pembanding */}
      <div>
        <button type="button" onClick={() => setShowComps(!showComps)} className="flex w-full items-center justify-between rounded-md px-1 py-1 text-xs font-medium hover:bg-surface-2">
          <span>Lihat {Math.min(price.used.length, 15)} pembanding terdekat</span>
          <ChevronDown className={cn("size-4 transition-transform", showComps && "rotate-180")} />
        </button>
        {showComps ? (
          <ul className="mt-1 space-y-1">
            {price.used.slice(0, 15).map(({ c, distanceM }) => (
              <li key={c.id} className="rounded-md border border-border px-2 py-1.5 text-[11px]">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="num font-medium">{formatRupiahShort(c.ppm)}/m²</span>
                  <span className="text-fg-muted">
                    {formatDistance(distanceM)}
                    {c.exact ? "" : " (perkiraan: pusat kelurahan)"}
                  </span>
                </div>
                <p className="truncate text-fg-muted" title={c.title}>
                  {c.area.toLocaleString("id-ID")} m² · {c.kel ?? c.kec} · akses {c.tier ?? "tidak disebut"}
                </p>
                {c.url ? (
                  <a href={c.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary">
                    {c.src === "pinhome" ? "Pinhome" : "Lamudi"} · {formatMonth(c.date)} <ExternalLink className="size-3" />
                  </a>
                ) : (
                  <span className="text-fg-subtle" title="URL iklan memuat nomor telepon sehingga tidak dipublikasikan">
                    {c.src === "pinhome" ? "Pinhome" : "Lamudi"} · {formatMonth(c.date)} · tautan disembunyikan
                  </span>
                )}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="flex gap-2 rounded-md border border-border bg-surface-2/60 px-2.5 py-2 text-[11px] leading-snug text-fg-muted">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        <span>
          Ini <b>estimasi kisaran harga pasar</b> dari harga <i>penawaran</i> iklan — bukan NJOP, bukan nilai ZNT BPN, bukan appraisal. Harga transaksi biasanya di bawah harga penawaran. Untuk nilai resmi, cek Zona Nilai Tanah di{" "}
          <a className="text-primary underline" href="https://bhumi.atrbpn.go.id/" target="_blank" rel="noopener noreferrer">
            BHUMI ATR/BPN
          </a>
          .
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        <Chip>Model {model.version}</Chip>
        <Chip>Data s.d. {formatMonth(model.asOf)}</Chip>
      </div>
    </div>
  );
}
