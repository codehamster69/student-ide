// End-to-end check: drive the real editor in Chromium, then read the stored
// events back through the research API and verify them.
//
//   BASE=http://127.0.0.1:8000 TOKEN=change-me node frontend/e2e/record.mjs [screenshot-dir]
//
// Needs the server running with the built frontend and STUDENTIDE_ADMIN_TOKEN=$TOKEN.

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "change-me";
const SHOTS = process.argv[2];
const STUDENT = `e2e-${Date.now().toString(36)}`;

function replay(events) {
  // JS strings are UTF-16, the same units CodeMirror uses for offsets.
  let doc = null;
  for (const ev of events) {
    if (ev.type === "snapshot") {
      if (doc === null) doc = ev.data.text;
      else assert.equal(doc, ev.data.text, `replay diverged at seq ${ev.seq}`);
    } else if (ev.type === "edit") {
      assert.equal(doc.length, ev.data.len_before, `len_before mismatch at seq ${ev.seq}`);
      for (const [from, to, text] of [...ev.data.changes].reverse()) doc = doc.slice(0, from) + text + doc.slice(to);
      assert.equal(doc.length, ev.data.len_after);
    }
  }
  return doc;
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
page.on("dialog", (d) => d.accept());
// Main-thread tasks over 50 ms; UI animation must not cause any while typing.
await page.addInitScript(() => {
  window.__longTasks = [];
  new PerformanceObserver((l) => window.__longTasks.push(...l.getEntries().map((e) => [e.startTime, e.duration])))
    .observe({ type: "longtask", buffered: true });
});
// Let entrance animations settle so screenshots show the finished screen.
const shot = async (name) => SHOTS && (await page.waitForTimeout(800), page.screenshot({ path: `${SHOTS}/${name}.png` }));

await page.goto(BASE);
await shot("editor-01-login");
await page.fill("input", STUDENT);
await page.click("button[type=submit]");
await page.waitForSelector("text=Before you start");
await shot("editor-02-consent");
await page.check("input[type=checkbox]");
await page.click("button:text-is(\"Start\")");
await page.waitForSelector("text=Choose a task");
await page.click("text=Warm-up: FizzBuzz");
await page.waitForSelector(".cm-content");

// Type like a person: per-key delays, a typo fixed with Backspace.
await page.click(".cm-content");
const typingFrom = await page.evaluate(() => performance.now());
await page.keyboard.press("Control+End");
await page.keyboard.type("for i in range(1, n + 1):\n", { delay: 35 });
await page.keyboard.type("if i % 15 == 0:\nprint(\"FizzBuzx", { delay: 45 });
await page.keyboard.press("Backspace");
await page.keyboard.type("z\")", { delay: 60 });
await page.keyboard.press("End");
await page.keyboard.press("Enter");

const typingTo = await page.evaluate(() => performance.now());
const longTasks = await page.evaluate(([a, b]) => window.__longTasks.filter(([t, d]) => t + d > a && t < b), [typingFrom, typingTo]);

// Paste the rest, as a student copying from elsewhere would.
const pasted = 'elif i % 3 == 0:\n        print("Fizz")\n    elif i % 5 == 0:\n        print("Buzz")\n    else:\n        print(i)';
await page.keyboard.press("Backspace"); // dedent one level to the if
await page.evaluate((text) => {
  const dt = new DataTransfer();
  dt.setData("text/plain", text);
  document.querySelector(".cm-content").dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
}, pasted);

// Leave the tab and come back.
await page.evaluate(() => window.dispatchEvent(new Event("blur")));
await page.waitForTimeout(150);
await page.evaluate(() => window.dispatchEvent(new Event("focus")));

await page.keyboard.press("Control+Enter");
await page.waitForFunction(() => !document.querySelector(".output")?.textContent?.startsWith("Running"));
const output = await page.textContent(".output");
await shot("editor-03-session");
const sessionId = await page.evaluate(() => window.__studentide.sessionId);
await page.click("button:text-is(\"Finish\")");
await page.click("[role=dialog] button:text-is(\"Finish session\")");
await page.waitForSelector("text=Session saved");
await browser.close();

const get = async (path) => {
  const r = await fetch(BASE + path, { headers: { "X-Admin-Token": TOKEN } });
  assert.ok(r.ok, `${path}: ${r.status}`);
  return r.json();
};
const events = await get(`/api/sessions/${sessionId}/events`);
const runs = await get(`/api/sessions/${sessionId}/runs`);
const sessions = await get(`/api/sessions?student_id=${STUDENT}`);

const count = (pred) => events.filter(pred).length;
const seqs = events.map((e) => e.seq);
assert.deepEqual(seqs, [...seqs.keys()], "seq has gaps");
assert.equal(events[0].type, "session_start");
assert.equal(events.at(-1).type, "session_end");
assert.equal(sessions[0].end_reason, "submit");

const downs = count((e) => e.type === "key" && e.data.action === "down");
const ups = count((e) => e.type === "key" && e.data.action === "up");
assert.ok(downs > 50 && Math.abs(downs - ups) <= 2, `key down/up: ${downs}/${ups}`);
assert.ok(count((e) => e.type === "key" && e.data.cls === "backspace") >= 1);
assert.ok(count((e) => e.type === "edit" && e.data.origin === "input.paste") === 1, "paste edit");
assert.ok(count((e) => e.type === "clipboard" && e.data.action === "paste" && e.data.text === pasted) === 1, "clipboard paste");
assert.ok(count((e) => e.type === "focus" && e.data.target === "window") >= 2, "window focus");
assert.ok(count((e) => e.type === "run") === 1 && runs.length === 1, "run");

const finalCode = replay(events);
assert.equal(finalCode, runs[0].code, "replayed code equals the code that was run");
assert.equal(output.trim().split("\n").at(-1), "FizzBuzz", `program output: ${output}`);

// Key timing sanity: typed with ~35-60 ms delays, so median digraph latency is in that range.
const t = events.filter((e) => e.type === "key" && e.data.action === "down" && !e.data.repeat).map((e) => e.t);
const gaps = t.slice(1).map((x, i) => x - t[i]).sort((a, b) => a - b);
const median = gaps[gaps.length >> 1];
assert.ok(median > 20 && median < 200, `median inter-key gap ${median} ms`);

assert.equal(longTasks.length, 0, `long main-thread tasks while typing: ${JSON.stringify(longTasks)}`);

const byType = {};
for (const e of events) byType[e.type] = (byType[e.type] ?? 0) + 1;
console.log(JSON.stringify({ session: sessionId, events: events.length, byType, medianKeyGapMs: Math.round(median * 10) / 10, longTasksWhileTyping: longTasks.length }));
console.log("e2e OK");
