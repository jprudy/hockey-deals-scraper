import { createPrismaClient } from "./prisma_client";

function argValue(flag: string): string | undefined {
  const idx = process.argv.indexOf(flag);
  if (idx === -1 || idx + 1 >= process.argv.length) return undefined;
  return process.argv[idx + 1];
}

type Payload = Record<string, unknown>;

function asStatus(value: unknown): string {
  const text = String(value || "").toUpperCase();
  if (text === "RUNNING") return "RUNNING";
  if (text === "SUCCESS") return "SUCCESS";
  if (text === "PARTIAL_SUCCESS") return "PARTIAL_SUCCESS";
  return "FAILED";
}

function asIntakeType(value: unknown): string {
  const text = String(value || "").toUpperCase();
  if (text === "MANUAL") return "MANUAL";
  if (text === "API") return "API";
  return "SCRAPED";
}

async function startRun(prisma: PrismaClient, payload: Payload): Promise<void> {
  const runId = String(payload.runId);
  const startedAt = payload.startedAt ? new Date(String(payload.startedAt)) : new Date();
  const intakeType = asIntakeType(payload.intakeType);
  const sourceStore = String(payload.sourceStore ?? "thehockeyshop");

  await prisma.pipelineRun.upsert({
    where: { runId },
    create: {
      runId,
      status: "RUNNING" as any,
      startedAt,
      intakeTypesUsed: [intakeType.toLowerCase()],
      scrapersTotal: 1,
    },
    update: {
      status: "RUNNING" as any,
      startedAt,
      intakeTypesUsed: [intakeType.toLowerCase()],
      scrapersTotal: 1,
    },
  });

  const run = await prisma.pipelineRun.findUniqueOrThrow({ where: { runId }, select: { id: true } });

  await prisma.pipelineRunIntakeJob.upsert({
    where: {
      pipelineRunId_intakeType_sourceStore: {
        pipelineRunId: run.id,
        intakeType: intakeType as any,
        sourceStore,
      },
    },
    create: {
      pipelineRunId: run.id,
      intakeType: intakeType as any,
      sourceStore,
      status: "RUNNING" as any,
    },
    update: {
      status: "RUNNING" as any,
    },
  });
}

async function updateIntakeJob(prisma: PrismaClient, payload: Payload): Promise<void> {
  const runId = String(payload.runId);
  const intakeType = asIntakeType(payload.intakeType);
  const sourceStore = String(payload.sourceStore ?? "thehockeyshop");
  const status = asStatus(payload.status);

  const run = await prisma.pipelineRun.findUniqueOrThrow({ where: { runId }, select: { id: true } });

  await prisma.pipelineRunIntakeJob.upsert({
    where: {
      pipelineRunId_intakeType_sourceStore: {
        pipelineRunId: run.id,
        intakeType: intakeType as any,
        sourceStore,
      },
    },
    create: {
      pipelineRunId: run.id,
      intakeType: intakeType as any,
      sourceStore,
      status,
      rowsProduced: Number(payload.rowsProduced ?? 0),
      rowsAccepted: Number(payload.rowsAccepted ?? 0),
      logPath: payload.logPath ? String(payload.logPath) : null,
      outputPath: payload.outputPath ? String(payload.outputPath) : null,
      errorMessage: payload.errorMessage ? String(payload.errorMessage) : null,
    },
    update: {
      status,
      rowsProduced: Number(payload.rowsProduced ?? 0),
      rowsAccepted: Number(payload.rowsAccepted ?? 0),
      logPath: payload.logPath ? String(payload.logPath) : null,
      outputPath: payload.outputPath ? String(payload.outputPath) : null,
      errorMessage: payload.errorMessage ? String(payload.errorMessage) : null,
    },
  });
}

async function finalizeRun(prisma: PrismaClient, payload: Payload): Promise<void> {
  const runId = String(payload.runId);
  const status = asStatus(payload.status);
  const endedAt = payload.endedAt ? new Date(String(payload.endedAt)) : new Date();

  await prisma.pipelineRun.update({
    where: { runId },
    data: {
      status,
      endedAt,
      scrapersSucceeded: status === "SUCCESS" ? 1 : 0,
      scrapersFailed: status === "SUCCESS" ? 0 : 1,
      rowsScrapedTotal: Number(payload.rowsScrapedTotal ?? 0),
      rowsImportedTotal: Number(payload.rowsImportedTotal ?? 0),
      insertedCount: Number(payload.insertedCount ?? 0),
      updatedCount: Number(payload.updatedCount ?? 0),
      lockedSkippedCount: Number(payload.lockedSkippedCount ?? 0),
      staleExpiredCount: Number(payload.staleExpiredCount ?? 0),
      errorCount: Number(payload.errorCount ?? 0),
      errorSummary: payload.errorSummary ?? null,
    },
  });
}

async function main(): Promise<number> {
  const action = argValue("--action");
  const payloadRaw = argValue("--payload");
  if (!action || !payloadRaw) {
    console.error("Missing --action and/or --payload");
    return 1;
  }

  const payload = JSON.parse(payloadRaw) as Payload;
  const prisma = createPrismaClient();

  try {
    if (action === "start_run") {
      await startRun(prisma, payload);
    } else if (action === "update_intake_job") {
      await updateIntakeJob(prisma, payload);
    } else if (action === "finalize_run") {
      await finalizeRun(prisma, payload);
    } else {
      console.error(`Unknown action: ${action}`);
      return 1;
    }
  } finally {
    await prisma.$disconnect();
  }

  return 0;
}

main()
  .then((code) => process.exit(code))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
