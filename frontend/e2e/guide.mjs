// End-to-end check of the guide: the public #/help page (index, search, a page, a
// link between pages), the teacher area's Guide with the "Help" button, and the
// student app's Guide tab. Every guide link must resolve to a page.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/guide.mjs

import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));

// public guide: index, search, a page, a cross-link
await page.goto(`${BASE}/#/help`);
await page.waitForSelector("text=Student guide");
await page.waitForSelector("text=Teacher guide");
await page.fill("input[aria-label='Search the guide']", "baseline");
await page.waitForSelector("a:has-text('Review timeline')");
await page.fill("input[aria-label='Search the guide']", "");
await page.click("a:has-text('Attendance') >> nth=0");
await page.waitForSelector("h1:text-is('Attendance')");
assert.match(page.url(), /#\/help\/student\/attendance$/);
// every in-guide link on every page resolves (unresolved links render as plain text, so count anchors)
for (const audience of ["student", "teacher"]) {
  await page.goto(`${BASE}/#/help/${audience}`);
  const slugs = await page.$$eval("nav[aria-label='Guide pages'] a", (as) => as.map((a) => a.getAttribute("href")));
  assert.ok(slugs.length >= 8, `${audience} guide has pages`);
  for (const href of slugs) {
    await page.goto(`${BASE}/${href}`);
    await page.waitForSelector("article h1");
    const links = await page.$$eval("article a[href^='#/help/']", (as) => as.map((a) => a.getAttribute("href")));
    for (const l of links) assert.match(l, /^#\/help\/(student|teacher)\/[\w-]+$/);
  }
}

// teacher area: sidebar Guide, the Help button opens the page for where you are
await page.goto(`${BASE}/#/review`);
await page.waitForSelector("input[type=password], nav[aria-label='Main']");
if (await page.locator("input[type=password]").count()) {
  await page.fill("input[type=password]", TOKEN);
  await page.click("button[type=submit]");
}
await page.waitForSelector("a[aria-label='Help for this page']");
await page.click("a[aria-label='Help for this page']");
await page.waitForSelector("h1:text-is('Review timeline')");
await page.click("nav[aria-label='Main'] a:has-text('Guide')");
await page.waitForSelector("text=Teacher guide");

// Ctrl+K finds a guide page
await page.keyboard.press("Control+k");
await page.fill("input[aria-label='Search']", "live view");
await page.keyboard.press("Enter");
await page.waitForSelector("h1:text-is('Live view')");

// student app: the Guide tab
await page.goto(`${BASE}/`);
await page.reload();
await page.waitForSelector("button[type=submit]");
await page.fill("input", "DEMO03");
await page.click("button[type=submit]");
const consent = page.locator("text=Before you start");
await page.waitForTimeout(800);
if (await consent.count()) { await page.check("input[type=checkbox]"); await page.click('button:text-is("Start")'); }
await page.click("nav[aria-label='Main'] button:has-text('Guide')");
await page.waitForSelector("text=Student guide");
await page.click("button:has-text('What we record')");
await page.waitForSelector("h1:text-is('What we record')");

assert.deepEqual(errors, []);
await browser.close();
console.log("guide e2e ok");
