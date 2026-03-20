export function formatPriceCents(priceCents: number): string {
  const safeCents = Number.isFinite(priceCents) ? priceCents : 0;
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(safeCents / 100);
}

