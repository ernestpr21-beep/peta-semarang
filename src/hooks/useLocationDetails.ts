import { useMemo } from "react";
import { useAppStore } from "@/lib/store";
import { useDataset, useFacilities, useKecamatan, useKelurahan, useKota, useReverseGeocode, useRoadsAround } from "@/lib/data";
import { findFeature } from "@/lib/geo";
import { detectAccess, type AccessDetection } from "@/lib/access";
import { estimatePrice, findAreaStat, type PriceResult } from "@/lib/estimate";
import { facilitiesNear, type Facility } from "@/lib/facilities";
import { computeLocationScore, SCORE_SEARCH_RADIUS, type LocationScore } from "@/lib/score";
import type { AccessTier } from "@/lib/model";

export interface LocationDetails {
  clicked: { lat: number; lng: number } | null;
  /** true selama data dasar (dataset, batas wilayah, jalan, fasilitas) belum siap — jangan tampilkan angka sementara */
  loading: boolean;
  error: string | null;
  insideCity: boolean;
  kecamatan: string | null;
  kelurahan: string | null;
  address: ReturnType<typeof useReverseGeocode>;
  access: AccessDetection | null;
  tier: AccessTier | null;
  tierIsManual: boolean;
  price: PriceResult | null;
  score: LocationScore | null;
  facilitiesAll: Facility[] | null;
  facilities: Facility[] | null;
}

export function useLocationDetails(): LocationDetails {
  const clicked = useAppStore((s) => s.clicked);
  const radiusM = useAppStore((s) => s.radiusM);
  const override = useAppStore((s) => s.tierOverride);
  const area = useAppStore((s) => s.area);
  const ds = useDataset();
  const kota = useKota();
  const kec = useKecamatan();
  const kel = useKelurahan();
  const fac = useFacilities();
  const lat = clicked?.lat ?? null;
  const lng = clicked?.lng ?? null;
  const roads = useRoadsAround(lat, lng);
  const address = useReverseGeocode(lat, lng);

  const admin = useMemo(() => {
    if (!clicked || !kota.data || !kec.data || !kel.data) return null;
    const inside = Boolean(findFeature(clicked.lat, clicked.lng, kota.data));
    const kc = findFeature(clicked.lat, clicked.lng, kec.data)?.properties.name ?? null;
    const kl = findFeature(clicked.lat, clicked.lng, kel.data)?.properties ?? null;
    return { inside, kec: kl?.kecamatan ?? kc, kel: kl?.name ?? null };
  }, [clicked, kota.data, kec.data, kel.data]);

  const access = useMemo(() => (clicked && roads.roads ? detectAccess(clicked.lat, clicked.lng, roads.roads) : null), [clicked, roads.roads]);

  const price = useMemo(() => {
    if (!clicked || !ds.data || !admin) return null;
    return estimatePrice({
      lat: clicked.lat,
      lng: clicked.lng,
      insideCity: admin.inside,
      comps: ds.data.comparables,
      model: ds.data.model,
      kelStat: findAreaStat(ds.data.kelurahan, admin.kel, admin.kec),
      kecStat: findAreaStat(ds.data.kecamatan, admin.kec),
      area,
    });
  }, [clicked, ds.data, admin, area]);

  const facilitiesAll = useMemo(
    () => (clicked && fac.data ? facilitiesNear(fac.data.rows, clicked.lat, clicked.lng, SCORE_SEARCH_RADIUS) : null),
    [clicked, fac.data],
  );
  const facilities = useMemo(() => facilitiesAll?.filter((f) => f.distanceM <= radiusM) ?? null, [facilitiesAll, radiusM]);
  const score = useMemo(() => (clicked && facilitiesAll ? computeLocationScore(clicked.lat, clicked.lng, facilitiesAll) : null), [clicked, facilitiesAll]);

  const loading = Boolean(clicked) && (ds.isLoading || kota.isLoading || kec.isLoading || kel.isLoading || fac.isLoading || roads.loading);
  const errObj = ds.error ?? kota.error ?? kel.error ?? fac.error ?? roads.error;
  const tier = override ?? access?.tier ?? null;

  return {
    clicked,
    loading,
    error: errObj ? String((errObj as Error).message ?? errObj) : null,
    insideCity: admin?.inside ?? false,
    kecamatan: admin?.kec ?? null,
    kelurahan: admin?.kel ?? null,
    address,
    access,
    tier,
    tierIsManual: override != null,
    price: loading ? null : price,
    score: loading ? null : score,
    facilitiesAll: loading ? null : facilitiesAll,
    facilities: loading ? null : facilities,
  };
}
