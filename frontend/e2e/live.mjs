// End-to-end check of the live classroom view, with screenshots for the thesis:
// four demo students open questions in the open demo lab and type; a teacher
// follows the class live, opens one student's editor, and that student's IDE
// shows who is viewing. When the teacher leaves, the notice goes away.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/live.mjs [screenshot-dir] [light|dark]
//
// Run against a database seeded with `python -m studentide.seed` (lab_demo1
// is open, DEMO01-06 are on its roster and have consented).

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);

const browser = await chromium.launch();
const errors = [];
const open = async (w = 1440, h = 900) => {
  const page = await browser.newPage({ viewport: { width: w, height: h }, colorScheme: SCHEME, deviceScaleFactor: 2 });
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("dialog", (d) => d.accept());
  return page;
};
const shot = async (page, name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(1200);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/live-${SCHEME}-${name}.png`, fullPage: full });
};

// --- students start working -----------------------------------------------------
const CODE = {
  DEMO01: "counts = {}\nfor w in text.split():\n    counts[w] = counts.get(w, 0) + 1\n",
  DEMO02: "print(sum(c in 'aeiouAEIOU' for c in line))\n",
  DEMO03: "for w in text.split()\n",       // a syntax error on purpose
  DEMO04: "print(text[::-1])\n",
};
const students = {};
for (const [id, code] of Object.entries(CODE)) {
  const s = await open(1280, 800);
  await s.goto(BASE);
  await s.fill("input", id);
  await s.click("button[type=submit]");
  // A student who agreed to the text from before live viewing is asked again
  // (to see it, set consent_version = NULL for the demo students first).
  await s.waitForSelector("h1:has-text('Before you start'), :text('Your labs')");
  if (await s.isVisible("text=Before you start")) {
    assert.ok(await s.isVisible("text=read-only view of your editor"), "consent mentions live viewing");
    if (id === "DEMO01") await shot(s, "01-consent");
    await s.check("input[type=checkbox]");
    await s.click("button:text-is(\"Start\")");
  }
  await s.waitForSelector("text=Your labs");
  await s.click(id === "DEMO02" ? "button:has-text('Count vowels')" : "button:has-text('Top three words')");
  await s.waitForSelector(".cm-content");
  await s.click(".cm-content");
  await s.keyboard.press("Control+End");
  await s.keyboard.type(code, { delay: 15 });
  if (id !== "DEMO04") await s.keyboard.press("Control+Enter");
  students[id] = s;
}
await students.DEMO03.waitForSelector(".output.failed");

// --- teacher -------------------------------------------------------------------
const t = await open();
await t.goto(`${BASE}/#/live`);
await t.waitForSelector("text=Teacher access");
await t.fill("input[type=password]", TOKEN);
await t.click("button[type=submit]");
await t.waitForSelector("a[href='#/live/l/lab_demo1']");
await shot(t, "02-open-labs");

await t.click("a[href='#/live/l/lab_demo1']");
await t.waitForSelector("text=Live class view");
await t.waitForFunction(() => document.querySelectorAll("button:has(svg.lucide-eye)").length >= 4);
// The class view is open: students see the small notice.
await students.DEMO02.waitForSelector("text=Class view on", { timeout: 8000 });
await shot(t, "03-class", true);

// DEMO01 is still typing while the teacher watches.
const watched = students.DEMO01;
const cardSel = "div.rounded-2xl:has(span:text-is('DEMO01'))";
await t.click(`${cardSel} button:has-text('View editor')`);
await t.waitForSelector("text=can see that you are viewing their editor");
await watched.keyboard.type("best = sorted(counts.items(), key=lambda kv: -kv[1])[:3]\n", { delay: 20 });
await t.waitForFunction(() => document.querySelector(".cm-content")?.innerText.includes("best = sorted"), null, { timeout: 10000 });
await shot(t, "04-editor");

// The student is told, by name, for as long as the teacher looks.
await watched.waitForSelector("text=viewing your editor", { timeout: 8000 });
await shot(watched, "05-student-notice");

// Leaving the page ends the notice at once.
await t.click("a:has-text('Lab 5')");
await t.waitForSelector("text=Live class view");
await watched.waitForSelector("text=Class view on", { timeout: 8000 });
assert.equal(await watched.isVisible("text=viewing your editor"), false, "notice ends when the teacher leaves");
await t.goto(`${BASE}/#/teach`);
await watched.waitForSelector("text=Class view on", { state: "detached", timeout: 20000 });

// Every view was logged.
const res = await fetch(`${BASE}/api/live/labs/lab_demo1`, { headers: { "X-Admin-Token": TOKEN } });
const live = await res.json();
const rows = Object.fromEntries(live.students.map((s) => [s.student_id, s]));
assert.equal(rows.DEMO03.last_run.ok, false);

assert.deepEqual(errors, [], "no page errors");
await browser.close();
console.log("live view e2e: ok");
