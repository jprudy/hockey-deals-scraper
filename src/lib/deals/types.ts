export type Deal = {
  slug: string;
  title: string;
  brand?: string;
  category?: string;
  priceCents: number;
  salePriceCents?: number;
  originalPriceCents?: number;
  discountPercent?: number;
  imageUrl?: string;
  size?: string;
  url: string;
  description?: string;
};

