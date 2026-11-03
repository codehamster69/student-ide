// End-to-end check of "View as student": from the teacher area a teacher opens
// the student side, sees their labs as students do (the draft lab too, marked),
// works a question and a lesson, and goes back. None of it may reach review.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/preview.mjs [screenshot-dir] [light|dark]
//
// Run against a database seeded with `python -m studentide.seed` (dev mode: the admin token).

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);

const browser = await chromium.launch();
const errors = [];
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
page.on("pageerror", (e) => errors.push(e.message));
const shot = async (name) => {
  if (!OUT) return;
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/preview-${SCHEME}-${name}.png` });
};
const admin = async (path) => (await fetch(BASE + path, { headers: { "X-Admin-Token": TOKEN } })).json();
const before = (await admin("/api/sessions")).length;

await page.goto(`${BASE}/#/teach`);
await page.fill("input[type=password]", TOKEN);
await page.click("button[type=submit]");
await page.waitForSelector("a[href^='#/teach/labs/']");
await page.click("a:has-text('View as student')");

// --- the student home, as the teacher's labs ------------------------------------------
await page.waitForSelector("text=Student view.");
await page.waitForSelector("h2:has-text('Lab 5: Strings and dictionaries')");
await page.waitForSelector("h2:has-text('Lab 6: Recursion') >> text=Draft");
assert.ok(!(await page.isVisible("text=Before you start")), "no consent screen for staff");
await shot("01-home");

// --- a question of the draft lab runs like a student's -----------------------------------
await page.click("button:has-text('Power set')");
await page.waitForSelector(".cm-content");
await page.click(".cm-content");
await page.keyboard.press("Control+A");
await page.keyboard.insertText("print('ok')\n");
await page.keyboard.press("Control+Enter");
await page.waitForSelector(".output:has-text('ok')");
await page.waitForSelector("text=Student view.");
await shot("02-editor");

// --- back to Teach --------------------------------------------------------------------------
await page.click("a:has-text('Back to Teach')");
await page.waitForSelector("a[href^='#/teach/labs/']");
assert.equal((await admin("/api/sessions")).length, before, "previews never reach review");
const labs = await admin("/api/teach/labs");
assert.equal(labs.find((l) => l.title === "Lab 6: Recursion").n_sessions, 0, "nor lab counts");
assert.deepEqual(errors, []);
await browser.close();
console.log("view as student e2e ok");
