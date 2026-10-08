import { useSyncExternalStore } from "react";

const QUERY = "(max-width: 767px)";
function subscribe(cb: () => void) {
  const m = window.matchMedia(QUERY);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
}
/** true bila lebar layar < 768 px (breakpoint md Tailwind) */
export function useIsMobile() {
  return useSyncExternalStore(subscribe, () => window.matchMedia(QUERY).matches, () => false);
}
