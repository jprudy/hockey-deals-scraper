import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "../../src/generated/prisma/client";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function loadDatabaseUrlFromEnvFile(): string | undefined {
  try {
    const envPath = resolve(process.cwd(), ".env");
    const content = readFileSync(envPath, "utf-8");
    for (const line of content.split(/\r?\n/)) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const idx = trimmed.indexOf("=");
      if (idx === -1) continue;
      const key = trimmed.slice(0, idx).trim();
      if (key !== "DATABASE_URL") continue;
      const raw = trimmed.slice(idx + 1).trim();
      return raw.replace(/^['"]|['"]$/g, "");
    }
  } catch {
    return undefined;
  }
  return undefined;
}

export function createPrismaClient(): PrismaClient {
  const connectionString = process.env.DATABASE_URL ?? loadDatabaseUrlFromEnvFile();
  if (!connectionString) {
    throw new Error("Missing DATABASE_URL");
  }

  return new PrismaClient({
    adapter: new PrismaPg({ connectionString }),
    log: ["error", "warn"],
  });
}
