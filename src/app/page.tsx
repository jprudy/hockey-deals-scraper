import DealCard from "@/components/DealCard";
import { getFeaturedDeals } from "@/lib/deals";
import Link from "next/link";

export default async function Home() {
  const featured = await getFeaturedDeals();

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <section className="rounded-2xl border border-black/10 bg-white p-6 shadow-sm">
        <h1 className="text-balance text-2xl font-bold tracking-tight">
          Canadian hockey deals, gathered in one place.
        </h1>
        <p className="mt-2 text-sm text-black/70">
          Live deals from the database. Next we’ll wire filters and Prisma/Postgres.
        </p>

        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            href="/deals"
            className="inline-flex h-10 items-center justify-center rounded-xl bg-black px-4 text-sm font-semibold text-white hover:bg-black/90"
          >
            Browse deals
          </Link>
          <Link
            href="/admin"
            className="inline-flex h-10 items-center justify-center rounded-xl border border-black/10 px-4 text-sm font-semibold text-black/90 hover:bg-black/5"
          >
            Admin
          </Link>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Featured deals</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {featured.map((deal) => (
            <DealCard key={deal.slug} deal={deal} />
          ))}
        </div>
      </section>
    </div>
  );
}
