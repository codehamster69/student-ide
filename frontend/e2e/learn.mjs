// End-to-end check of the learning lab, with screenshots for the thesis: a
// student opens it from the home page, reads a C lesson, loads an example
// with "Try it", changes and runs it, solves the exercise and presses Check,
// moves to the next lesson, and on returning finds the lesson marked done.
// Practice is recorded but must stay out of everything teachers see.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/learn.mjs [screenshot-dir] [light|dark]
//
// Run against a database seeded with `python -m studentide.seed`, on a server with gcc.

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
  await page.screenshot({ path: `${OUT}/learn-${SCHEME}-${name}.png` });
};
const code = () => page.evaluate(() => document.querySelector(".cm-content").innerText);
// Replaces the whole file in one input (typing key by key would trip the editor's auto-indent and bracket closing).
const type = async (text) => {
  await page.click(".cm-content");
  await page.keyboard.press("Control+A");
  await page.keyboard.insertText(text);
};
const admin = async (path) => (await fetch(BASE + path, { headers: { "X-Admin-Token": TOKEN } })).json();
const before = (await admin("/api/sessions")).length;

await page.goto(BASE);
await page.fill("input", STUDENT);
await page.click("button[type=submit]");
await page.waitForSelector("h1");
if (await page.isVisible("text=Before you start")) {
  await page.check("input[type=checkbox]");
  await page.click("button:text-is(\"Start\")");
}
await page.waitForSelector("text=Always open");
await shot("01-home");

// --- the lesson list -------------------------------------------------------------
await page.click("button:has-text('Learning lab')");
for (const t of ["C 1 · Beginner", "C 2 · Advanced", "Python 1 · Beginner", "Python 2 · Intermediate", "Python 3 · Advanced"]) {
  await page.waitForSelector(`h2:has-text('${t}')`);
}
await shot("02-lessons");

// --- a lesson: read, try the example, change it, run ---------------------------------
await page.click("button:has-text('Loops'):has-text('for and while')");
await page.waitForSelector("text=lesson 6 of 12");
assert.match(await code(), /sum of its digits|add up the digits/, "the editor opens with the exercise starter");
await page.click("button:has-text('Try it') >> nth=0");
assert.match(await code(), /squared is/, "Try it loads the example");
await page.keyboard.press("Control+Enter");
await page.waitForSelector(".output:has-text('5 squared is 25')");
await shot("03-example-run");
// change the example: count to 3 instead of 5
await page.click(".cm-content");
await page.keyboard.press("Control+Home");
await page.keyboard.press("ArrowDown");
await page.keyboard.press("ArrowDown");
await page.keyboard.press("ArrowDown");
await page.keyboard.press("End");
const line = await page.evaluate(() => document.querySelectorAll(".cm-line")[3].innerText);
assert.match(line, /i <= 5; i\+\+\) \{$/);
for (let k = 0; k < 8; k++) await page.keyboard.press("ArrowLeft");
await page.keyboard.press("Backspace");
await page.keyboard.type("3");
await page.keyboard.press("Control+Enter");
await page.waitForSelector(".output:has-text('3 squared is 9')");
assert.ok(!(await page.isVisible(".output:has-text('4 squared')")));

// --- the lesson pane scrolls, and every pane can be resized by dragging its edge -----
const panel = () => page.evaluate(() => { const d = document.querySelector("aside > div"); return { w: d.offsetWidth, top: d.scrollTop }; });
await page.mouse.move(200, 500);
await page.mouse.wheel(0, 800);
await page.waitForTimeout(300);
assert.ok((await panel()).top > 0, "the lesson text scrolls");
const drag = async (label, dx, dy) => {
  const b = await page.locator(`[role=separator][aria-label='${label}']`).boundingBox();
  const x = b.x + b.width / 2, y = b.y + b.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx, y + dy, { steps: 6 });
  await page.mouse.up();
  await page.waitForTimeout(200);
};
const w0 = (await panel()).w;
await drag("Lesson width", 160, 0);
assert.ok((await panel()).w > w0 + 100, "the lesson pane widens");
const consoleH = () => page.evaluate(() => document.querySelector("section[style]").offsetHeight);
const h0 = await consoleH();
await drag("Output height", 0, -150);
assert.ok((await consoleH()) > h0 + 100, "the output pane grows");
await drag("Output height", 0, 150);
await drag("Lesson width", -160, 0);

// --- the exercise: wrong, then right ---------------------------------------------------
await type(`#include <stdio.h>

int main(void) {
    int n;
    scanf("%d", &n);
    int sum = 0;
    while (n > 0) {
        sum += n % 10;
        n /= 10;
    }
    printf("%d\\n", sum);
    return 0;
}
`);
await page.click("button:has-text('Check')");
await page.waitForSelector("text=4/4");
await shot("04-exercise-checked");

// --- next lesson keeps the track; this one shows as done -------------------------------
await page.click("button:has-text('Next')");
await page.waitForSelector("text=lesson 7 of 12");
await page.waitForSelector("text=Write the function");
await shot("05-next-lesson");
await page.click("button:has-text('All lessons')");
await page.waitForSelector("text=1 of 12 done");
await shot("06-progress");

// --- reopening the lesson brings the code back --------------------------------------
await page.click("button:has-text('Loops'):has-text('for and while')");
await page.waitForSelector("text=lesson 6 of 12");
assert.match(await code(), /sum \+= n % 10/, "the lesson opens with the student's last code");
await page.click("button:has-text('All lessons')");
await page.waitForSelector("text=1 of 12 done");

// --- teachers see none of it ------------------------------------------------------------
assert.equal((await admin("/api/sessions")).length, before, "learning-lab sessions never reach review");
assert.deepEqual(errors, []);
await browser.close();
console.log("learning lab e2e ok");
