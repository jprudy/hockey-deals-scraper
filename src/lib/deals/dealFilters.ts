import type {
  StockStatus,
} from "@/generated/prisma/enums";

export type DealsSort = "newest" | "discount" | "price_asc" | "price_desc";
export type DealSize = "Youth" | "Junior" | "Intermediate" | "Senior";
export type PriceGap =
  | "under-25"
  | "25-50"
  | "50-100"
  | "100-200"
  | "200-plus";

export type DealsFilters = {
  category?: string;
  subcategory?: string;
  brand?: string;
  store?: string; // retailer slug
  size?: DealSize;
  q?: string;
  stock?: StockStatus;
  featured?: boolean;
  minPrice?: number; // salePriceCents
  maxPrice?: number; // salePriceCents
  priceGap?: PriceGap;
  sort?: DealsSort;
  take?: number;
};

const STOCK_VALUES: Record<string, StockStatus> = {
  IN_STOCK: "IN_STOCK",
  OUT_OF_STOCK: "OUT_OF_STOCK",
  PREORDER: "PREORDER",
  UNKNOWN: "UNKNOWN",
};

const SIZE_VALUES: Record<string, DealSize> = {
  Youth: "Youth",
  Junior: "Junior",
  Intermediate: "Intermediate",
  Senior: "Senior",
};

const PRICE_GAP_VALUES: Record<string, PriceGap> = {
  "under-25": "under-25",
  "25-50": "25-50",
  "50-100": "50-100",
  "100-200": "100-200",
  "200-plus": "200-plus",
};

function getFirst(
  searchParams: Record<string, string | string[] | undefined>,
  key: string
): string | undefined {
  const v = searchParams[key];
  if (Array.isArray(v)) return v[0];
  return v;
}

function parseBoolean(value: string | undefined): boolean | undefined {
  if (!value) return undefined;
  const normalized = value.toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "off"].includes(normalized)) return false;
  return undefined;
}

function parseDollarsToCents(value: string | undefined): number | undefined {
  if (!value) return undefined;
  const n = Number(value);
  if (!Number.isFinite(n)) return undefined;
  if (n < 0) return undefined;
  return Math.round(n * 100);
}

export function priceGapToRangeCents(
  priceGap: PriceGap
): { minPrice?: number; maxPrice?: number } {
  switch (priceGap) {
    case "under-25":
      return { maxPrice: 2500 };
    case "25-50":
      return { minPrice: 2500, maxPrice: 5000 };
    case "50-100":
      return { minPrice: 5000, maxPrice: 10000 };
    case "100-200":
      return { minPrice: 10000, maxPrice: 20000 };
    case "200-plus":
      return { minPrice: 20000 };
    default:
      return {};
  }
}

export function parseDealsFilters(
  searchParams: Record<string, string | string[] | undefined>
): DealsFilters {
  const category = getFirst(searchParams, "category");
  const subcategory = getFirst(searchParams, "subcategory");
  const brand = getFirst(searchParams, "brand");
  const store = getFirst(searchParams, "store");
  const q = getFirst(searchParams, "q")?.trim();
  const size = getFirst(searchParams, "size");
  const stockRaw = getFirst(searchParams, "stock");
  const featured = parseBoolean(getFirst(searchParams, "featured"));
  const minPriceManual = parseDollarsToCents(getFirst(searchParams, "minPrice"));
  const maxPriceManual = parseDollarsToCents(getFirst(searchParams, "maxPrice"));
  const priceGapRaw = getFirst(searchParams, "priceGap");
  const sortRaw = getFirst(searchParams, "sort");

  const parsedSize =
    size && size in SIZE_VALUES ? (SIZE_VALUES[size] as DealSize) : undefined;

  const stock =
    stockRaw && stockRaw in STOCK_VALUES
      ? (STOCK_VALUES[stockRaw] as StockStatus)
      : undefined;

  const priceGap =
    priceGapRaw && priceGapRaw in PRICE_GAP_VALUES
      ? (PRICE_GAP_VALUES[priceGapRaw] as PriceGap)
      : undefined;

  // Priority rule:
  // - If manual min/max exists, use those values.
  // - Otherwise, use the selected priceGap mapped range.
  const hasManualPrice = minPriceManual != null || maxPriceManual != null;
  const gapRange =
    !hasManualPrice && priceGap ? priceGapToRangeCents(priceGap) : {};
  const minPrice =
    minPriceManual != null ? minPriceManual : gapRange.minPrice;
  const maxPrice =
    maxPriceManual != null ? maxPriceManual : gapRange.maxPrice;

  const sort: DealsSort | undefined = (() => {
    switch (sortRaw) {
      case "newest":
      case "discount":
      case "price_asc":
      case "price_desc":
        return sortRaw;
      default:
        return undefined;
    }
  })();

  return {
    category: category || undefined,
    subcategory: subcategory || undefined,
    brand: brand || undefined,
    store: store || undefined,
    q: q || undefined,
    size: parsedSize,
    stock,
    featured,
    minPrice,
    maxPrice,
    priceGap,
    sort: sort || "newest",
  };
}

