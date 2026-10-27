// End-to-end check of teacher authoring, with screenshots for the thesis:
// a teacher makes a lab, adds questions with starter code, assigns a student
// and opens it; that student sees it, answers question 1 in the editor, and
// the recorded session is linked to the lab and the question.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/teach.mjs [screenshot-dir] [light|dark]
//
// Run against a database seeded with `python -m studentide.seed` so the demo
// lab is there too. The server needs STUDENTIDE_ADMIN_TOKEN=$TOKEN.

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const STUDENT = `E2E${Date.now().toString(36).toUpperCase()}`;
const STARTER = "a = input()\nb = input()\n";

const browser = await chromium.launch();
const errors = [];
const open = async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("dialog", (d) => d.accept());
  return page;
};
const shot = async (page, name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(1200);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/teach-${SCHEME}-${name}.png`, fullPage: full });
};

// --- teacher -----------------------------------------------------------------
const t = await open();
await t.goto(`${BASE}/#/teach`);
await t.waitForSelector("text=Teacher access");
await t.fill("input[type=password]", TOKEN);
await t.click("button[type=submit]");
await t.waitForSelector("text=A lab is one sitting");
await t.waitForSelector("a[href^='#/teach/l/']");
await shot(t, "01-labs");

await t.click("button:has-text('New lab')");
await t.fill("input[placeholder^='Lab 5']", "Lab 7: Anagrams (e2e)");
await t.fill("textarea", "Two short questions. Run your code as often as you like.");
await shot(t, "02-new-lab");
await t.click("button:has-text('Create and add questions')");
await t.waitForSelector("text=Add the first question");
const labId = (await t.evaluate(() => location.hash)).split("/").at(-1);

const addQuestion = async (title, prompt, starter, sample, shotName) => {
  await t.click("button:has-text('Add question') >> nth=0");
  await t.fill("input[placeholder='Anagram check']", title);
  await t.fill("textarea[placeholder^='Read two words']", prompt);
  await t.fill("textarea[placeholder^='a = input()']", starter);
  await t.fill("textarea[placeholder^='listen']", sample);
  if (shotName) await shot(t, shotName);
  await t.click("form button[type=submit]:has-text('Add question')");
  await t.waitForSelector(`strong:text-is("${title}")`);
};
await addQuestion("Anagram check", "Read two words, one per line. Print YES if they are anagrams, otherwise NO.", STARTER, "listen\nsilent", "03-question-form");
await addQuestion("Count vowels", "Read a line and print how many vowels it has.", "line = input()\n", "Programming is fun");

// question 2 first, then back again: reordering must round-trip
await t.click("button[aria-label='Move up'] >> nth=1");
await t.waitForFunction(() => document.querySelector("ol li strong")?.textContent === "Count vowels");
await t.click("button[aria-label='Move down'] >> nth=0");
await t.waitForFunction(() => document.querySelector("ol li strong")?.textContent === "Anagram check");

await t.fill("input[aria-label='Add roll numbers']", `${STUDENT}, PG25CS07`);
await t.click("form:has(input[aria-label='Add roll numbers']) button[type=submit]");
await t.waitForSelector(`button[title=Remove]:has-text("${STUDENT}")`);
await t.click("button[role=radio]:has-text('Open')");
await t.waitForSelector("button[role=radio][aria-checked=true]:has-text('Open')");
await shot(t, "04-lab-open", true);

// --- student -----------------------------------------------------------------
const s = await open();
await s.goto(BASE);
await s.fill("input", STUDENT);
await s.click("button[type=submit]");
await s.waitForSelector("text=Before you start");
await s.check("input[type=checkbox]");
await s.click("button:text-is(\"Start\")");
await s.waitForSelector("text=Your labs");
await s.waitForSelector("text=Lab 7: Anagrams (e2e)");
await shot(s, "05-student-labs", true);
await s.click("button:has-text('Anagram check')");
await s.waitForSelector(".cm-content");
assert.equal(await s.evaluate(() => document.querySelector(".cm-content").innerText.trim()), STARTER.trim(), "starter code in the editor");
await s.click(".cm-content");
await s.keyboard.press("Control+End");
await s.keyboard.type("print('YES' if sorted(a) == sorted(b) else 'NO')", { delay: 30 });
await s.keyboard.press("Control+Enter");
await s.waitForFunction(() => document.querySelector(".output")?.textContent?.trim() === "YES");
await shot(s, "06-student-editor");
const sessionId = await s.evaluate(() => window.__studentide.sessionId);
// A lab with several questions opens as one sitting: "Finish lab" hands in the whole sitting.
await s.click("header button:text-is(\"Finish lab\"), header button:text-is(\"Finish\")");
await s.click("[role=dialog] button:text-is(\"Finish lab\"), [role=dialog] button:text-is(\"Finish session\")");
await s.waitForSelector(":text('Lab saved'), :text('Session saved')");

// --- the recording is linked to the lab and question -------------------------
const get = async (path) => {
  const r = await fetch(BASE + path, { headers: { "X-Admin-Token": TOKEN } });
  assert.ok(r.ok, `${path}: ${r.status}`);
  return r.json();
};
const lab = await get(`/api/teach/labs/${labId}`);
const [session] = await get(`/api/sessions?lab_id=${labId}`);
assert.equal(session.id, sessionId);
assert.equal(session.student_id, STUDENT);
assert.equal(session.question_id, lab.questions[0].id);
assert.equal(session.question_json.starter_code, STARTER);
const events = await get(`/api/sessions/${sessionId}/events`);
assert.equal(events.at(-1).type, "session_end");
assert.ok(events.filter((e) => e.type === "key").length > 40, "keys recorded");
assert.deepEqual(lab.progress.map((p) => [p.student_id, p.submitted]), [[STUDENT, true]]);

await t.reload();
await t.waitForSelector("table svg.text-success");
await shot(t, "07-progress", true);

// the seeded demo lab, with the simulated class's progress
const demo = (await get("/api/teach/labs")).find((l) => l.id === "lab_demo1");
if (demo) {
  await t.goto(`${BASE}/#/teach/l/${demo.id}`);
  await t.waitForSelector("text=Count vowels");
  await shot(t, "08-demo-lab", true);
  await t.goto(`${BASE}/#/review`);
  await t.waitForSelector("text=Sessions reviewed");
  await t.waitForSelector("text=Anagram check");
}

await browser.close();
assert.deepEqual(errors, [], `page errors: ${errors.join("; ")}`);
console.log(JSON.stringify({ lab: labId, session: sessionId, events: events.length, questions: lab.questions.length }));
console.log("teach e2e OK");
