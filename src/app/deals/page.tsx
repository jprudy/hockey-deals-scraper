import DealCard from "@/components/DealCard";
import DealsFilters from "@/components/DealsFilters";
import { getDeals } from "@/lib/deals";
import { getPrisma } from "@/lib/prisma";
import { sortBrandsForFilterUi } from "@/lib/deals/filterOptions";
import { parseDealsFilters } from "@/lib/deals/dealFilters";
import { Suspense } from "react";
import { unstable_noStore as noStore } from "next/cache";
import Link from "next/link";

// Ensure Next does not static-optimize this page;
// we must respect `searchParams` for URL-driven filtering.
export const dynamic = "force-dynamic";
export const revalidate = 0;
const DEALS_PER_PAGE = 20;

function parsePageParam(value: string | string[] | undefined): number {
  const raw = Array.isArray(value) ? value[0] : value;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1) return 1;
  return Math.floor(n);
}

export default async function DealsPage({
  searchParams,
}: {
  searchParams:
    | Record<string, string | string[] | undefined>
    | Promise<Record<string, string | string[] | undefined>>;
}) {
  noStore();
  const resolvedSearchParams = await searchParams;
  const filters = parseDealsFilters(resolvedSearchParams);
  const requestedPage = parsePageParam(resolvedSearchParams.page);
  const prisma = getPrisma();

  const [categories, brands, retailers, subcategories] = await Promise.all([
    prisma.category.findMany({
      select: { slug: true, name: true },
      orderBy: { name: "asc" },
    }),
    prisma.brand.findMany({
      select: { slug: true, name: true },
      orderBy: { name: "asc" },
    }),
    prisma.retailer.findMany({
      select: { slug: true, name: true },
      orderBy: { name: "asc" },
    }),
    prisma.subcategory.findMany({
      select: {
        slug: true,
        name: true,
        category: { select: { slug: true, name: true } },
      },
      orderBy: { name: "asc" },
    }),
  ]);

  const subcategoryOptions = subcategories.map((sc) => ({
    slug: sc.slug,
    name: sc.name,
    categorySlug: sc.category.slug,
    categoryName: sc.category.name,
  }));

  const brandsSorted = sortBrandsForFilterUi(brands);

  const {
    deals,
    totalCount,
    totalPages,
    currentPage,
  } = await getDeals(filters, {
    page: requestedPage,
    take: DEALS_PER_PAGE,
  });

  function buildPageHref(page: number): string {
    const params = new URLSearchParams();

    for (const [key, value] of Object.entries(resolvedSearchParams)) {
      if (key === "page" || value == null) continue;

      if (Array.isArray(value)) {
        for (const item of value) {
          params.append(key, item);
        }
      } else {
        params.set(key, value);
      }
    }

    params.set("page", String(page));
    return `/deals?${params.toString()}`;
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Deals</h1>
        <p className="mt-2 text-sm text-black/70">
          Browse hockey gear discounts using URL-driven filters.
        </p>
      </header>

      <div className="mt-6">
        <Suspense fallback={<div className="h-[88px] rounded-2xl border border-black/10" />}>
          <DealsFilters
            categories={categories}
            subcategories={subcategoryOptions}
            brands={brandsSorted}
            retailers={retailers}
          />
        </Suspense>
      </div>

      <section className="mt-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {deals.map((deal) => (
            <DealCard key={deal.slug} deal={deal} />
          ))}
        </div>

        <div className="mt-6 flex items-center justify-between rounded-xl border border-black/10 bg-white px-4 py-3 text-sm">
          <div className="text-black/70">
            {totalCount} deal{totalCount === 1 ? "" : "s"} total
          </div>
          <div className="flex items-center gap-3">
            {currentPage > 1 ? (
              <Link
                href={buildPageHref(currentPage - 1)}
                className="rounded-lg border border-black/10 px-3 py-1.5 hover:bg-black/5"
              >
                Previous
              </Link>
            ) : (
              <span className="rounded-lg border border-black/10 px-3 py-1.5 text-black/40">
                Previous
              </span>
            )}

            <span className="text-black/70">
              Page {currentPage} of {totalPages}
            </span>

            {currentPage < totalPages ? (
              <Link
                href={buildPageHref(currentPage + 1)}
                className="rounded-lg border border-black/10 px-3 py-1.5 hover:bg-black/5"
              >
                Next
              </Link>
            ) : (
              <span className="rounded-lg border border-black/10 px-3 py-1.5 text-black/40">
                Next
              </span>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

