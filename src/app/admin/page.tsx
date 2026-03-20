import { getDeals } from "@/lib/deals";
import { formatPriceCents } from "@/lib/money";
import Link from "next/link";

export default async function AdminPage() {
  const { deals } = await getDeals();

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Admin</h1>
        <p className="mt-2 text-sm text-black/70">
          Phase 0 admin shell. Data is currently using mock deals.
        </p>
        <div className="mt-3">
          <Link href="/admin/pipeline" className="text-sm text-blue-700 hover:underline">
            Open Pipeline Runs
          </Link>
        </div>
      </header>

      <section className="mt-8 rounded-2xl border border-black/10 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-black/80">Deals (mock)</h2>
        <div className="mt-4 overflow-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-black/10 text-xs uppercase text-black/50">
                <th className="py-2 pr-4">Title</th>
                <th className="py-2 pr-4">Brand</th>
                <th className="py-2 pr-4">Category</th>
                <th className="py-2 pr-4">Price</th>
                <th className="py-2 pr-4">Slug</th>
              </tr>
            </thead>
            <tbody>
              {deals.map((deal) => (
                <tr key={deal.slug} className="border-b border-black/5">
                  <td className="py-3 pr-4 font-medium text-black/90">
                    {deal.title}
                  </td>
                  <td className="py-3 pr-4 text-black/70">
                    {deal.brand ?? "—"}
                  </td>
                  <td className="py-3 pr-4 text-black/70">
                    {deal.category ?? "—"}
                  </td>
                  <td className="py-3 pr-4 font-semibold">
                    {formatPriceCents(deal.priceCents)}
                  </td>
                  <td className="py-3 pr-4 text-black/60">{deal.slug}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

