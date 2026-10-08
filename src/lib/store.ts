import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { BasemapId, RadiusM } from "./constants";
import type { AccessTier } from "./model";

export interface LatLngPoint {
  lat: number;
  lng: number;
}

interface AppState {
  theme: "light" | "dark";
  basemap: BasemapId;
  showComparables: boolean;
  showPriceLayer: boolean;
  clicked: LatLngPoint | null;
  searchMarker: (LatLngPoint & { label: string }) | null;
  cursor: LatLngPoint | null;
  focusTarget: (LatLngPoint & { zoom?: number; t: number }) | null;
  radiusM: RadiusM;
  hoverKecamatan: string | null;
  panelOpen: boolean;
  /** pilihan manual kondisi akses (null = pakai deteksi OSM) */
  tierOverride: AccessTier | null;
  /** luas bidang (m²) untuk estimasi */
  area: number;
  toggleTheme: () => void;
  setBasemap: (b: BasemapId) => void;
  setShowComparables: (v: boolean) => void;
  setShowPriceLayer: (v: boolean) => void;
  setClicked: (p: LatLngPoint | null) => void;
  setSearchMarker: (p: (LatLngPoint & { label: string }) | null) => void;
  setCursor: (p: LatLngPoint | null) => void;
  flyTo: (p: LatLngPoint, zoom?: number) => void;
  setRadius: (r: RadiusM) => void;
  setHoverKecamatan: (k: string | null) => void;
  setPanelOpen: (v: boolean) => void;
  setTierOverride: (t: AccessTier | null) => void;
  setArea: (a: number) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      theme: "light",
      basemap: "streets",
      showComparables: true,
      showPriceLayer: false,
      clicked: null,
      searchMarker: null,
      cursor: null,
      focusTarget: null,
      radiusM: 1000,
      hoverKecamatan: null,
      panelOpen: false,
      tierOverride: null,
      area: 150,
      toggleTheme: () =>
        set((s) => {
          const theme = s.theme === "dark" ? "light" : "dark";
          document.documentElement.classList.toggle("dark", theme === "dark");
          return { theme };
        }),
      setBasemap: (basemap) => set({ basemap }),
      setShowComparables: (showComparables) => set({ showComparables }),
      setShowPriceLayer: (showPriceLayer) => set({ showPriceLayer }),
      setClicked: (clicked) => set({ clicked, panelOpen: Boolean(clicked), tierOverride: null }),
      setSearchMarker: (searchMarker) => set({ searchMarker }),
      setCursor: (cursor) => set({ cursor }),
      flyTo: (p, zoom) => set({ focusTarget: { ...p, zoom, t: Date.now() } }),
      setRadius: (radiusM) => set({ radiusM }),
      setHoverKecamatan: (hoverKecamatan) => set({ hoverKecamatan }),
      setPanelOpen: (panelOpen) => set({ panelOpen }),
      setTierOverride: (tierOverride) => set({ tierOverride }),
      setArea: (area) => set({ area }),
    }),
    {
      name: "peta-semarang-ui",
      partialize: (s) => ({ theme: s.theme, basemap: s.basemap, showComparables: s.showComparables, showPriceLayer: s.showPriceLayer, radiusM: s.radiusM, area: s.area }),
    },
  ),
);
