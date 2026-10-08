/** Skala warna harga/m² (log) — dipakai titik pembanding & lapisan median kelurahan. */
export const PRICE_STOPS = [1_000_000, 2_000_000, 3_500_000, 6_000_000, 10_000_000, 20_000_000];
const COLORS = ["#2b6f8f", "#3f9a8a", "#8fb85a", "#e0b23a", "#e07b39", "#c2412d", "#8e1f2b"];
export function priceColor(ppm: number) {
  let i = 0;
  while (i < PRICE_STOPS.length && ppm >= PRICE_STOPS[i]) i++;
  return COLORS[i];
}
export const PRICE_LEGEND = COLORS.map((c, i) => ({
  color: c,
  label: i === 0 ? `< ${PRICE_STOPS[0] / 1e6} jt` : i === COLORS.length - 1 ? `≥ ${PRICE_STOPS[i - 1] / 1e6} jt` : `${PRICE_STOPS[i - 1] / 1e6}–${PRICE_STOPS[i] / 1e6} jt`,
}));
