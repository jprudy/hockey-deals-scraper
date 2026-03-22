# Remove seed / demo deals

The four mock deals in `prisma/seed.ts` use **Example Hockey Retailer** and `https://example.com/...` links. To remove them from **Neon** (or local DB):

## Option A — npm script (recommended)

From the repo root, with `DATABASE_URL` in `.env`:

```bash
npm install
npm run db:delete-seed-deals
```

This deletes the known seed slugs and removes **`example-retailer`** if no deals still reference it.

## Option B — Neon SQL Editor

Run the statements in `scripts/sql/remove_seed_deals.sql` (see file for optional retailer delete).

## Option C — VPS

```bash
cd /root/hockeydeals-v2
npm run db:delete-seed-deals
```

Ensure `.env` on the server has `DATABASE_URL` (same as the app / importer).

---

## Stop demo deals from coming back on `db seed`

Set before running Prisma seed (e.g. in production `.env`):

```env
SEED_SKIP_DEMO_DEALS=1
```

Then `npx prisma db seed` still seeds **retailers / brands / categories** but **skips** the four demo `Deal` upserts.

Without this variable, seed **re-creates** the demo deals whenever you run the full seed.
