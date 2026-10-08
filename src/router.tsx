import { createRootRoute, createRoute, createRouter, Outlet, redirect } from "@tanstack/react-router";
import { Toaster } from "sonner";
import { AppHeader } from "@/components/layout/AppHeader";
import { useAppStore } from "@/lib/store";
import { MapPage } from "@/pages/MapPage";
import { MetodologiPage } from "@/pages/MetodologiPage";
import { TentangPage } from "@/pages/TentangPage";
import { DataZonaPage } from "@/pages/DataZonaPage";

function Root() {
  const theme = useAppStore((s) => s.theme);
  return (
    <div className="flex min-h-svh flex-col bg-bg text-fg">
      <AppHeader />
      <Outlet />
      <Toaster richColors position="top-center" theme={theme} />
    </div>
  );
}

const rootRoute = createRootRoute({ component: Root, notFoundComponent: () => <div className="p-8 text-center text-sm text-fg-muted">Halaman tidak ditemukan.</div> });
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: MapPage });
const metodologiRoute = createRoute({ getParentRoute: () => rootRoute, path: "/metodologi", component: MetodologiPage });
const tentangRoute = createRoute({ getParentRoute: () => rootRoute, path: "/tentang", component: TentangPage });
const zonaRoute = createRoute({ getParentRoute: () => rootRoute, path: "/data-zona", component: DataZonaPage });
const legacyZona = createRoute({ getParentRoute: () => rootRoute, path: "/data-editor", beforeLoad: () => { throw redirect({ to: "/data-zona" }); } });

const routeTree = rootRoute.addChildren([indexRoute, metodologiRoute, tentangRoute, zonaRoute, legacyZona]);
export const router = createRouter({ routeTree, basepath: import.meta.env.BASE_URL.replace(/\/$/, "") || "/", defaultPreload: "intent", scrollRestoration: true });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
