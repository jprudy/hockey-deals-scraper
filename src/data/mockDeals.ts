import type { Deal } from "@/lib/deals/types";

// Mock data used for the initial Phase 0 UI.
// Later this repository will swap to Prisma/PostgreSQL reads.
export const mockDeals: Deal[] = [
  {
    slug: "bauer-supreme-ultrasonic-helmet-clearance",
    title: "Bauer Supreme Ultrasonic Helmet Clearance",
    brand: "Bauer",
    category: "Helmets",
    priceCents: 4299,
    size: "Senior",
    url: "https://example.com/bauer-helmet",
    description:
      "A limited-time price drop on a popular senior helmet. Stock moves fast.",
  },
  {
    slug: "ccm-tacks-4r-pro-shin-pads-deal",
    title: "CCM Tacks 4R Pro Shin Pads Deal",
    brand: "CCM",
    category: "Shin Pads",
    priceCents: 5499,
    size: "Intermediate",
    url: "https://example.com/ccm-shin-pads",
    description:
      "Comfortable fit with a competitive price for intermediate players.",
  },
  {
    slug: "watson-hockey-grip-tape-2-pack",
    title: "Watson Hockey Grip Tape 2-Pack",
    brand: "Watson",
    category: "Accessories",
    priceCents: 1299,
    size: "One Size",
    url: "https://example.com/grip-tape",
    description:
      "Reliable tack and value in a convenient 2-pack. Great for string jobs and quick refreshes.",
  },
  {
    slug: "rico-curve-stick-tape-bundle",
    title: "Rico Curve Stick Tape Bundle",
    brand: "Rico",
    category: "Accessories",
    priceCents: 1699,
    size: "One Size",
    url: "https://example.com/stick-tape",
    description:
      "Bundle pricing for teams and frequent stick replacers.",
  },
  {
    slug: "warrior-sports-knife-edge-skates-sale",
    title: "Warrior Knife-Edge Skates - Weekend Sale",
    brand: "Warrior",
    category: "Skates",
    priceCents: 15999,
    size: "Size 8",
    url: "https://example.com/warrior-skates",
    description:
      "Weekend markdown on knife-edge style skates. Confirm fit before checkout.",
  },
  {
    slug: "mission-infinity-gloves-clearance",
    title: "Mission Infinity Gloves Clearance",
    brand: "Mission",
    category: "Gloves",
    priceCents: 3799,
    size: "Senior",
    url: "https://example.com/mission-gloves",
    description:
      "Clearance pricing on a glove that’s built for all-season durability.",
  },
];

