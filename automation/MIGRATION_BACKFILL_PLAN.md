# Phase 5 Safe Migration / Backfill Plan

This plan avoids breaking existing manual `Deal` rows while moving toward required
`externalKey` and `sourceStore` for imported pipeline records.

## Step 1: Expand schema safely (nullable)

Add these fields as nullable first:

- `sourceStore String?`
- `sourceProductId String?`
- `externalKey String? @unique`
- `importSource String?`
- `missedRuns Int @default(0)`
- `firstSeenAt DateTime?`
- `lastCheckedAt DateTime?`
- `lastRunId String?`

Run migration and deploy it before importer rollout.

## Step 2: Backfill existing rows

Backfill manual rows in SQL (or Prisma script):

- If `sourceStore` is null, set to `"manual"`
- If `importSource` is null, set to `"manual"`
- If `externalKey` is null, set to deterministic manual key:
  - `externalKey = 'manual:' || id`

This guarantees unique values and preserves current behavior.

## Step 3: Enable Phase 5 importer

Importer writes:

- `sourceStore = "thehockeyshop"`
- `importSource = "scraped"`
- required runtime key `externalKey`

Rows without a valid `externalKey` are rejected before DB writes.

## Step 4: Verify data completeness

Before making fields required, validate:

- `select count(*) from "Deal" where "externalKey" is null;` -> `0`
- `select count(*) from "Deal" where "sourceStore" is null;` -> `0`

## Step 5: Tighten constraints (second migration)

After successful backfill + importer burn-in:

- Change `externalKey` to `String @unique` (non-null)
- Change `sourceStore` to `String` (non-null)

Do this only after at least one full successful Phase 5 run.
