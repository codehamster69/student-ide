// Conversation outcomes on review moments: tap one, it is saved and comes back on
// reload, tap it again to clear. Also takes the thesis screenshot of a moment card.
// Needs a server on a seeded database (python -m studentide.seed) with STUDENTIDE_ADMIN_TOKEN.
//
//   BASE=http://127.0.0.1:8000 TOKEN=... node frontend/e2e/review-outcomes.mjs [out-dir] [light|dark]

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: OUT ? 2 : 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const api = (path, init = {}) => page.evaluate(async ([p, i, tok]) => {
  const r = await fetch(p, { ...i, headers: { "X-Admin-Token": tok, "Content-Type": "application/json" } });
  return r.json();
}, [path, init, TOKEN]);

await page.goto(`${BASE}/#/review/sessions`);
await page.waitForSelector("input[type=password]");
await page.fill("input[type=password]", TOKEN);
await page.click("button[type=submit]");
await page.waitForSelector("text=Sessions reviewed");

const rows = await api("/api/review/sessions");
const s = rows.find((r) => r.phase === "assessed" && r.synthetic?.condition === "takeover" && r.episodes.length)
  ?? rows.find((r) => r.episodes.length);
const ep = s.episodes[0];
await api(`/api/review/sessions/${s.id}/outcome`, { method: "PUT", body: JSON.stringify({ channel: ep.channel, start_s: ep.switch_est, outcome: null }) });

await page.goto(`${BASE}/#/review/sessions/${s.id}`);
await page.waitForSelector("text=Moment 1");
const group = page.getByRole("radiogroup", { name: "What came of the conversation" }).first();
await group.getByRole("radio", { name: "Had help" }).click();
await page.waitForTimeout(400);
const saved = (await api(`/api/review/sessions/${s.id}`)).episodes[0].outcome;
if (saved !== "had_help") throw new Error(`expected had_help, got ${saved}`);

await page.reload();
await page.waitForSelector("text=Moment 1");
const checked = await group.getByRole("radio", { name: "Had help" }).getAttribute("aria-checked");
if (checked !== "true") throw new Error("outcome did not come back after reload");

if (OUT) {
  const card = page.locator("text=Moment 1").locator("xpath=ancestor::div[contains(@class,'rounded')][1]");
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await group.getByRole("radio", { name: "Not discussed" }).hover();
  await page.waitForTimeout(300);
  await card.screenshot({ path: `${OUT}/review-${SCHEME}-08-moment-outcome.png` });
}

await group.getByRole("radio", { name: "Had help" }).click();  // tap again: cleared
await page.waitForTimeout(400);
const cleared = (await api(`/api/review/sessions/${s.id}`)).episodes[0].outcome;
if (cleared !== null) throw new Error("tapping the chosen outcome again should clear it");

await browser.close();
if (errors.length) throw new Error(errors.join("\n"));
console.log("review outcomes ok");
