#!/usr/bin/env node
// Setup check from the command line (the installer can spawn this):
//   node bin/sandbox-doctor.mjs --engine engine.json [--image ref] [--quick]
// Prints { ok, checks: [...] } as JSON; exit code 0 when ok, 1 otherwise.
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";

const args = process.argv.slice(2);
const opt = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };
const enginePath = opt("--engine");
if (!enginePath) {
  console.error("usage: sandbox-doctor --engine engine.json [--image ref] [--quick]");
  process.exit(2);
}
// built package when installed, sources when run from the repo (Node >= 22.18 strips types)
const dist = new URL("../dist/doctor.js", import.meta.url);
const { setupCheck } = await import(existsSync(dist) ? dist.href : new URL("../src/doctor.ts", import.meta.url).href);
const engine = JSON.parse(await readFile(enginePath, "utf8"));
const report = await setupCheck(engine, { image: opt("--image"), quick: args.includes("--quick") });
console.log(JSON.stringify(report, null, 2));
process.exit(report.ok ? 0 : 1);
