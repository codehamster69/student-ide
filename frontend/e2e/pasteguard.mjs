// End-to-end check of the paste guard (schema v4): copy and paste inside the editor works and is
// logged as "input.paste.internal"; text copied from the question counts as inside; a paste from
// outside is blocked with a notice and logged as a blocked clipboard event with no edit.
//
//   BASE=http://127.0.0.1:8000 TOKEN=change-me node frontend/e2e/pasteguard.mjs [screenshot-dir]

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "change-me";
const SHOTS = process.argv[2];
const STUDENT = `paste-${Date.now().toString(36)}`;

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
const page = await context.newPage();
page.on("dialog", (d) => d.accept());

await page.goto(BASE);
await page.fill("input", STUDENT);
await page.click("button[type=submit]");
await page.waitForSelector("text=Before you start");
await page.check("input[type=checkbox]");
await page.click("button:text-is(\"Start\")");
await page.waitForSelector("text=Choose a task");
await page.click("text=Warm-up: FizzBuzz");
await page.waitForSelector(".cm-content");

// 1. Copy a line of my own code and paste it: allowed, origin input.paste.internal.
await page.click(".cm-content");
await page.keyboard.press("Control+End");
await page.keyboard.press("Enter");
await page.keyboard.type("total = 0", { delay: 20 });
await page.keyboard.press("Shift+Home");
await page.keyboard.press("Control+c");
await page.keyboard.press("End");
await page.keyboard.press("Enter");
await page.keyboard.press("Control+v");
const doc = await page.evaluate(() => document.querySelector(".cm-content").innerText);
assert.equal(doc.split("total = 0").length - 1, 2, `own paste reached the editor: ${doc}`);

// 2. Copy text from the question statement and paste it: allowed (source "page").
const quote = await page.evaluate(() => {
  const p = [...document.querySelectorAll("p, li")].find((el) => !el.closest(".cm-editor") && el.textContent.trim().length > 12);
  const r = document.createRange();
  r.selectNodeContents(p.firstChild ?? p);
  getSelection().removeAllRanges();
  getSelection().addRange(r);
  return getSelection().toString();
});
await page.keyboard.press("Control+c");
await page.click(".cm-content");
await page.keyboard.press("Control+End");
await page.keyboard.press("Enter");
await page.keyboard.type("# ");
await page.keyboard.press("Control+v");

// 3. Paste from outside (an LLM answer on another page): blocked, notice shown, nothing inserted.
const outside = "def fizzbuzz(n):\n    return [str(i) for i in range(n)]";
await page.evaluate(async (text) => navigator.clipboard.writeText(text), outside); // as if copied in another app
await page.keyboard.press("Control+v");
await page.waitForSelector("text=Pasting from outside Scribelab is turned off here");
SHOTS && await page.screenshot({ path: `${SHOTS}/paste-blocked.png` });
const after = await page.evaluate(() => document.querySelector(".cm-content").innerText);
assert.ok(!after.includes("def fizzbuzz"), "outside paste was blocked");

const sessionId = await page.evaluate(() => window.__studentide.sessionId);
await page.click("button:text-is(\"Finish\")");
await page.click("[role=dialog] button:text-is(\"Finish session\")");
await page.waitForSelector("text=Session saved");
await browser.close();

const r = await fetch(`${BASE}/api/sessions/${sessionId}/events`, { headers: { "X-Admin-Token": TOKEN } });
const events = await r.json();
const clips = events.filter((e) => e.type === "clipboard" && e.data.action === "paste").map((e) => e.data);
const origins = events.filter((e) => e.type === "edit").map((e) => e.data.origin);
assert.deepEqual(clips.map((c) => [c.source, c.blocked]), [["editor", false], ["page", false], ["external", true]], JSON.stringify(clips));
assert.equal(origins.filter((o) => o === "input.paste.internal").length, 2, origins.join(","));
assert.equal(origins.filter((o) => o === "input.paste").length, 0);
assert.equal(clips[2].text, outside);
console.log(JSON.stringify({ session: sessionId, pastes: clips.map((c) => `${c.source}${c.blocked ? " (blocked)" : ""}`), quote: quote.slice(0, 40) }));
console.log("paste guard e2e OK");
