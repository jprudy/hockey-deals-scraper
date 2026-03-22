/**
 * Remove prisma demo deals from the database (Neon / local).
 * Uses DATABASE_URL from repo root .env (same as Prisma).
 *
 * Usage (from repo root):
 *   npx tsx scripts/delete_seed_deals.ts
 */
import { resolve } from "node:path";
import { config } from "dotenv";

config({ path: resolve(process.cwd(), ".env") });

import { getPrisma } from "../src/lib/prisma";
import { SEED_DEMO_DEAL_SLUGS } from "../src/lib/seedDemoDealSlugs";

async function main(): Promise<void> {
  const prisma = getPrisma();
  const slugs = [...SEED_DEMO_DEAL_SLUGS];

  const deleted = await prisma.deal.deleteMany({
    where: { slug: { in: slugs } },
  });
  console.log(`[delete_seed_deals] removed ${deleted.count} deal(s) with seed demo slugs.`);

  const example = await prisma.retailer.findUnique({
    where: { slug: "example-retailer" },
  });
  if (example) {
    const remaining = await prisma.deal.count({
      where: { retailerId: example.id },
    });
    if (remaining === 0) {
      await prisma.retailer.delete({ where: { slug: "example-retailer" } });
      console.log(
        "[delete_seed_deals] removed retailer example-retailer (no deals left).",
      );
    } else {
      console.log(
        `[delete_seed_deals] kept example-retailer (${remaining} deal(s) still use it).`,
      );
    }
  }

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
