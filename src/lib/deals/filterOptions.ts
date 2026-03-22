/**
 * Server-side helpers for /deals filter dropdowns.
 * Keeps UX clean without changing Prisma schema or filter query semantics.
 */

export type SubcategoryOption = {
  slug: string;
  name: string;
  categorySlug: string;
  categoryName: string;
};

export type BrandRow = { slug: string; name: string };

/**
 * Subcategory slugs are unique per category in the DB, but the same slug can repeat
 * across categories. When **no** category is selected, the deals query filters by
 * `subcategory.slug` only, so showing one row per slug is correct and removes duplicate
 * labels. When a **category is selected**, show every subcategory row for that category
 * (no cross-category slug collision in DB).
 */
export function filterSubcategoriesForDropdown(
  rows: SubcategoryOption[],
  selectedCategorySlug: string,
): SubcategoryOption[] {
  const scoped = selectedCategorySlug.trim()
    ? rows.filter((sc) => sc.categorySlug === selectedCategorySlug)
    : rows;

  if (selectedCategorySlug.trim()) {
    return [...scoped].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
    );
  }

  const bySlug = new Map<string, SubcategoryOption>();
  const sorted = [...scoped].sort((a, b) => {
    const c = a.categoryName.localeCompare(b.categoryName, undefined, {
      sensitivity: "base",
    });
    if (c !== 0) return c;
    return a.slug.localeCompare(b.slug);
  });
  for (const sc of sorted) {
    if (!bySlug.has(sc.slug)) {
      bySlug.set(sc.slug, sc);
    }
  }
  return Array.from(bySlug.values()).sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
  );
}

/**
 * Core hockey brands first (by slug — matches DB), then everything else A–Z.
 * Slug variants cover common importer / vendor spellings.
 */
const CORE_BRAND_SLUG_PRIORITY: string[] = [
  "bauer",
  "ccm",
  "warrior",
  "true-hockey",
  "true",
  "vaughn",
  "brians",
  "brian-s",
  "sher-wood",
  "sherwood",
  "winnwell",
  "graf",
  "reebok",
];

function coreBrandRank(slug: string): number {
  const s = slug.trim().toLowerCase();
  const idx = CORE_BRAND_SLUG_PRIORITY.indexOf(s);
  return idx === -1 ? CORE_BRAND_SLUG_PRIORITY.length : idx;
}

export function sortBrandsForFilterUi(brands: BrandRow[]): BrandRow[] {
  return [...brands].sort((a, b) => {
    const ra = coreBrandRank(a.slug);
    const rb = coreBrandRank(b.slug);
    if (ra !== rb) return ra - rb;
    return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
  });
}
