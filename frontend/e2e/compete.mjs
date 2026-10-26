// End-to-end check of class competitions, with screenshots for the thesis:
// a teacher creates a competition, adds two questions with test cases and
// opens the lobby; a student joins under a board name, the teacher starts the
// clock, the student solves question 1 in the editor and submits; six
// classmates (driven through the API) submit too; the board ranks them, the
// teacher ends it and both sides see the podium.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/compete.mjs [screenshot-dir] [light|dark]
//
// The server needs STUDENTIDE_ADMIN_TOKEN=$TOKEN. Any database works.

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const TAG = Date.now().toString(36).toUpperCase();
const STUDENT = `E2E${TAG}`;
const CLASS = ["Ada", "Grace", "Linus", "Guido", "Ken", "Barbara"].map((h, i) => ({ id: `C${TAG}${i}`, handle: `${h} ${TAG.slice(-2)}` }));

const api = async (method, path, body, admin = false) => {
  const r = await fetch(BASE + path, {
    method,
    headers: { "Content-Type": "application/json", ...(admin ? { "X-Admin-Token": TOKEN } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  assert.ok(r.ok, `${method} ${path}: ${r.status} ${JSON.stringify(data)}`);
  return data;
};

const browser = await chromium.launch();
const errors = [];
const open = async () => {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
  page.on("pageerror", (e) => errors.push(e.message));
  return page;
};
const shot = async (page, name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(1400);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/compete-${SCHEME}-${name}.png`, fullPage: full });
};

// --- teacher creates the competition -----------------------------------------
const t = await open();
await t.goto(`${BASE}/#/teach`);
await t.fill("input[type=password]", TOKEN);
await t.click("button[type=submit]");
await t.waitForSelector("text=A lab is one sitting");
await t.click("button:has-text('New competition')");
await t.fill("input[placeholder^='Friday sprint']", `Friday sprint ${TAG}`);
await t.fill("textarea", "Two quick ones. Pass the tests, climb the board.");
await t.fill("input[type=number]", "20");
await shot(t, "01-new-competition");
await t.click("button:has-text('Create and add questions')");
await t.waitForSelector("text=Add the first question");
const labId = (await t.evaluate(() => location.hash)).split("/").at(-1);

const Q = [
  { title: "Add two numbers", prompt: "Read two integers on one line and print their sum.", starter_code: "a, b = map(int, input().split())\n",
    sample_input: "2 3", tests: [
      { name: "small", stdin: "2 3", expected: "5" }, { name: "negative", stdin: "-4 1", expected: "-3" },
      { name: "large", stdin: "1000000 2345678", expected: "3345678", hidden: true }] },
  { title: "Count vowels", prompt: "Read a line and print how many vowels (a, e, i, o, u) it has.", starter_code: "line = input()\n",
    sample_input: "Programming is fun", tests: [
      { name: "sentence", stdin: "Programming is fun", expected: "5" }, { name: "capitals", stdin: "AEIOU xyz", expected: "5", hidden: true }] },
];
for (const q of Q) await api("POST", `/api/teach/labs/${labId}/questions`, q, true);
await api("PUT", `/api/teach/labs/${labId}/roster`, { student_ids: [STUDENT, ...CLASS.map((c) => c.id)], everyone: false }, true);
await t.reload();
await t.waitForSelector("text=Add two numbers");
await t.click("button[role=radio]:has-text('Open')");
await t.waitForSelector("text=Lobby open");
await shot(t, "02-teacher-setup", true);

// --- lobby -------------------------------------------------------------------
for (const c of CLASS.slice(0, 4)) {
  await api("POST", "/api/consent", { student_id: c.id });
  await api("POST", `/api/competitions/${labId}/join`, { student_id: c.id, handle: c.handle });
}
const s = await open();
await s.goto(BASE);
await s.fill("input", STUDENT);
await s.click("button[type=submit]");
await s.waitForSelector("text=Before you start");
await s.check("input[type=checkbox]");
await s.click("button:text-is(\"Start\")");
await s.waitForSelector(`text=Friday sprint ${TAG}`);
await shot(s, "03-student-labs");
await s.click(`button:has-text('Friday sprint ${TAG}')`);
await s.waitForSelector("text=Join the competition");
await s.fill("input[aria-label='Name on the board']", "Rohan");
await s.click("button[type=submit]:has-text('Join')");
await s.waitForSelector("text=You're in");
await shot(s, "04-lobby");

// --- the clock starts ----------------------------------------------------------
await t.click("button:has-text('Start the clock')");
await t.waitForSelector("text=End now");
await s.waitForSelector("text=Add two numbers", { timeout: 10_000 });

// classmates submit first, so the student climbs past some of them
const submitAs = async (c, qi, code) => {
  const q = (await api("GET", `/api/competitions/${labId}?student_id=${c.id}`)).questions[qi];
  const { session_id } = await api("POST", "/api/sessions", { student_id: c.id, question_id: q.id, client_meta: { synthetic: true } });
  return api("POST", `/api/sessions/${session_id}/submit`, { code });
};
const ADD = "a, b = map(int, input().split())\nprint(a + b)\n";
const VOWELS = "line = input()\nprint(sum(ch in 'aeiouAEIOU' for ch in line))\n";
for (const c of CLASS.slice(4)) await api("POST", "/api/consent", { student_id: c.id });
await submitAs(CLASS[0], 0, ADD);
await submitAs(CLASS[0], 1, VOWELS);
await submitAs(CLASS[1], 0, ADD);
await submitAs(CLASS[2], 0, "a, b = input().split()\nprint(a + b)\n");      // string concat: fails
await submitAs(CLASS[3], 1, "line = input()\nprint(sum(ch in 'aeiou' for ch in line))\n"); // misses capitals
await submitAs(CLASS[4], 0, "print(5)\n");                                      // passes one test only

await s.waitForSelector("text=Leaderboard");
await shot(s, "05-arena-live", true);
await s.click("button:has-text('Add two numbers')");
await s.waitForSelector(".cm-content");
await s.click(".cm-content");
await s.keyboard.press("Control+End");
await s.keyboard.type("print(a - b)", { delay: 30 });
await s.click("button:has-text('Submit')");
await s.waitForSelector("text=tests passed");
await shot(s, "06-submit-partial");
await s.click("[role=dialog] button:has-text('Fix and retry')");
for (let i = 0; i < 5; i++) await s.keyboard.press("Backspace");
await s.keyboard.type("+ b)", { delay: 30 });
await s.click("button:has-text('Submit')");
await s.waitForSelector("text=All tests passed!");
const result = await s.evaluate(() => document.querySelector("[role=dialog]")?.textContent ?? "");
await shot(s, "07-submit-solved");
await s.click("[role=dialog] button:has-text('Back to board')");
await s.click("[role=dialog] button:has-text('Back to board')");
await s.waitForSelector("text=Leaderboard");
await submitAs(CLASS[5], 0, ADD);

// --- teacher's live board ------------------------------------------------------
await t.goto(`${BASE}/#/teach/c/${labId}`);
await t.waitForSelector("text=Rohan");
await shot(t, "08-live-board", true);

const board = await api("GET", `/api/teach/competitions/${labId}`, undefined, true);
const ranks = board.board.map((r) => [r.handle, r.points, r.solved]);
assert.equal(board.board[0].handle, CLASS[0].handle, "two solves beat one");
const me = board.board.find((r) => r.student_id === STUDENT);
assert.equal(me.solved, 1);
assert.equal(me.questions[0].tries, 2);
assert.ok(board.board.find((r) => r.student_id === CLASS[4].id).points === 33, "partial credit: 1 of 3 tests");
assert.equal(board.board.find((r) => r.student_id === CLASS[2].id).points, 0, "a wrong answer costs nothing and earns nothing");

// --- end ----------------------------------------------------------------------
await api("POST", `/api/teach/competitions/${labId}/end`, {}, true);
await t.waitForSelector("text=Time's up", { timeout: 10_000 });
const after = await api("GET", `/api/teach/competitions/${labId}`, undefined, true);
assert.deepEqual(after.board.map((r) => [r.handle, r.points]), board.board.map((r) => [r.handle, r.points]),
  "ending early keeps every score as it was");
await shot(t, "09-podium", true);
await s.waitForSelector("text=Final standings", { timeout: 10_000 });
await shot(s, "10-student-final", true);

const sess = await api("GET", `/api/sessions?lab_id=${labId}`, undefined, true);
const mine = sess.find((x) => x.student_id === STUDENT);
const events = await api("GET", `/api/sessions/${mine.id}/events`, undefined, true);
assert.ok(events.filter((e) => e.type === "key").length > 10, "competition typing is recorded like any lab");

await browser.close();
assert.deepEqual(errors, [], `page errors: ${errors.join("; ")}`);
console.log(JSON.stringify({ lab: labId, ranks, result: result.slice(0, 80) }));
console.log("compete e2e OK");
