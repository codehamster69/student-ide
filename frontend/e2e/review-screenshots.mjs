// Screenshots of the review timeline for the thesis, on a database seeded
// with `python -m studentide.seed`. The server needs STUDENTIDE_ADMIN_TOKEN.
//
//   BASE=http://127.0.0.1:8000 TOKEN=... node frontend/e2e/review-screenshots.mjs <out-dir> [light|dark]

import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
if (!OUT) throw new Error("usage: review-screenshots.mjs <out-dir> [light|dark]");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => m.type() === "error" && !m.text().includes("401") && errors.push(m.text()));
const shot = async (name, full = false) => {
  await page.waitForTimeout(1600);
  // a sticky header would be painted mid-page in a full-page capture
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/review-${SCHEME}-${name}.png`, fullPage: full });
};

await page.goto(`${BASE}/#/review/all`);
await page.waitForSelector("text=Teacher access");
await shot("01-gate");
await page.fill("input[type=password]", "wrong");
await page.click("button[type=submit]");
await page.waitForSelector("text=not accepted");
await page.fill("input[type=password]", TOKEN);
await page.click("button[type=submit]");
await page.waitForSelector("text=Sessions reviewed");
await page.waitForSelector("a[href^='#/review/s/'] svg path");
await shot("02-overview", true);

// a takeover session that the detector caught
const rows = await page.evaluate(async (tok) => {
  const r = await fetch("/api/review/sessions", { headers: { "X-Admin-Token": tok } });
  return r.json();
}, TOKEN);
const pick = (cond, ch) => rows.find((r) => r.synthetic?.condition === cond && r.episodes.some((e) => e.channel === ch));
const takeover = pick("takeover", "identity");
const copying = pick("copying", "process") ?? pick("paste", "process");
const honest = rows.find((r) => r.phase === "assessed" && r.synthetic?.condition === "honest" && r.episodes.length === 0);

await page.goto(`${BASE}/#/review/s/${takeover.id}`);
await page.waitForSelector("text=Moment 1");
await shot("03-session-takeover", true);
await page.click("button:has-text('Ground truth')");
const tl = page.locator("svg[aria-label='Evidence timeline']");
const box = await tl.boundingBox();
await page.mouse.move(box.x + box.width * 0.55, box.y + 120);
await shot("04-takeover-truth-hover");
await page.mouse.move(10, 10);
await page.click("button:has-text('Replay')");
await page.waitForTimeout(2500);
await shot("05-replaying");
await page.keyboard.press("Space");

await page.goto(`${BASE}/#/review/s/${copying.id}`);
await page.waitForSelector("text=Moment 1");
await shot("06-session-process", true);

if (honest) {
  await page.goto(`${BASE}/#/review/s/${honest.id}`);
  await page.waitForSelector("text=Nothing stood out");
  await shot("07-session-honest");
}
await browser.close();
if (errors.length) { console.error(errors.join("\n")); process.exit(1); }
console.log(`screenshots written to ${OUT}`);
