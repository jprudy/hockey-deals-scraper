import Link from "next/link";
import { getPrisma } from "@/lib/prisma";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AdminPipelinePage() {
  const prisma = getPrisma();
  const runs = await prisma.pipelineRun.findMany({
    orderBy: { startedAt: "desc" },
    take: 50,
    select: {
      runId: true,
      status: true,
      startedAt: true,
      endedAt: true,
      rowsScrapedTotal: true,
      rowsImportedTotal: true,
      insertedCount: true,
      updatedCount: true,
      lockedSkippedCount: true,
      staleExpiredCount: true,
      errorCount: true,
    },
  });

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Pipeline Runs</h1>
          <p className="mt-2 text-sm text-black/70">
            THS Phase 5A run history.
          </p>
        </div>
        <Link href="/admin" className="text-sm text-blue-700 hover:underline">
          Back to Admin
        </Link>
      </header>

      <section className="mt-8 rounded-2xl border border-black/10 bg-white p-4 shadow-sm">
        <div className="overflow-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-black/10 text-xs uppercase text-black/50">
                <th className="py-2 pr-4">Run ID</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Started</th>
                <th className="py-2 pr-4">Ended</th>
                <th className="py-2 pr-4">Scraped</th>
                <th className="py-2 pr-4">Imported</th>
                <th className="py-2 pr-4">New</th>
                <th className="py-2 pr-4">Updated</th>
                <th className="py-2 pr-4">Locked</th>
                <th className="py-2 pr-4">Expired</th>
                <th className="py-2 pr-4">Errors</th>
                <th className="py-2 pr-4">Details</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.runId} className="border-b border-black/5">
                  <td className="py-3 pr-4 font-mono text-xs">{run.runId}</td>
                  <td className="py-3 pr-4">{run.status}</td>
                  <td className="py-3 pr-4 text-black/70">{run.startedAt.toISOString()}</td>
                  <td className="py-3 pr-4 text-black/70">
                    {run.endedAt ? run.endedAt.toISOString() : "—"}
                  </td>
                  <td className="py-3 pr-4">{run.rowsScrapedTotal}</td>
                  <td className="py-3 pr-4">{run.rowsImportedTotal}</td>
                  <td className="py-3 pr-4">{run.insertedCount}</td>
                  <td className="py-3 pr-4">{run.updatedCount}</td>
                  <td className="py-3 pr-4">{run.lockedSkippedCount}</td>
                  <td className="py-3 pr-4">{run.staleExpiredCount}</td>
                  <td className="py-3 pr-4">{run.errorCount}</td>
                  <td className="py-3 pr-4">
                    <Link
                      href={`/admin/pipeline/${run.runId}`}
                      className="text-blue-700 hover:underline"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
              {runs.length === 0 ? (
                <tr>
                  <td className="py-4 text-black/60" colSpan={12}>
                    No pipeline runs yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
