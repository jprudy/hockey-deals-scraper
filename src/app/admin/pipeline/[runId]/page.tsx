import Link from "next/link";
import { notFound } from "next/navigation";
import { getPrisma } from "@/lib/prisma";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function AdminPipelineRunDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  const prisma = getPrisma();

  const run = await prisma.pipelineRun.findUnique({
    where: { runId },
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
      errorSummary: true,
      intakeJobs: {
        orderBy: { createdAt: "asc" },
        select: {
          intakeType: true,
          sourceStore: true,
          status: true,
          rowsProduced: true,
          rowsAccepted: true,
          outputPath: true,
          logPath: true,
          errorMessage: true,
        },
      },
    },
  });

  if (!run) notFound();

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Pipeline Run</h1>
          <p className="mt-2 font-mono text-xs text-black/70">{run.runId}</p>
        </div>
        <Link href="/admin/pipeline" className="text-sm text-blue-700 hover:underline">
          Back to Pipeline
        </Link>
      </header>

      <section className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-black/10 p-3">
          <div className="text-xs uppercase text-black/50">Status</div>
          <div className="mt-1 font-semibold">{run.status}</div>
        </div>
        <div className="rounded-xl border border-black/10 p-3">
          <div className="text-xs uppercase text-black/50">Rows Scraped</div>
          <div className="mt-1 font-semibold">{run.rowsScrapedTotal}</div>
        </div>
        <div className="rounded-xl border border-black/10 p-3">
          <div className="text-xs uppercase text-black/50">Rows Imported</div>
          <div className="mt-1 font-semibold">{run.rowsImportedTotal}</div>
        </div>
        <div className="rounded-xl border border-black/10 p-3">
          <div className="text-xs uppercase text-black/50">Errors</div>
          <div className="mt-1 font-semibold">{run.errorCount}</div>
        </div>
        <div className="rounded-xl border border-black/10 p-3">
          <div className="text-xs uppercase text-black/50">New</div>
          <div className="mt-1 font-semibold">{run.insertedCount}</div>
        </div>
        <div className="rounded-xl border border-black/10 p-3">
          <div className="text-xs uppercase text-black/50">Updated</div>
          <div className="mt-1 font-semibold">{run.updatedCount}</div>
        </div>
        <div className="rounded-xl border border-black/10 p-3">
          <div className="text-xs uppercase text-black/50">Locked Skipped</div>
          <div className="mt-1 font-semibold">{run.lockedSkippedCount}</div>
        </div>
        <div className="rounded-xl border border-black/10 p-3">
          <div className="text-xs uppercase text-black/50">Expired</div>
          <div className="mt-1 font-semibold">{run.staleExpiredCount}</div>
        </div>
      </section>

      <section className="mt-8 rounded-2xl border border-black/10 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-black/80">Intake Jobs</h2>
        <div className="mt-4 overflow-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-black/10 text-xs uppercase text-black/50">
                <th className="py-2 pr-4">Intake Type</th>
                <th className="py-2 pr-4">Source</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Rows Produced</th>
                <th className="py-2 pr-4">Rows Accepted</th>
                <th className="py-2 pr-4">Output Path</th>
                <th className="py-2 pr-4">Log Path</th>
                <th className="py-2 pr-4">Error</th>
              </tr>
            </thead>
            <tbody>
              {run.intakeJobs.map((job) => (
                <tr
                  key={`${job.intakeType}-${job.sourceStore}`}
                  className="border-b border-black/5"
                >
                  <td className="py-3 pr-4">{job.intakeType}</td>
                  <td className="py-3 pr-4">{job.sourceStore}</td>
                  <td className="py-3 pr-4">{job.status}</td>
                  <td className="py-3 pr-4">{job.rowsProduced}</td>
                  <td className="py-3 pr-4">{job.rowsAccepted}</td>
                  <td className="py-3 pr-4 font-mono text-xs text-black/70">
                    {job.outputPath ?? "—"}
                  </td>
                  <td className="py-3 pr-4 font-mono text-xs text-black/70">
                    {job.logPath ?? "—"}
                  </td>
                  <td className="py-3 pr-4 text-black/70">{job.errorMessage ?? "—"}</td>
                </tr>
              ))}
              {run.intakeJobs.length === 0 ? (
                <tr>
                  <td className="py-4 text-black/60" colSpan={8}>
                    No intake jobs for this run.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-8 rounded-2xl border border-black/10 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-black/80">Run Metadata</h2>
        <dl className="mt-3 space-y-2 text-sm">
          <div>
            <dt className="text-black/50">Started</dt>
            <dd>{run.startedAt.toISOString()}</dd>
          </div>
          <div>
            <dt className="text-black/50">Ended</dt>
            <dd>{run.endedAt ? run.endedAt.toISOString() : "—"}</dd>
          </div>
          <div>
            <dt className="text-black/50">Error Summary</dt>
            <dd className="rounded-md bg-black/5 p-2 font-mono text-xs">
              {run.errorSummary ? JSON.stringify(run.errorSummary) : "{}"}
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
