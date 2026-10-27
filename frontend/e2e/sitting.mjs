// End-to-end check of a lab as one sitting, with screenshots for the thesis:
// a student opens the open demo lab once, moves between its questions inside
// the editor (each keeps its own code), finishes the lab, and on opening it
// again carries on where they left off. Each question visited is its own
// recorded session, linked by a sitting id.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/sitting.mjs [screenshot-dir] [light|dark]
//
// Run against a database seeded with `python -m studentide.seed` (lab_demo1
// is open, DEMO01-06 are on its roster and have consented).

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const STUDENT = process.env.STUDENT ?? "DEMO05";
const [OUT, SCHEME = "light"] = process.argv.slice(2);

const browser = await chromium.launch();
const errors = [];
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
page.on("pageerror", (e) => errors.push(e.message));
const shot = async (name) => {
  if (!OUT) return;
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/sitting-${SCHEME}-${name}.png` });
};
const code = () => page.evaluate(() => document.querySelector(".cm-content").innerText);
// Replaces the whole file: a demo student may come back to code from an earlier sitting.
const type = async (text) => {
  await page.click(".cm-content");
  await page.keyboard.press("Control+A");
  await page.keyboard.type(text, { delay: 12 });
};
const admin = async (path) => (await fetch(BASE + path, { headers: { "X-Admin-Token": TOKEN } })).json();

await page.goto(BASE);
await page.fill("input", STUDENT);
await page.click("button[type=submit]");
await page.waitForSelector("text=Your labs");
if (await page.isVisible("text=Before you start")) {
  await page.check("input[type=checkbox]");
  await page.click("button:text-is(\"Start\")");
}
await page.waitForSelector("button:has-text('Start lab'), button:has-text('Continue lab')");
await shot("01-labs");

// --- one sitting: open the lab once, move between questions ----------------------
await page.click("main button:has-text('Count vowels'), button:has-text('Count vowels')");  // opens the lab at question 1
await page.waitForSelector("nav[aria-label='Questions in this lab']");
await page.waitForSelector("text=Question 1 of 3");
assert.equal(await page.locator("[role=tab]").count(), 3, "one editor tab per question");
await type("line = input()\nprint(sum(c in 'aeiouAEIOU' for c in line))\n");
await page.keyboard.press("Control+Enter");
await page.waitForSelector(".output:has-text('5')");
await shot("02-question-1");

await page.click("[role=tab]:has-text('q2')");
await page.waitForSelector("text=Question 2 of 3");
assert.ok(!(await code()).includes("aeiou"), "question 2 starts from its own starter code");
await type("a = input()\nb = input()\nprint('YES' if sorted(a) == sorted(b) else 'NO')\n");
await page.keyboard.press("Control+Enter");
await page.waitForSelector(".output:has-text('YES')");
await shot("03-question-2");

await page.click("nav[aria-label='Questions in this lab'] button:has-text('Count vowels')");
await page.waitForSelector("text=Question 1 of 3");
assert.ok((await code()).includes("aeiouAEIOU"), "question 1 kept its code");
assert.ok(!(await page.textContent(".output")).includes("YES"), "each question keeps its own output");

await page.click("header button:has-text('Finish lab')");
await page.waitForSelector("text=You have written code for 2 of 3 questions");
await shot("04-finish");
await page.click("[role=dialog] button:has-text('Finish lab')");
await page.waitForSelector("text=Lab saved");
await shot("05-saved");

// --- what was recorded -----------------------------------------------------------
const mine = (await admin(`/api/sessions?student_id=${STUDENT}`)).filter((s) => s.sitting_id);  // the seed's sessions have none
const sittings = [...new Set(mine.map((s) => s.sitting_id))];
assert.equal(sittings.length, 1, "one sitting");
assert.equal(mine.length, 2, "a session per question visited (question 3 never opened)");
for (const s of mine) {
  assert.equal(s.end_reason, "submit", "both questions with code are handed in");
  const evs = await admin(`/api/sessions/${s.id}/events?type=focus`);
  assert.ok(evs.some((e) => e.data.target === "question"), "switches are marked on the session");
}

// --- the next sitting picks up where the student left off -------------------------
await page.click("button:has-text('Another task')");
await page.click("button:has-text('Continue lab')");
await page.waitForSelector("nav[aria-label='Questions in this lab']"); // lands on the first unfinished question
await page.click("[role=tab]:has-text('q1')");
await page.waitForSelector("text=Question 1 of 3");
assert.ok((await code()).includes("aeiouAEIOU"), "code carried over to the new sitting");
await shot("06-resumed");
await page.click("header button:has-text('Finish lab')");
await page.click("[role=dialog] button:has-text('Finish lab')");
await page.waitForSelector("text=Lab saved");
const after = (await admin(`/api/sessions?student_id=${STUDENT}`)).filter((s) => s.sitting_id);
assert.equal(new Set(after.map((s) => s.sitting_id)).size, 2, "a second sitting");

assert.deepEqual(errors, []);
await browser.close();
console.log(`ok: ${mine.length} sessions in sitting ${sittings[0]}, then a second sitting resumed the code`);
