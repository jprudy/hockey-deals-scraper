-- Remove demo deals created by prisma/seed.ts (Example Hockey Retailer / mock copy).
--
-- Preferred (uses Prisma + .env): from repo root
--   npm run db:delete-seed-deals
--
-- Or run in Neon SQL Editor, or:
--   psql "$DATABASE_URL" -f scripts/sql/remove_seed_deals.sql
--
-- Review first:
--   SELECT id, slug, title, "affiliateUrl", "sourceType" FROM "Deal"
--   WHERE slug IN (
--     'bauer-supreme-ultrasonic-helmet-clearance-senior',
--     'ccm-ribcor-trigger-5-helmet-sale-senior',
--     'ccm-tacks-4r-pro-shin-pads-deal-shin-pads',
--     'warrior-shin-guard-deal-shin-pads'
--   );

DELETE FROM "Deal"
WHERE slug IN (
  'bauer-supreme-ultrasonic-helmet-clearance-senior',
  'ccm-ribcor-trigger-5-helmet-sale-senior',
  'ccm-tacks-4r-pro-shin-pads-deal-shin-pads',
  'warrior-shin-guard-deal-shin-pads'
);

-- Optional: remove the seed-only retailer if nothing else references it.
-- Uncomment after verifying:
--   SELECT * FROM "Deal" WHERE "retailerId" IN (SELECT id FROM "Retailer" WHERE slug = 'example-retailer');
-- DELETE FROM "Retailer" WHERE slug = 'example-retailer';
