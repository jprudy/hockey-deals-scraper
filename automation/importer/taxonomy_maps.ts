/**
 * Controlled taxonomy for importer-side resolution.
 * Raw scraper labels are mapped here; only allowlisted categories may be created in the DB.
 */

/** Slugs we allow to exist / be created for top-level categories. */
export const ALLOWED_CATEGORY_SLUGS = new Set([
  "player-gear",
  "goalie-gear",
  "accessories",
  "helmets",
  "protective",
]);

/** Canonical display name per slug (used on first create). */
export const CATEGORY_DISPLAY_BY_SLUG: Record<string, string> = {
  "player-gear": "Player Gear",
  "goalie-gear": "Goalie Gear",
  accessories: "Accessories",
  helmets: "Helmets",
  protective: "Protective",
};

/**
 * Fold scraper/label text for map lookup: trim, lowercase, collapse whitespace.
 */
export function normalizeFoldKey(raw: string): string {
  return raw.trim().replace(/\s+/g, " ").toLowerCase();
}

function slugifyTaxonomy(s: string): string {
  const collapsed = s.trim().replace(/\s+/g, " ");
  const slug = collapsed
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return slug || "unknown";
}

/**
 * Map folded label variants → allowed category slug.
 * Keep this list small; extend when review log shows repeats.
 */
export const CATEGORY_ALIAS_TO_SLUG: Record<string, string> = {
  // Accessories
  accessory: "accessories",
  accessories: "accessories",
  // Player / goalie (scrapers)
  "player gear": "player-gear",
  "players gear": "player-gear",
  "goalie gear": "goalie-gear",
  "goalie equipment": "goalie-gear",
  // Helmets (singular/plural + seed alignment)
  helmet: "helmets",
  helmets: "helmets",
  // Protective
  protective: "protective",
  protection: "protective",
  protections: "protective",
};

/**
 * Resolve raw scraper category to an allowlisted slug, or null if unknown.
 */
export function resolveCategorySlugFromRaw(raw: string | undefined): string | null {
  const trimmed = (raw || "").trim();
  if (!trimmed) return null;

  const fold = normalizeFoldKey(trimmed);
  const fromAlias = CATEGORY_ALIAS_TO_SLUG[fold];
  if (fromAlias && ALLOWED_CATEGORY_SLUGS.has(fromAlias)) {
    return fromAlias;
  }

  const fromSlug = slugifyTaxonomy(trimmed);
  if (ALLOWED_CATEGORY_SLUGS.has(fromSlug)) {
    return fromSlug;
  }

  // Match canonical display names (case-insensitive)
  for (const [slug, name] of Object.entries(CATEGORY_DISPLAY_BY_SLUG)) {
    if (normalizeFoldKey(name) === fold) {
      return slug;
    }
  }

  return null;
}

/**
 * Map folded subcategory labels → canonical display name (reduces plural/singular drift).
 * If no alias, returns the trimmed single-spaced original (not .title()'d).
 */
export const SUBCATEGORY_ALIAS_TO_LABEL: Record<string, string> = {
  // Shin / elbow / shoulder / neck
  "shin guard": "Shin Guards",
  "shin guards": "Shin Guards",
  "shinguard": "Shin Guards",
  "shinguards": "Shin Guards",
  "elbow pad": "Elbow Pads",
  "elbow pads": "Elbow Pads",
  "shoulder pad": "Shoulder Pads",
  "shoulder pads": "Shoulder Pads",
  "neck guard": "Neck Guards",
  "neck guards": "Neck Guards",
  "throat protector": "Neck Guards",
  "mouth guard": "Mouth Guards",
  "mouthguard": "Mouth Guards",
  "mouth guards": "Mouth Guards",
  // Helmet
  helmet: "Helmet",
  helmets: "Helmet",
  mask: "Mask",
  masks: "Mask",
  // Lower body / jock
  "hockey pant": "Hockey Pants",
  "hockey pants": "Hockey Pants",
  "jock/jill": "Jock/Jill",
  "jock jill": "Jock/Jill",
  // Sticks / skates
  stick: "Stick",
  sticks: "Stick",
  skate: "Skates",
  skates: "Skates",
  "goalie skate": "Goalie Skates",
  "goalie skates": "Goalie Skates",
  "goalie stick": "Goalie Stick",
  "goalie sticks": "Goalie Stick",
  // Goalie pieces
  "leg pad": "Leg Pads",
  "leg pads": "Leg Pads",
  "catcher glove": "Catcher Glove",
  blocker: "Blocker",
  blockers: "Blocker",
  "goalie pant": "Goalie Pants",
  "goalie pants": "Goalie Pants",
  "chest & arm protector": "Chest & Arm Protector",
  "chest and arm protector": "Chest & Arm Protector",
  glove: "Gloves",
  gloves: "Gloves",
  jersey: "Jersey",
  jerseys: "Jersey",
  socks: "Socks",
  sock: "Socks",
  // Seed-ish
  senior: "Senior",
  "shin pad": "Shin Pads",
  "shin pads": "Shin Pads",
};

export function resolveSubcategoryDisplayLabel(raw: string | undefined): string | null {
  const trimmed = (raw || "").trim().replace(/\s+/g, " ");
  if (!trimmed) return null;

  const fold = normalizeFoldKey(trimmed);
  const aliased = SUBCATEGORY_ALIAS_TO_LABEL[fold];
  if (aliased) return aliased;

  return trimmed;
}

export { slugifyTaxonomy };
