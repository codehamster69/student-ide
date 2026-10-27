// End-to-end check of LeetCode questions, with screenshots for the thesis: a
// teacher browses LeetCode problems by topic (tests and tags bundled from
// LeetCodeDataset), previews one whose text loads live from the Hugging Face
// dataset viewer (never stored by the server), adds it; a student opens it,
// reads the live text and checks a solution against the bundled tests.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/leetcode.mjs [screenshot-dir] [light|dark]
//
// The browser needs internet access to datasets-server.huggingface.co.

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
  await page.screenshot({ path: `${OUT}/leetcode-${SCHEME}-${name}.png`, fullPage: full });
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
await t.fill("input[placeholder^='Lab 5']", "Lab 11: Arrays and hashing (e2e)");
await t.fill("input[placeholder='Data Structures']", "Data Structures");
await t.click("button:has-text('Create and add questions')");
await t.waitForSelector("text=Add the first question");
const labId = (await t.evaluate(() => location.hash)).split("/").at(-1);

// LeetCode: topics, then Easy / Medium / Hard
await t.click("button:has-text('From a platform') >> nth=0");
await t.click("button[role=tab]:has-text('LeetCode')");
await t.click("[role=group][aria-label=Topic] button:has-text('Dictionaries and sets')");
await t.waitForSelector("ul[aria-label=Questions] button");
await shot(t, "01-topics");
await t.fill("input[aria-label='Search questions']", "two-sum");
await t.click("ul[aria-label=Questions] button:has-text('1. Two Sum')");
await t.waitForSelector("text=loaded live from LeetCodeDataset");
await t.waitForSelector("text=indices of the two numbers"); // the live text arrived
await shot(t, "02-preview-live-text");
await t.click("button:has-text('Add to lab')");
await t.waitForSelector("strong:text-is('1. Two Sum')");
await t.waitForSelector("text=Problem text loads live");

await t.click("label:has-text('Everyone who signs in') input[type=checkbox]");
await t.click("button[role=radio]:has-text('Open')");
await t.waitForSelector("button[role=radio][aria-checked=true]:has-text('Open')");
await shot(t, "03-lab", true);

const lab = await get(`/api/teach/labs/${labId}`);
const q = lab.questions.find((x) => x.source?.provider === "leetcode");
assert.equal(q.prompt, "", "LeetCode's text must not be stored");
assert.ok(q.tests.length >= 3 && q.source.live_prompt);

// student reads the live text and solves it
const s = await open();
await s.goto(BASE);
await s.fill("input", STUDENT);
await s.click("button[type=submit]");
await s.waitForSelector("text=Before you start");
await s.check("input[type=checkbox]");
await s.click("button:text-is(\"Start\")");
await s.waitForSelector("text=Lab 11: Arrays and hashing (e2e)");
await s.click("button:has-text('1. Two Sum')");
await s.waitForSelector(".cm-content");
await s.waitForSelector("text=indices of the two numbers");
await s.click(".cm-content");
await s.keyboard.press("Control+End");
for (let i = 0; i < 5; i++) await s.keyboard.press("Backspace"); // the newline and "pass"
await s.keyboard.type("return next([j, i] for i in range(len(nums)) for j in range(i) if nums[i] + nums[j] == target)", { delay: 5 });
await s.click("button:has-text('Check')");
await s.waitForSelector(`text=${q.tests.length} of ${q.tests.length} passed`);
await shot(s, "04-student-check");

await browser.close();
assert.deepEqual(errors, [], `page errors: ${errors.join("; ")}`);
console.log(JSON.stringify({ lab: labId, tests: q.tests.length }));
console.log("leetcode e2e OK");
