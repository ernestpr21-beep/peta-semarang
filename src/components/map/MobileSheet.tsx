import { Drawer } from "vaul";
import { useAppStore } from "@/lib/store";
import { ClickPanel } from "./ClickPanel";
import { useIsMobile } from "@/hooks/useIsMobile";

export function MobileSheet() {
  const open = useAppStore((s) => s.panelOpen);
  const setOpen = useAppStore((s) => s.setPanelOpen);
  const clicked = useAppStore((s) => s.clicked);
  const mobile = useIsMobile();
  // Drawer hanya untuk layar kecil; di desktop panel samping yang dipakai (drawer terbuka akan memblokir klik peta)
  if (!mobile) return null;
  return (
    <Drawer.Root open={open && Boolean(clicked)} onOpenChange={setOpen}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 z-[900] bg-fg/25 md:hidden" />
        <Drawer.Content className="fixed bottom-0 left-0 right-0 z-[1000] flex h-[min(82vh,760px)] flex-col rounded-t-xl border-t border-border bg-surface outline-none md:hidden">
          <Drawer.Handle className="mx-auto mt-2 h-1.5 w-12 rounded-full bg-border-strong" />
          <Drawer.Title className="sr-only">Detail lokasi</Drawer.Title>
          <Drawer.Description className="sr-only">Estimasi kisaran harga pasar, akses jalan, skor dan fasilitas</Drawer.Description>
          <div className="min-h-0 flex-1 overflow-hidden">
            <ClickPanel />
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
