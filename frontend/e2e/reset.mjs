// End-to-end check of the editor's Reset button, with screenshots for the thesis:
// a student comes back to a lab question (the editor resumes their code), resets
// it to the starter code, undoes the reset with Ctrl+Z, and resets again. The
// reset is recorded as one edit with origin "reset", which the detector skips.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/reset.mjs [screenshot-dir] [light|dark]
//
// Run against a database seeded with `python -m studentide.seed` (lab_demo1
// is open, DEMO01-06 are on its roster and have consented).

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const STUDENT = process.env.STUDENT ?? "DEMO04";
const [OUT, SCHEME = "light"] = process.argv.slice(2);

const browser = await chromium.launch();
const errors = [];
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
page.on("pageerror", (e) => errors.push(e.message));
const shot = async (name) => {
  if (!OUT) return;
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/reset-${SCHEME}-${name}.png` });
};
const code = () => page.evaluate(() => document.querySelector(".cm-content").innerText);
const admin = async (path) => (await fetch(BASE + path, { headers: { "X-Admin-Token": TOKEN } })).json();
const openLab = async (button) => {
  await page.click(button);
  await page.waitForSelector("text=Question 1 of 3");
};
const finish = async () => {
  await page.click("header button:has-text('Finish lab')");
  await page.click("[role=dialog] button:has-text('Finish lab')");
  await page.waitForSelector("text=Lab saved");
};

await page.goto(BASE);
await page.fill("input", STUDENT);
await page.click("button[type=submit]");
await page.waitForSelector("text=Your labs");
if (await page.isVisible("text=Before you start")) {
  await page.check("input[type=checkbox]");
  await page.click("button:text-is(\"Start\")");
}

// --- first sitting: write some code on question 1 ----------------------------------
await openLab("button:has-text('Count vowels')");
const starter = await code();
await page.click(".cm-content");
await page.keyboard.press("Control+End");
await page.keyboard.type("\n# my attempt\nprint(len(input()))\n", { delay: 12 });
const mineCode = await code();
assert.notEqual(mineCode, starter);
await finish();

// --- next sitting resumes it; Reset brings the starter back --------------------------
await page.click("button:has-text('Another task')");
await openLab("button:has-text('Continue lab'), button:has-text('Start lab')");
await page.click("[role=tab]:has-text('q1')");
assert.ok((await code()).includes("# my attempt"), "the editor resumes the student's code");
await page.click("button:has-text('Reset')");
await page.waitForSelector("text=Start again from the starter code?");
await shot("01-confirm");
await page.click("[role=dialog] button:has-text('Keep my code')");
assert.ok((await code()).includes("# my attempt"), "cancelling keeps the code");

await page.click("button:has-text('Reset')");
await page.click("[role=dialog] button:has-text('Reset to starter code')");
await page.waitForFunction((s) => document.querySelector(".cm-content").innerText === s, starter);
await shot("02-starter");

await page.keyboard.press("Control+z");
assert.ok((await code()).includes("# my attempt"), "Ctrl+Z undoes the reset");
await page.click("button:has-text('Reset')");
await page.click("[role=dialog] button:has-text('Reset to starter code')");
await page.waitForFunction((s) => document.querySelector(".cm-content").innerText === s, starter);
await finish();

// --- what was recorded ---------------------------------------------------------------
const last = (await admin(`/api/sessions?student_id=${STUDENT}`)).filter((s) => s.sitting_id && s.task_id)
  .sort((a, b) => (a.started_at < b.started_at ? 1 : -1))[0];
const edits = await admin(`/api/sessions/${last.id}/events?type=edit`);
const resets = edits.filter((e) => e.data.origin === "reset");
assert.equal(resets.length, 2, "each reset is one edit with origin 'reset'");
assert.ok(edits.some((e) => e.data.origin === "undo"), "the undo is recorded too");

assert.deepEqual(errors, []);
await browser.close();
console.log(`ok: ${resets.length} resets recorded on session ${last.id}`);
