import { notFound } from "next/navigation";
import Link from "next/link";
import { formatPriceCents } from "@/lib/money";
import { getDealBySlug, getDealSlugs } from "@/lib/deals";

export async function generateStaticParams() {
  const slugs = await getDealSlugs();
  return slugs.map((slug) => ({ slug }));
}

export default async function DealPage({
  params,
}: {
  params: { slug: string };
}) {
  const deal = await getDealBySlug(params.slug);

  if (!deal) notFound();

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <div className="flex flex-wrap items-center gap-2 text-sm text-black/70">
        <Link href="/deals" className="hover:underline">
          Back to deals
        </Link>
        <span aria-hidden="true">•</span>
        <span>{deal.brand ?? "Deal"}</span>
      </div>

      <h1 className="mt-3 text-balance text-2xl font-bold tracking-tight">
        {deal.title}
      </h1>

      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <div className="text-2xl font-bold">
          {formatPriceCents(deal.priceCents)}
        </div>
        {deal.size ? <div className="text-sm text-black/70">{deal.size}</div> : null}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section className="rounded-2xl border border-black/10 bg-white p-5 shadow-sm lg:col-span-2">
          <h2 className="text-sm font-semibold text-black/80">Details</h2>
          <p className="mt-3 text-sm leading-6 text-black/70">
            {deal.description ?? "No description available."}
          </p>

          <div className="mt-4 flex flex-wrap gap-3 text-xs text-black/70">
            {deal.category ? <span>Category: {deal.category}</span> : null}
            {deal.brand ? <span>Brand: {deal.brand}</span> : null}
            {deal.size ? <span>Size: {deal.size}</span> : null}
          </div>
        </section>

        <aside className="rounded-2xl border border-black/10 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-black/80">Where to buy</h2>
          <p className="mt-3 text-sm text-black/70">
            Use the link below to see the current price on the retailer’s
            site.
          </p>
          <a
            href={deal.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 inline-flex w-full items-center justify-center rounded-xl bg-black px-4 py-3 text-sm font-semibold text-white hover:bg-black/90"
          >
            View deal
          </a>
        </aside>
      </div>
    </div>
  );
}

