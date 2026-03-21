import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createPrismaClient } from "./prisma_client";

type Row = {
  run_id: string;
  scraped_at: string;
  import_source: string;
  source?: string;
  external_key: string;
  source_store: string;
  source_url: string;
  source_product_id?: string;
  title: string;
  price: string;
  sale_price?: string;
  currency: string;
  in_stock: string;
  stock_text?: string;
  image_url?: string;
  description?: string;
};

type Summary = {
  run_id: string;
  rows_read: number;
  inserted: number;
  updated_unlocked: number;
  locked_seen_only: number;
  stale_incremented: number;
  inactivated: number;
  errors: number;
};

function argValue(flag: string): string | undefined {
  const idx = process.argv.indexOf(flag);
  if (idx === -1 || idx + 1 >= process.argv.length) return undefined;
  return process.argv[idx + 1];
}

function toCents(value: string | undefined): number | null {
  if (!value || value.trim() === "") return null;
  const n = Number(value);
  if (Number.isNaN(n)) return null;
  return Math.round(n * 100);
}

function toSourceType(importSource: string): string {
  if (importSource === "manual") {
    return "MANUAL";
  }
  if (importSource === "scraped" || importSource === "api") {
    return "SCRAPER";
  }
  return "SCRAPER";
}

async function main(): Promise<number> {
  const rowsArg = argValue("--rows");
  const runId = argValue("--run-id");
  const staleThresholdArg = argValue("--stale-threshold") ?? "2";
  const summaryArg = argValue("--summary");

  if (!rowsArg || !runId || !summaryArg) {
    console.error("Missing required args --rows --run-id --summary");
    return 1;
  }

  const staleThreshold = Number(staleThresholdArg);
  const rowsPath = resolve(rowsArg);
  const summaryPath = resolve(summaryArg);
  const rows = JSON.parse(readFileSync(rowsPath, "utf-8")) as Row[];
  const prisma = createPrismaClient();
  const now = new Date();

  const summary: Summary = {
    run_id: runId,
    rows_read: rows.length,
    inserted: 0,
    updated_unlocked: 0,
    locked_seen_only: 0,
    stale_incremented: 0,
    inactivated: 0,
    errors: 0,
  };

  const seenKeys = new Set<string>();
  const importSourceScope = rows[0]?.import_source ?? "scraped";
  const seenSourceStores = new Set<string>();

  try {
    for (const row of rows) {
      seenKeys.add(row.external_key);
      const sourceStore = row.source || row.source_store;
      seenSourceStores.add(sourceStore);
      const inStock = String(row.in_stock).toLowerCase() === "true";
      const stockStatus = inStock ? "IN_STOCK" : "OUT_OF_STOCK";
      const sourceType = toSourceType(row.import_source);
      const baseSalePrice = toCents(row.sale_price);
      const basePrice = toCents(row.price);

      const originalPriceCents = baseSalePrice !== null ? basePrice : null;
      const salePriceCents = baseSalePrice ?? basePrice;

      const existing = await prisma.deal.findUnique({
        where: { externalKey: row.external_key },
      });

      if (!existing) {
        await prisma.deal.create({
          data: {
            slug: `${row.external_key}-${Date.now()}`,
            title: row.title,
            description: row.description || null,
            imageUrl: row.image_url || null,
            originalPriceCents,
            salePriceCents,
            currency: row.currency,
            stockStatus: stockStatus as any,
            shippingText: row.stock_text || null,
            retailerUrl: row.source_url,
            externalKey: row.external_key,
            sourceStore,
            sourceProductId: row.source_product_id || null,
            importSource: row.import_source,
            sourceType: sourceType as any,
            status: "ACTIVE" as any,
            firstSeenAt: now,
            lastSeenAt: now,
            lastCheckedAt: now,
            lastRunId: runId,
            missedRuns: 0,
          },
        });
        summary.inserted += 1;
        continue;
      }

      if (existing.keepFlag) {
        await prisma.deal.update({
          where: { id: existing.id },
          data: {
            status: "ACTIVE" as any,
            missedRuns: 0,
            lastSeenAt: now,
            lastCheckedAt: now,
            lastRunId: runId,
          },
        });
        summary.locked_seen_only += 1;
        continue;
      }

      await prisma.deal.update({
        where: { id: existing.id },
        data: {
          title: row.title,
          description: row.description || null,
          // KEEP deals do not overwrite imageUrl; unlocked rows can.
          imageUrl: row.image_url || null,
          originalPriceCents,
          salePriceCents,
          currency: row.currency,
          stockStatus: stockStatus as any,
          shippingText: row.stock_text || null,
          retailerUrl: row.source_url,
          sourceStore,
          sourceProductId: row.source_product_id || null,
          importSource: row.import_source,
          sourceType: sourceType as any,
          status: "ACTIVE" as any,
          missedRuns: 0,
          lastSeenAt: now,
          lastCheckedAt: now,
          lastRunId: runId,
        },
      });
      summary.updated_unlocked += 1;
    }

    const staleCandidates = await prisma.deal.findMany({
      where: {
        sourceStore: { in: [...seenSourceStores] },
        importSource: importSourceScope,
        externalKey: { notIn: [...seenKeys] },
      },
      select: {
        id: true,
        missedRuns: true,
      },
    });

    for (const stale of staleCandidates) {
      const nextMissedRuns = stale.missedRuns + 1;
      const shouldExpire = nextMissedRuns >= staleThreshold;
      await prisma.deal.update({
        where: { id: stale.id },
        data: {
          missedRuns: nextMissedRuns,
          lastCheckedAt: now,
          lastRunId: runId,
          status: (shouldExpire ? "EXPIRED" : "ACTIVE") as any,
        },
      });
      summary.stale_incremented += 1;
      if (shouldExpire) {
        summary.inactivated += 1;
      }
    }
  } catch (error) {
    summary.errors += 1;
    console.error(error);
    writeFileSync(summaryPath, JSON.stringify(summary, null, 2), "utf-8");
    await prisma.$disconnect();
    return 1;
  }

  writeFileSync(summaryPath, JSON.stringify(summary, null, 2), "utf-8");
  await prisma.$disconnect();
  return 0;
}

main()
  .then((code) => {
    process.exit(code);
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
