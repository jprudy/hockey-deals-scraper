"use client";

import { filterSubcategoriesForDropdown } from "@/lib/deals/filterOptions";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

type Option = { slug: string; name: string };
type SubcategoryOption = {
  slug: string;
  name: string;
  categorySlug: string;
  categoryName: string;
};

type Props = {
  categories: Option[];
  subcategories: SubcategoryOption[];
  brands: Option[];
  retailers: Option[];
};

const STOCK_OPTIONS = [
  { value: "IN_STOCK", label: "In stock" },
  { value: "OUT_OF_STOCK", label: "Out of stock" },
  { value: "PREORDER", label: "Preorder" },
  { value: "UNKNOWN", label: "Unknown" },
] as const;

const SIZE_OPTIONS = ["Youth", "Junior", "Intermediate", "Senior"] as const;

const PRICE_GAP_OPTIONS = [
  { value: "under-25", label: "Under $25" },
  { value: "25-50", label: "$25-$50" },
  { value: "50-100", label: "$50-$100" },
  { value: "100-200", label: "$100-$200" },
  { value: "200-plus", label: "$200+" },
] as const;

type StockValue = (typeof STOCK_OPTIONS)[number]["value"];

export default function DealsFilters({
  categories,
  subcategories,
  brands,
  retailers,
}: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const currentCategory = searchParams.get("category") ?? "";
  const currentSubcategory = searchParams.get("subcategory") ?? "";
  const currentBrand = searchParams.get("brand") ?? "";
  const currentStore = searchParams.get("store") ?? "";
  const currentQuery = searchParams.get("q") ?? "";
  const currentSize = searchParams.get("size") ?? "";
  const currentPriceGap = searchParams.get("priceGap") ?? "";
  const currentStock = (searchParams.get("stock") ?? "") as StockValue | "";
  const currentFeatured = searchParams.get("featured") === "1";
  const currentMinPrice = searchParams.get("minPrice") ?? "";
  const currentMaxPrice = searchParams.get("maxPrice") ?? "";
  const currentSort = searchParams.get("sort") ?? "newest";

  const visibleSubcategories = filterSubcategoriesForDropdown(
    subcategories,
    currentCategory,
  );

  function pushQuery(
    updates: Record<string, string | null | undefined>
  ): void {
    const params = new URLSearchParams(searchParams.toString());
    // Any filter/sort change should restart pagination from page 1.
    params.delete("page");

    for (const [key, value] of Object.entries(updates)) {
      if (value === undefined) continue;
      if (!value) params.delete(key);
      else params.set(key, value);
    }

    const qs = params.toString();
    const nextUrl = qs ? `${pathname}?${qs}` : pathname;
    router.push(nextUrl);
    // Ensure server component data is re-fetched for new searchParams.
    router.refresh();
  }

  return (
    <section className="rounded-2xl border border-black/10 bg-white p-4 shadow-sm">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label className="text-xs font-medium text-black/60">Category</label>
          <select
            value={currentCategory}
            onChange={(e) => {
              const nextCategory = e.target.value;
              pushQuery({
                category: nextCategory || null,
                // keep subcategory consistent with category selection
                subcategory: null,
              });
            }}
            className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
          >
            <option value="">All</option>
            {categories.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-black/60">Brand</label>
          <select
            value={currentBrand}
            onChange={(e) => {
              pushQuery({ brand: e.target.value || null });
            }}
            className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
          >
            <option value="">All</option>
            {brands.map((b) => (
              <option key={b.slug} value={b.slug}>
                {b.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-black/60">Store</label>
          <select
            value={currentStore}
            onChange={(e) => {
              pushQuery({ store: e.target.value || null });
            }}
            className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
          >
            <option value="">All</option>
            {retailers.map((r) => (
              <option key={r.slug} value={r.slug}>
                {r.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-black/60">Subcategory</label>
          <select
            value={currentSubcategory}
            onChange={(e) => {
              pushQuery({ subcategory: e.target.value || null });
            }}
            className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
          >
            <option value="">All</option>
            {visibleSubcategories.map((sc) => (
              <option key={`${sc.categorySlug}:${sc.slug}`} value={sc.slug}>
                {sc.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-black/60">
            Stock status
          </label>
          <select
            value={currentStock}
            onChange={(e) => {
              pushQuery({ stock: e.target.value || null });
            }}
            className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
          >
            <option value="">Any</option>
            {STOCK_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-black/60">Keyword</label>
          <input
            defaultValue={currentQuery}
            onBlur={(e) => {
              pushQuery({ q: e.target.value.trim() || null });
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                pushQuery({ q: (e.currentTarget.value || "").trim() || null });
              }
            }}
            className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
            placeholder="Search title or description"
          />
        </div>

        <div>
          <label className="text-xs font-medium text-black/60">Sort</label>
          <select
            value={currentSort}
            onChange={(e) => {
              pushQuery({ sort: e.target.value || "newest" });
            }}
            className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
          >
            <option value="newest">Newest</option>
            <option value="discount">Discount</option>
            <option value="price_asc">Price: Low</option>
            <option value="price_desc">Price: High</option>
          </select>
        </div>

        <div>
          <label className="text-xs font-medium text-black/60">Size</label>
          <select
            value={currentSize}
            onChange={(e) => {
              pushQuery({ size: e.target.value || null });
            }}
            className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
          >
            <option value="">All</option>
            {SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center justify-between gap-3">
          <div>
            <label className="text-xs font-medium text-black/60">Featured</label>
          </div>
          <input
            type="checkbox"
            checked={currentFeatured}
            onChange={(e) => {
              pushQuery({ featured: e.target.checked ? "1" : null });
            }}
            aria-label="Featured only"
          />
        </div>

        <div>
          <label className="text-xs font-medium text-black/60">
            Price range ($ CAD)
          </label>
          <select
            value={currentPriceGap}
            onChange={(e) => {
              pushQuery({ priceGap: e.target.value || null });
            }}
            className="mt-1 w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
          >
            <option value="">All</option>
            {PRICE_GAP_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <div className="mt-1 flex gap-2">
            <input
              type="number"
              defaultValue={currentMinPrice}
              onBlur={(e) => {
                pushQuery({ minPrice: e.target.value || null });
              }}
              className="w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
              placeholder="min $"
            />
            <input
              type="number"
              defaultValue={currentMaxPrice}
              onBlur={(e) => {
                pushQuery({ maxPrice: e.target.value || null });
              }}
              className="w-full rounded-xl border border-black/10 bg-white px-3 py-2 text-sm"
              placeholder="max $"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

