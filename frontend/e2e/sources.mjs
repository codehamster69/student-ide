// End-to-end check of the larger question sets, with screenshots for the
// thesis: a teacher browses Codeforces problems by topic (open-r1 Codeforces
// dataset, bundled), adds a dynamic-programming problem with its tests, adds
// a CodeChef problem and an MBPP problem; a student solves the Codeforces one
// and checks it against the imported tests.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/sources.mjs [screenshot-dir] [light|dark]
//
// MBPP is fetched from raw.githubusercontent.com, so the server needs that.

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const STUDENT = `S${Date.now().toString(36).toUpperCase()}`;

const browser = await chromium.launch();
const errors = [];
const open = async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
  page.on("pageerror", (e) => errors.push(e.message));
  return page;
};
const shot = async (page, name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(1200);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/sources-${SCHEME}-${name}.png`, fullPage: full });
};
const get = async (path) => {
  const r = await fetch(BASE + path, { headers: { "X-Admin-Token": TOKEN } });
  assert.ok(r.ok, `${path}: ${r.status}`);
  return r.json();
};

const t = await open();
await t.goto(`${BASE}/#/teach`);
await t.fill("input[type=password]", TOKEN);
await t.click("button[type=submit]");
await t.waitForSelector("text=A lab is one sitting");
await t.click("button:has-text('New lab')");
await t.fill("input[placeholder^='Lab 5']", "Lab 10: Problem solving (e2e)");
await t.fill("input[placeholder='Data Structures']", "Algorithms");
await t.click("button:has-text('Create and add questions')");
await t.waitForSelector("text=Add the first question");
const labId = (await t.evaluate(() => location.hash)).split("/").at(-1);

// Codeforces: topics, then rating bands
await t.click("button:has-text('From a platform') >> nth=0");
await t.click("button[role=tab]:has-text('Codeforces')");
await t.waitForSelector("[role=group][aria-label=Topic] button:has-text('Dynamic programming')");
await t.click("[role=group][aria-label=Topic] button:has-text('Dynamic programming')");
await t.waitForSelector("ul[aria-label=Questions] button");
await shot(t, "01-codeforces-topics");
await t.fill("input[aria-label='Search questions']", "Polycarp's Pockets");
await t.click("ul[aria-label=Questions] button:has-text(\"Polycarp's Pockets\")");
await t.waitForSelector("button:has-text('Add to lab')");
await shot(t, "02-codeforces-preview");
await t.click("button:has-text('Add to lab')");
await t.waitForSelector("strong:text-is(\"Polycarp's Pockets\")");

// CodeChef, from the same dataset
await t.click("button:has-text('From a platform') >> nth=0");
await t.click("button[role=tab]:has-text('CodeChef')");
await t.click("[role=group][aria-label=Level] button:has-text('Easy')");
await t.waitForSelector("ul[aria-label=Questions] button");
await shot(t, "03-codechef");
await t.click("ul[aria-label=Questions] button >> nth=0");
await t.click("button:has-text('Add to lab')");
await t.waitForSelector("text=From CodeChef");

// MBPP: beginner Python, topics guessed from the wording
await t.click("button:has-text('From a platform') >> nth=0");
await t.click("button[role=tab]:has-text('MBPP')");
await t.click("[role=group][aria-label=Topic] button:has-text('Strings')");
await t.waitForSelector("ul[aria-label=Questions] button");
await shot(t, "04-mbpp");
await t.click("ul[aria-label=Questions] button >> nth=0");
await t.click("button:has-text('Add to lab')");
await t.waitForSelector("text=From MBPP");

await t.click("label:has-text('Everyone who signs in') input[type=checkbox]");
await t.click("button[role=radio]:has-text('Open')");
await t.waitForSelector("button[role=radio][aria-checked=true]:has-text('Open')");
await shot(t, "05-lab", true);

const lab = await get(`/api/teach/labs/${labId}`);
const cf = lab.questions.find((q) => q.source?.provider === "codeforces");
assert.ok(cf.tests.length >= 3 && cf.source.license === "CC BY 4.0");
assert.ok(lab.questions.find((q) => q.source?.provider === "codechef"));
assert.ok(lab.questions.find((q) => q.source?.provider === "mbpp").tests.length >= 1);

// student solves the Codeforces problem
const s = await open();
await s.goto(BASE);
await s.fill("input", STUDENT);
await s.click("button[type=submit]");
await s.waitForSelector("text=Before you start");
await s.check("input[type=checkbox]");
await s.click("button:text-is(\"Start\")");
await s.waitForSelector("text=Lab 10: Problem solving (e2e)");
await s.click("button:has-text(\"Polycarp's Pockets\")");
await s.waitForSelector(".cm-content");
await s.click(".cm-content");
await s.keyboard.type("input()", { delay: 10 });
await s.keyboard.press("Enter");
await s.keyboard.type("a = input().split()", { delay: 10 });
await s.keyboard.press("Enter");
await s.keyboard.type("print(max(a.count(x) for x in a))", { delay: 10 });
await s.click("button:has-text('Check')");
await s.waitForSelector(`text=${cf.tests.length} of ${cf.tests.length} passed`);
await shot(s, "06-student-check");

await browser.close();
assert.deepEqual(errors, [], `page errors: ${errors.join("; ")}`);
console.log(JSON.stringify({ lab: labId, questions: lab.questions.length, cfTests: cf.tests.length }));
console.log("sources e2e OK");
