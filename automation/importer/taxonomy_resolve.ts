import type { PrismaClient } from "../../src/generated/prisma/client";
import {
  CATEGORY_DISPLAY_BY_SLUG,
  normalizeFoldKey,
  resolveCategorySlugFromRaw,
  resolveSubcategoryDisplayLabel,
  slugifyTaxonomy,
} from "./taxonomy_maps";

/** Normalized CSV / rows.json row shape (subset). */
export type TaxonomyRow = {
  source?: string;
  source_store?: string;
  brand?: string;
  category?: string;
  subcategory?: string;
  size?: string;
  run_id?: string;
};

const KNOWN_RETAILERS: Record<
  string,
  { slug: string; name: string; websiteUrl?: string | null }
> = {
  thehockeyshop: {
    slug: "thehockeyshop",
    name: "The Hockey Shop",
    websiteUrl: "https://www.thehockeyshop.com",
  },
  sourceforsports: {
    slug: "sourceforsports",
    name: "Source for Sports",
    websiteUrl: null,
  },
  sportexcellence: {
    slug: "sportexcellence",
    name: "Sport Excellence",
    websiteUrl: null,
  },
};

const DEAL_FILTER_SIZES = new Set(["Youth", "Junior", "Intermediate", "Senior"]);

const SIZE_ALIASES: Record<string, string> = {
  youth: "Youth",
  yth: "Youth",
  junior: "Junior",
  jr: "Junior",
  intermediate: "Intermediate",
  int: "Intermediate",
  intermidiate: "Intermediate",
  senior: "Senior",
  sr: "Senior",
};

export type TaxonomyCaches = {
  retailer: Map<string, string | null>;
  brand: Map<string, string | null>;
  category: Map<string, string | null>;
  subcategory: Map<string, string | null>;
};

export type TaxonomyReviewEntry = {
  run_id: string;
  source_store: string;
  raw_category: string;
  raw_subcategory: string;
  normalized_category_slug: string | null;
  normalized_subcategory: string | null;
  reason: string;
};

/** Deduped review lines for tuning alias maps (written once per import). */
export class TaxonomyReviewBuffer {
  private readonly list: TaxonomyReviewEntry[] = [];
  private readonly seen = new Set<string>();

  add(entry: TaxonomyReviewEntry): void {
    const key = [
      entry.reason,
      entry.raw_category,
      entry.raw_subcategory,
      entry.normalized_category_slug ?? "",
      entry.normalized_subcategory ?? "",
    ].join("|");
    if (this.seen.has(key)) return;
    this.seen.add(key);
    this.list.push(entry);
  }

  toArray(): readonly TaxonomyReviewEntry[] {
    return this.list;
  }
}

export function createTaxonomyCaches(): TaxonomyCaches {
  return {
    retailer: new Map(),
    brand: new Map(),
    category: new Map(),
    subcategory: new Map(),
  };
}

/**
 * Persisted store key for Deal.sourceStore, stale matching, and retailer resolution.
 * Never use scraper `source` codes like "ths" here.
 */
export function normalizeCanonicalSourceStore(row: TaxonomyRow): string {
  const raw = (row.source_store || "").trim().toLowerCase();
  if (raw) return raw;
  const src = (row.source || "").trim().toLowerCase();
  if (src === "ths") return "thehockeyshop";
  return src;
}

export function normalizeDealFilterSize(raw: string | undefined): string | null {
  if (!raw) return null;
  const t = raw.trim();
  if (!t) return null;
  if (DEAL_FILTER_SIZES.has(t)) return t;
  const mapped = SIZE_ALIASES[t.toLowerCase().replace(/\.$/, "")];
  return mapped && DEAL_FILTER_SIZES.has(mapped) ? mapped : null;
}

export async function resolveRetailerId(
  prisma: PrismaClient,
  cache: Map<string, string | null>,
  canonicalStore: string,
): Promise<string | null> {
  if (!canonicalStore) return null;
  if (cache.has(canonicalStore)) return cache.get(canonicalStore)!;

  const known = KNOWN_RETAILERS[canonicalStore];
  if (known) {
    const r = await prisma.retailer.upsert({
      where: { slug: known.slug },
      update: {},
      create: {
        slug: known.slug,
        name: known.name,
        websiteUrl: known.websiteUrl ?? null,
      },
    });
    cache.set(canonicalStore, r.id);
    return r.id;
  }

  const existing = await prisma.retailer.findUnique({
    where: { slug: canonicalStore },
  });
  const id = existing?.id ?? null;
  cache.set(canonicalStore, id);
  return id;
}

export async function resolveBrandId(
  prisma: PrismaClient,
  cache: Map<string, string | null>,
  raw: string | undefined,
): Promise<string | null> {
  const name = (raw || "").trim();
  if (!name) return null;
  const lower = name.toLowerCase();
  if (lower === "other" || lower === "unknown") return null;

  const cacheKey = `n:${lower}`;
  if (cache.has(cacheKey)) return cache.get(cacheKey)!;

  const slug = slugifyTaxonomy(name);
  const existing = await prisma.brand.findFirst({
    where: {
      OR: [{ slug }, { name: { equals: name, mode: "insensitive" } }],
    },
  });
  if (existing) {
    cache.set(cacheKey, existing.id);
    return existing.id;
  }

  try {
    const created = await prisma.brand.create({
      data: { slug, name },
    });
    cache.set(cacheKey, created.id);
    return created.id;
  } catch {
    const retry = await prisma.brand.findFirst({
      where: {
        OR: [{ slug }, { name: { equals: name, mode: "insensitive" } }],
      },
    });
    const id = retry?.id ?? null;
    cache.set(cacheKey, id);
    return id;
  }
}

/**
 * Resolve allowlisted category only. Creates row only for known slug + display name map.
 */
export async function resolveCategoryIdControlled(
  prisma: PrismaClient,
  cache: Map<string, string | null>,
  categorySlug: string,
): Promise<string | null> {
  if (cache.has(categorySlug)) return cache.get(categorySlug)!;

  const displayName = CATEGORY_DISPLAY_BY_SLUG[categorySlug];
  if (!displayName) {
    cache.set(categorySlug, null);
    return null;
  }

  const existing = await prisma.category.findUnique({
    where: { slug: categorySlug },
  });
  if (existing) {
    cache.set(categorySlug, existing.id);
    return existing.id;
  }

  try {
    const created = await prisma.category.create({
      data: { slug: categorySlug, name: displayName },
    });
    cache.set(categorySlug, created.id);
    return created.id;
  } catch {
    const retry = await prisma.category.findUnique({
      where: { slug: categorySlug },
    });
    const id = retry?.id ?? null;
    cache.set(categorySlug, id);
    return id;
  }
}

/**
 * Subcategory: normalize label via alias map, then find or create under parent category.
 */
export async function resolveSubcategoryIdNormalized(
  prisma: PrismaClient,
  cache: Map<string, string | null>,
  categoryId: string | null,
  raw: string | undefined,
): Promise<string | null> {
  if (!categoryId) return null;

  const displayLabel = resolveSubcategoryDisplayLabel(raw);
  if (!displayLabel) return null;

  const cacheKey = `s:${categoryId}:${normalizeFoldKey(displayLabel)}`;
  if (cache.has(cacheKey)) return cache.get(cacheKey)!;

  const slug = slugifyTaxonomy(displayLabel);
  const existing = await prisma.subcategory.findFirst({
    where: {
      categoryId,
      OR: [{ slug }, { name: { equals: displayLabel, mode: "insensitive" } }],
    },
  });
  if (existing) {
    cache.set(cacheKey, existing.id);
    return existing.id;
  }

  try {
    const created = await prisma.subcategory.create({
      data: { categoryId, slug, name: displayLabel },
    });
    cache.set(cacheKey, created.id);
    return created.id;
  } catch {
    const retry = await prisma.subcategory.findFirst({
      where: {
        categoryId,
        OR: [{ slug }, { name: { equals: displayLabel, mode: "insensitive" } }],
      },
    });
    const id = retry?.id ?? null;
    cache.set(cacheKey, id);
    return id;
  }
}

export type DealTaxonomyResolution = {
  canonicalSourceStore: string;
  retailerId: string | null;
  brandId: string | null;
  categoryId: string | null;
  subcategoryId: string | null;
  size: string | null;
};

export async function resolveDealTaxonomy(
  prisma: PrismaClient,
  caches: TaxonomyCaches,
  row: TaxonomyRow,
  options?: {
    runId: string;
    review?: TaxonomyReviewBuffer;
  },
): Promise<DealTaxonomyResolution> {
  const runId = options?.runId ?? row.run_id ?? "";
  const review = options?.review;

  const canonicalSourceStore = normalizeCanonicalSourceStore(row);
  const retailerId = await resolveRetailerId(
    prisma,
    caches.retailer,
    canonicalSourceStore,
  );
  const brandId = await resolveBrandId(prisma, caches.brand, row.brand);

  const rawCategory = (row.category || "").trim();
  const rawSubcategory = (row.subcategory || "").trim();
  const categorySlug = resolveCategorySlugFromRaw(rawCategory);

  let categoryId: string | null = null;
  if (categorySlug) {
    categoryId = await resolveCategoryIdControlled(
      prisma,
      caches.category,
      categorySlug,
    );
  } else if (normalizeFoldKey(rawCategory) && review && runId) {
    review.add({
      run_id: runId,
      source_store: canonicalSourceStore,
      raw_category: rawCategory,
      raw_subcategory: rawSubcategory,
      normalized_category_slug: null,
      normalized_subcategory: resolveSubcategoryDisplayLabel(rawSubcategory),
      reason: "unknown_category",
    });
  }

  const subcategoryId = await resolveSubcategoryIdNormalized(
    prisma,
    caches.subcategory,
    categoryId,
    row.subcategory,
  );

  if (
    !categoryId &&
    normalizeFoldKey(rawSubcategory) &&
    review &&
    runId &&
    !normalizeFoldKey(rawCategory)
  ) {
    review.add({
      run_id: runId,
      source_store: canonicalSourceStore,
      raw_category: rawCategory,
      raw_subcategory: rawSubcategory,
      normalized_category_slug: null,
      normalized_subcategory: resolveSubcategoryDisplayLabel(rawSubcategory),
      reason: "subcategory_skipped_no_category",
    });
  }

  const size = normalizeDealFilterSize(row.size);

  return {
    canonicalSourceStore,
    retailerId,
    brandId,
    categoryId,
    subcategoryId,
    size,
  };
}
