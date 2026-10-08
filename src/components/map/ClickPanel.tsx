import { useState } from "react";
import { Check, Copy, MapPinned, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { useLocationDetails } from "@/hooks/useLocationDetails";
import { useDataset } from "@/lib/data";
import { formatCoord } from "@/lib/utils";
import { PRICE_LABEL } from "@/lib/constants";
import { Button, Chip, SectionTitle, Separator, Skeleton } from "@/components/ui/primitives";
import { PriceCard, PriceSkeleton } from "./PriceCard";
import { ScoreCard } from "./ScoreCard";
import { FacilityList } from "./FacilityList";

export function ClickPanel() {
  const d = useLocationDetails();
  const ds = useDataset();
  const [copied, setCopied] = useState(false);

  if (!d.clicked) {
    return (
      <div className="flex h-full flex-col justify-center gap-2 px-6 py-8 text-center">
        <MapPinned className="mx-auto size-8 text-primary" />
        <h2 className="text-base font-semibold">Klik peta untuk detail lokasi</h2>
        <p className="text-sm text-fg-muted">
          Alamat, kelurahan, {PRICE_LABEL.toLowerCase()} tanah kosong — dibedakan antara yang <b>punya akses jalan</b> dan yang <b>tanpa akses</b> — fasilitas terdekat, dan skor lokasi 0–100.
        </p>
        {ds.data ? (
          <p className="mt-2 text-[11px] text-fg-subtle">
            {ds.data.meta.counts.clean.toLocaleString("id-ID")} iklan tanah pembanding · {ds.data.meta.kelurahanCovered} dari {ds.data.meta.kelurahanTotal} kelurahan
          </p>
        ) : null}
      </div>
    );
  }

  const { lat, lng } = d.clicked;
  const coordText = `${formatCoord(lat)}, ${formatCoord(lng)}`;
  async function copy() {
    try {
      await navigator.clipboard.writeText(coordText);
      setCopied(true);
      toast.success("Koordinat disalin");
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Gagal menyalin");
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <section className="space-y-2">
          <p className="text-xs uppercase tracking-wide text-fg-subtle">Detail lokasi</p>
          <div className="flex items-center justify-between gap-2">
            <p className="font-mono text-sm tabular-nums">{coordText}</p>
            <Button variant="outline" size="sm" onClick={copy} className="shrink-0">
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              Salin
            </Button>
          </div>
          {d.address.isLoading ? (
            <Skeleton className="h-9 w-full" />
          ) : d.address.isError ? (
            <p className="text-xs text-fg-muted">Alamat gagal dimuat (Nominatim). Koordinat tetap valid.</p>
          ) : (
            <p className="text-sm leading-snug">{d.address.data?.label || "Alamat tidak ditemukan"}</p>
          )}
          {d.loading ? (
            <Skeleton className="h-6 w-2/3" />
          ) : d.insideCity ? (
            <div className="flex flex-wrap gap-1">
              <Chip>Kec. {d.kecamatan ?? "—"}</Chip>
              <Chip>Kel. {d.kelurahan ?? "—"}</Chip>
            </div>
          ) : (
            <div className="flex gap-2 rounded-md border border-warn/40 bg-warn/10 px-2.5 py-2 text-xs">
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warn" />
              Titik ini di luar Kota Semarang. Estimasi harga tidak dihitung.
            </div>
          )}
          {d.error ? <p className="text-xs text-danger">Gagal memuat data: {d.error}</p> : null}
        </section>

        <Separator className="my-4" />
        <section>
          <SectionTitle>Harga tanah kosong</SectionTitle>
          {d.loading || !d.price || !ds.data ? <PriceSkeleton /> : <PriceCard price={d.price} access={d.access} tier={d.tier} tierIsManual={d.tierIsManual} model={ds.data.model} />}
        </section>

        <Separator className="my-4" />
        <section>
          <SectionTitle>Skor lokasi</SectionTitle>
          <ScoreCard data={d.score} />
        </section>

        <Separator className="my-4" />
        <section>
          <SectionTitle>Fasilitas terdekat</SectionTitle>
          <FacilityList facilities={d.facilities} />
        </section>
      </div>
    </div>
  );
}
