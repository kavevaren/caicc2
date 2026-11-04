// Locale parity check: id.json and en.json must have the same keys and the
// same key shapes (objects vs arrays vs strings), with equal array lengths.
// Run from web/: node scripts/check-locales.mjs — exits 1 on any mismatch.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const locales = join(here, "..", "src", "locales");

const id = JSON.parse(readFileSync(join(locales, "id.json"), "utf8"));
const en = JSON.parse(readFileSync(join(locales, "en.json"), "utf8"));

const errors = [];

function walk(a, b, path) {
  for (const key of Object.keys(a)) {
    const p = path ? `${path}.${key}` : key;
    if (!(key in b)) {
      errors.push(`missing in en: ${p}`);
      continue;
    }
    const av = a[key];
    const bv = b[key];
    if (Array.isArray(av) || Array.isArray(bv)) {
      if (!Array.isArray(av) || !Array.isArray(bv)) errors.push(`type mismatch at ${p}`);
      else if (av.length !== bv.length) errors.push(`array length mismatch at ${p}: id=${av.length} en=${bv.length}`);
    } else if (av && typeof av === "object") {
      walk(av, bv, p);
    }
  }
  for (const key of Object.keys(b)) {
    if (!(key in a)) errors.push(`missing in id: ${path ? `${path}.${key}` : key}`);
  }
}

walk(id, en, "");

if (errors.length > 0) {
  console.error("Locale parity failed:\n  " + errors.join("\n  "));
  process.exit(1);
}
console.log("Locale parity OK (id/en).");
