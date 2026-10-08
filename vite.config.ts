import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// SPA murni (tanpa SSR) — Leaflet hanya dimuat di peramban lewat import dinamis (MapView.tsx).
export default defineConfig({
  // BASE_PATH=/peta-semarang/ untuk GitHub Pages; bawaan "/" (npm run dev / npm start)
  base: process.env.BASE_PATH || "/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  build: { target: "es2022", chunkSizeWarningLimit: 900 },
});
