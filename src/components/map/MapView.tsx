import { lazy, Suspense } from "react";
import { Skeleton } from "@/components/ui/primitives";

// Leaflet hanya dimuat di peramban (aplikasi ini SPA murni, tanpa SSR) dan dipisah ke chunk sendiri.
const MapInner = lazy(() => import("./MapInner"));

export function MapView() {
  return (
    <Suspense fallback={<Skeleton className="absolute inset-0 rounded-none" />}>
      <div className="absolute inset-0">
        <MapInner />
      </div>
    </Suspense>
  );
}
