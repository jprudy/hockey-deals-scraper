// Ensure Prisma always loads DATABASE_URL from the repo root `.env`,
// regardless of the current working directory.
import dotenv from "dotenv";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";
import { defineConfig } from "prisma/config";

const __dirname = dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: resolve(__dirname, ".env") });

if (!process.env.DATABASE_URL) {
  throw new Error(
    "Missing DATABASE_URL. Ensure it is set in the repo root `.env` file."
  );
}

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
  },
  datasource: {
    url: process.env.DATABASE_URL,
  },
});
