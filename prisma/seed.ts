import "dotenv/config";
import { getPrisma } from "../src/lib/prisma";
import type { Prisma } from "../src/generated/prisma/client";

async function main() {
  const prisma = getPrisma();

  // Taxonomy seed:
  // - Helmets -> Senior
  // - Protective -> Shin Pads
  const retailer = await prisma.retailer.upsert({
    where: { slug: "example-retailer" },
    update: {},
    create: {
      slug: "example-retailer",
      name: "Example Hockey Retailer",
      websiteUrl: "https://example.com",
    },
  });

  // Production scraper stores (importer also upserts these; seed keeps local/dev aligned).
  await prisma.retailer.upsert({
    where: { slug: "thehockeyshop" },
    update: {},
    create: {
      slug: "thehockeyshop",
      name: "The Hockey Shop",
      websiteUrl: "https://www.thehockeyshop.com",
    },
  });
  await prisma.retailer.upsert({
    where: { slug: "sourceforsports" },
    update: {},
    create: {
      slug: "sourceforsports",
      name: "Source for Sports",
      websiteUrl: null,
    },
  });
  await prisma.retailer.upsert({
    where: { slug: "sportexcellence" },
    update: {},
    create: {
      slug: "sportexcellence",
      name: "Sport Excellence",
      websiteUrl: null,
    },
  });

  const bauer = await prisma.brand.upsert({
    where: { slug: "bauer" },
    update: {},
    create: { slug: "bauer", name: "Bauer" },
  });

  const ccm = await prisma.brand.upsert({
    where: { slug: "ccm" },
    update: {},
    create: { slug: "ccm", name: "CCM" },
  });

  const warrior = await prisma.brand.upsert({
    where: { slug: "warrior" },
    update: {},
    create: { slug: "warrior", name: "Warrior" },
  });

  const helmetsCategory = await prisma.category.upsert({
    where: { slug: "helmets" },
    update: {},
    create: { slug: "helmets", name: "Helmets", description: null },
  });

  const protectiveCategory = await prisma.category.upsert({
    where: { slug: "protective" },
    update: {},
    create: {
      slug: "protective",
      name: "Protective",
      description: "Protective gear for hockey players",
    },
  });

  const helmetsSeniorSubcategory =
    (await prisma.subcategory.findFirst({
      where: { categoryId: helmetsCategory.id, slug: "senior" },
    })) ??
    (await prisma.subcategory.create({
      data: {
        categoryId: helmetsCategory.id,
        slug: "senior",
        name: "Senior",
      },
    }));

  const protectiveShinPadsSubcategory =
    (await prisma.subcategory.findFirst({
      where: { categoryId: protectiveCategory.id, slug: "shin-pads" },
    })) ??
    (await prisma.subcategory.create({
      data: {
        categoryId: protectiveCategory.id,
        slug: "shin-pads",
        name: "Shin Pads",
      },
    }));

  const now = new Date();

  type StockStatus =
    | "IN_STOCK"
    | "OUT_OF_STOCK"
    | "PREORDER"
    | "UNKNOWN";
  type DealStatus = "ACTIVE" | "EXPIRED" | "HIDDEN" | "DRAFT";
  type SourceType = "CSV" | "SHEET" | "SCRAPER" | "MANUAL";

  type SeedDeal = {
    slug: string;
    title: string;
    brandId: string;
    retailerId: string;
    categoryId: string;
    subcategoryId: string;
    imageUrl: string | null;
    description: string;
    originalPriceCents: number | null;
    salePriceCents: number | null;
    discountPercent: number | null;
    size: string | null;
    stockStatus: StockStatus;
    shippingText: string | null;
    affiliateUrl: string | null;
    affiliateUrlWithUtm: string | null;
    retailerUrl: string | null;
    isFeatured: boolean;
    keepFlag: boolean;
    status: DealStatus;
    lastSeenAt: Date;
    promotionStartAt: Date | null;
    promotionEndAt: Date | null;
    sourceType: SourceType;
    rawData: Prisma.InputJsonValue;
  };

  const deals: SeedDeal[] = [
    {
      slug: "bauer-supreme-ultrasonic-helmet-clearance-senior",
      title: "Bauer Supreme Ultrasonic Helmet Clearance",
      brandId: bauer.id,
      retailerId: retailer.id,
      categoryId: helmetsCategory.id,
      subcategoryId: helmetsSeniorSubcategory.id,
      imageUrl: null,
      description:
        "Limited-time clearance on a popular senior helmet. Check size/fit before checkout.",
      originalPriceCents: 6999,
      salePriceCents: 4299,
      discountPercent: 39,
      size: "Senior",
      stockStatus: "IN_STOCK",
      shippingText: "Ships in 2-3 days (mock).",
      affiliateUrl: "https://example.com/deals/bauer-helmet",
      affiliateUrlWithUtm: null,
      retailerUrl: retailer.websiteUrl ?? null,
      isFeatured: true,
      keepFlag: false,
      status: "ACTIVE",
      lastSeenAt: now,
      promotionStartAt: null,
      promotionEndAt: null,
      sourceType: "MANUAL",
      rawData: {
        source: "seed",
        category: "Helmets",
        subcategory: "Senior",
      },
    },
    {
      slug: "ccm-ribcor-trigger-5-helmet-sale-senior",
      title: "CCM Ribcor Trigger 5 Helmet Sale",
      brandId: ccm.id,
      retailerId: retailer.id,
      categoryId: helmetsCategory.id,
      subcategoryId: helmetsSeniorSubcategory.id,
      imageUrl: null,
      description:
        "Trigger 5 senior helmet deal for players who want strong protection without overspending.",
      originalPriceCents: 7999,
      salePriceCents: 5299,
      discountPercent: 34,
      size: "Senior",
      stockStatus: "PREORDER",
      shippingText: "Preorder item (mock).",
      affiliateUrl: "https://example.com/deals/ccm-helmet",
      affiliateUrlWithUtm: null,
      retailerUrl: retailer.websiteUrl ?? null,
      isFeatured: false,
      keepFlag: false,
      status: "ACTIVE",
      lastSeenAt: now,
      promotionStartAt: null,
      promotionEndAt: null,
      sourceType: "MANUAL",
      rawData: {
        source: "seed",
        category: "Helmets",
        subcategory: "Senior",
      },
    },
    {
      slug: "ccm-tacks-4r-pro-shin-pads-deal-shin-pads",
      title: "CCM Tacks 4R Pro Shin Pads Deal",
      brandId: ccm.id,
      retailerId: retailer.id,
      categoryId: protectiveCategory.id,
      subcategoryId: protectiveShinPadsSubcategory.id,
      imageUrl: null,
      description:
        "Competitive price on Tacks shin pads for strong protection and mobility.",
      originalPriceCents: 8499,
      salePriceCents: 5499,
      discountPercent: 35,
      size: "Intermediate",
      stockStatus: "IN_STOCK",
      shippingText: "Ships in 2-4 days (mock).",
      affiliateUrl: "https://example.com/deals/ccm-shin-pads",
      affiliateUrlWithUtm: null,
      retailerUrl: retailer.websiteUrl ?? null,
      isFeatured: true,
      keepFlag: false,
      status: "ACTIVE",
      lastSeenAt: now,
      promotionStartAt: null,
      promotionEndAt: null,
      sourceType: "MANUAL",
      rawData: {
        source: "seed",
        category: "Protective",
        subcategory: "Shin Pads",
      },
    },
    {
      slug: "warrior-shin-guard-deal-shin-pads",
      title: "Warrior Shin Pads Deal",
      brandId: warrior.id,
      retailerId: retailer.id,
      categoryId: protectiveCategory.id,
      subcategoryId: protectiveShinPadsSubcategory.id,
      imageUrl: null,
      description:
        "Extra deal on protective shin pads. Ideal for stocking up before the season starts.",
      originalPriceCents: 6999,
      salePriceCents: 4599,
      discountPercent: 34,
      size: "Senior",
      stockStatus: "OUT_OF_STOCK",
      shippingText: "Out of stock (mock).",
      affiliateUrl: "https://example.com/deals/warrior-shin-pads",
      affiliateUrlWithUtm: null,
      retailerUrl: retailer.websiteUrl ?? null,
      isFeatured: false,
      keepFlag: false,
      status: "ACTIVE",
      lastSeenAt: now,
      promotionStartAt: null,
      promotionEndAt: null,
      sourceType: "MANUAL",
      rawData: {
        source: "seed",
        category: "Protective",
        subcategory: "Shin Pads",
      },
    },
  ];

  for (const deal of deals) {
    await prisma.deal.upsert({
      where: { slug: deal.slug },
      update: {
        title: deal.title,
        description: deal.description,
        imageUrl: deal.imageUrl,
        originalPriceCents: deal.originalPriceCents,
        salePriceCents: deal.salePriceCents,
        discountPercent: deal.discountPercent,
        size: deal.size,
        stockStatus: deal.stockStatus,
        shippingText: deal.shippingText,
        affiliateUrl: deal.affiliateUrl,
        affiliateUrlWithUtm: deal.affiliateUrlWithUtm,
        retailerUrl: deal.retailerUrl,
        isFeatured: deal.isFeatured,
        keepFlag: deal.keepFlag,
        status: deal.status,
        lastSeenAt: deal.lastSeenAt,
        promotionStartAt: deal.promotionStartAt,
        promotionEndAt: deal.promotionEndAt,
        sourceType: deal.sourceType,
        rawData: deal.rawData,
        retailerId: deal.retailerId,
        brandId: deal.brandId,
        categoryId: deal.categoryId,
        subcategoryId: deal.subcategoryId,
      },
      create: {
        slug: deal.slug,
        title: deal.title,
        description: deal.description,
        imageUrl: deal.imageUrl,
        originalPriceCents: deal.originalPriceCents,
        salePriceCents: deal.salePriceCents,
        discountPercent: deal.discountPercent,
        size: deal.size,
        stockStatus: deal.stockStatus,
        shippingText: deal.shippingText,
        affiliateUrl: deal.affiliateUrl,
        affiliateUrlWithUtm: deal.affiliateUrlWithUtm,
        retailerUrl: deal.retailerUrl,
        isFeatured: deal.isFeatured,
        keepFlag: deal.keepFlag,
        status: deal.status,
        lastSeenAt: deal.lastSeenAt,
        promotionStartAt: deal.promotionStartAt,
        promotionEndAt: deal.promotionEndAt,
        sourceType: deal.sourceType,
        rawData: deal.rawData,
        retailerId: deal.retailerId,
        brandId: deal.brandId,
        categoryId: deal.categoryId,
        subcategoryId: deal.subcategoryId,
      },
    });
  }

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

