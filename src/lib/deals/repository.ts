import { getPrisma } from "@/lib/prisma";
import type { Deal } from "./types";
import type { DealsFilters } from "./dealFilters";

export type DealsPagination = {
  page: number;
  take: number;
};

export type DealsListResult = {
  deals: Deal[];
  totalCount: number;
  totalPages: number;
  currentPage: number;
};

type DealDbShape = {
  slug: string;
  title: string;
  salePriceCents: number | null;
  originalPriceCents: number | null;
  discountPercent: number | null;
  imageUrl: string | null;
  brand: { name: string } | null;
  category: { name: string } | null;
  size: string | null;
  affiliateUrl: string | null;
  retailerUrl: string | null;
  description: string | null;
};

function mapDbDealToDeal(dbDeal: DealDbShape): Deal {
  const priceCents = dbDeal.salePriceCents ?? dbDeal.originalPriceCents ?? 0;
  return {
    slug: dbDeal.slug,
    title: dbDeal.title,
    brand: dbDeal.brand?.name ?? undefined,
    category: dbDeal.category?.name ?? undefined,
    priceCents,
    salePriceCents: dbDeal.salePriceCents ?? undefined,
    originalPriceCents: dbDeal.originalPriceCents ?? undefined,
    discountPercent: dbDeal.discountPercent ?? undefined,
    imageUrl: dbDeal.imageUrl ?? undefined,
    size: dbDeal.size ?? undefined,
    url: dbDeal.affiliateUrl ?? dbDeal.retailerUrl ?? "#",
    description: dbDeal.description ?? undefined,
  };
}

export async function getDeals(
  filters: DealsFilters = {},
  pagination?: Partial<DealsPagination>
): Promise<DealsListResult> {
  const prisma = getPrisma();

  type FindManyArgs = NonNullable<Parameters<typeof prisma.deal.findMany>[0]>;
  const where: FindManyArgs["where"] = { status: "ACTIVE" };

  if (filters.category) {
    where.category = { slug: filters.category };
  }
  if (filters.subcategory) {
    // If category is present, also scope the subcategory to avoid ambiguity.
    where.subcategory = filters.category
      ? { slug: filters.subcategory, category: { slug: filters.category } }
      : { slug: filters.subcategory };
  }
  if (filters.brand) {
    where.brand = { slug: filters.brand };
  }
  if (filters.store) {
    where.retailer = { slug: filters.store };
  }
  if (filters.q) {
    where.OR = [
      { title: { contains: filters.q, mode: "insensitive" } },
      { description: { contains: filters.q, mode: "insensitive" } },
    ];
  }
  if (filters.size) {
    where.size = filters.size;
  }
  if (filters.stock) {
    where.stockStatus = filters.stock;
  }
  if (filters.featured === true) {
    where.isFeatured = true;
  }
  if (filters.minPrice != null || filters.maxPrice != null) {
    where.salePriceCents = {
      ...(filters.minPrice != null ? { gte: filters.minPrice } : {}),
      ...(filters.maxPrice != null ? { lte: filters.maxPrice } : {}),
    };
  }

  const sort = filters.sort ?? "newest";
  const orderBy: FindManyArgs["orderBy"] =
    (() => {
      switch (sort) {
        case "discount":
          return { discountPercent: "desc" };
        case "price_asc":
          return { salePriceCents: "asc" };
        case "price_desc":
          return { salePriceCents: "desc" };
        case "newest":
        default:
          return { lastSeenAt: "desc" };
      }
    })();

  const pageSizeRaw = pagination?.take ?? filters.take ?? 100;
  const pageSize = Number.isFinite(pageSizeRaw) && pageSizeRaw > 0 ? Math.floor(pageSizeRaw) : 100;
  const requestedPageRaw = pagination?.page ?? 1;
  const requestedPage =
    Number.isFinite(requestedPageRaw) && requestedPageRaw > 0
      ? Math.floor(requestedPageRaw)
      : 1;
  const totalCount = await prisma.deal.count({ where });
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const currentPage = Math.min(requestedPage, totalPages);
  const skip = (currentPage - 1) * pageSize;

  const deals = await prisma.deal.findMany({
    where,
    include: {
      brand: { select: { name: true } },
      category: { select: { name: true } },
    },
    orderBy,
    skip,
    take: pageSize,
  });

  return {
    deals: deals.map(mapDbDealToDeal),
    totalCount,
    totalPages,
    currentPage,
  };
}

export async function getDealBySlug(slug: string | undefined): Promise<Deal | null> {
  if (!slug) return null;
  const prisma = getPrisma();

  const deal = await prisma.deal.findUnique({
    where: { slug },
    include: {
      brand: { select: { name: true } },
      category: { select: { name: true } },
    },
  });

  if (!deal || deal.status !== "ACTIVE") return null;
  return mapDbDealToDeal(deal);
}

export async function getDealSlugs(): Promise<string[]> {
  const prisma = getPrisma();

  const deals = await prisma.deal.findMany({
    where: { status: "ACTIVE" },
    select: { slug: true },
  });

  return deals.map((d) => d.slug);
}

export async function getFeaturedDeals(): Promise<Deal[]> {
  const { deals } = await getDeals({ featured: true, sort: "newest" }, { page: 1, take: 3 });
  return deals;
}

