// End-to-end check of the competition hand-in and the staff leaderboard, with
// screenshots for the thesis: a teacher runs a competition; a student types a
// solution but never presses Submit; when the teacher ends the clock the
// student's editor hands the code in by itself and, after the grace period,
// the board scores it. The owner, a co-teacher and an admin all reach the
// leaderboard from the labs list, the lab page and the live class view.
//
//   BASE=http://127.0.0.1:8011 node frontend/e2e/handin.mjs [screenshot-dir] [light|dark]
//
// Needs a server in Google mode whose token check accepts the address as the
// credential (tests' fake_google), with admin rohan.admin@iiitsurat.ac.in.

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8011";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const D = "@iiitsurat.ac.in";
const ADMIN = `rohan.admin${D}`, PRIYA = `priya.shah${D}`, MEERA = `meera.rao${D}`;
const STUDENT = "PG25CS01", CLASSMATE = "PG25CS02";
const GRACE_S = 20; // compete.GRACE_S

const browser = await chromium.launch();
const errors = [];
const as = async (email) => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  const r = await page.request.post(`${BASE}/api/auth/google`, { data: { credential: email } });
  assert.equal(r.status(), 200, `sign in ${email}`);
  return page;
};
const call = async (page, method, path, data) => {
  const r = await page.request.fetch(BASE + path, { method, data });
  assert.ok(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`);
  return r.json();
};
const shot = async (page, name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(1200);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/handin-${SCHEME}-${name}.png`, fullPage: full });
};

// --- Priya sets up a competition and shares it with Meera ---------------------------
const priya = await as(PRIYA);
const comp = await call(priya, "POST", "/api/teach/competitions", { title: "Friday sprint", duration_min: 20, language: "python" });
const labId = comp.lab_id;
await call(priya, "POST", `/api/teach/labs/${labId}/questions`, {
  title: "Add two numbers", prompt: "Read two integers on one line and print their sum.",
  starter_code: "a, b = map(int, input().split())\n", sample_input: "2 3",
  tests: [{ name: "small", stdin: "2 3", expected: "5" }, { name: "large", stdin: "1000000 2345678", expected: "3345678", hidden: true }] });
await call(priya, "PUT", `/api/teach/labs/${labId}/roster`, { student_ids: [STUDENT, CLASSMATE], everyone: false });
await call(priya, "PUT", `/api/teach/labs/${labId}/teachers`, { co_teachers: [MEERA] });
await call(priya, "PATCH", `/api/teach/labs/${labId}`, { status: "open" });
await call(priya, "POST", `/api/teach/competitions/${labId}/start`);

// a classmate submits a partial answer the ordinary way
const mate = await as(CLASSMATE.toLowerCase() + D);
await call(mate, "POST", "/api/consent", { student_id: CLASSMATE });
await call(mate, "POST", `/api/competitions/${labId}/join`, { student_id: CLASSMATE, handle: "Grace" });
const qid = (await call(mate, "GET", `/api/competitions/${labId}?student_id=${CLASSMATE}`)).questions[0].id;
const ms = await call(mate, "POST", "/api/sessions", { student_id: CLASSMATE, question_id: qid, client_meta: { synthetic: true } });
await call(mate, "POST", `/api/sessions/${ms.session_id}/submit`, { code: "print(5)\n" });

// --- the student types a full solution and never presses Submit ------------------------
const s = await as(STUDENT.toLowerCase() + D);
await call(s, "POST", "/api/consent", { student_id: STUDENT });
await call(s, "POST", `/api/competitions/${labId}/join`, { student_id: STUDENT, handle: "Ada" });
await s.goto(BASE);
await s.click("button:has-text('Friday sprint')");
await s.click("button:has-text('Add two numbers')");
await s.waitForSelector(".cm-content");
await s.click(".cm-content");
await s.keyboard.press("Control+End");
await s.keyboard.type("print(a + b)", { delay: 25 });
await s.waitForSelector("[role=timer]");
await shot(s, "01-editor-clock");

// --- staff: the leaderboard from every teacher screen -------------------------------------
for (const [email, who] of [[PRIYA, "owner"], [MEERA, "co-teacher"], [ADMIN, "admin"]]) {
  const t = await as(email);
  await t.goto(`${BASE}/#/teach`);
  await t.waitForSelector("text=Friday sprint");
  await t.click("[role=link]:has-text('Leaderboard')");
  await t.waitForSelector("text=Class competition");
  assert.ok(await t.isVisible("text=Grace"), `${who} sees the board`);
  if (who === "owner") {
    await shot(t, "02-board-live", true);
    await t.goto(`${BASE}/#/teach`);
    await t.waitForSelector("text=Friday sprint");
    await shot(t, "03-labs-list");
    await t.goto(`${BASE}/#/teach/l/${labId}`);
    await t.waitForSelector("text=Open leaderboard");
    assert.ok(await t.isVisible("button:has-text('Leaderboard')"), "lab page links the board");
    await shot(t, "04-lab-page");
    await t.goto(`${BASE}/#/live/l/${labId}`);
    await t.click("button:has-text('Leaderboard')");
    await t.waitForSelector("text=Class competition");
  }
  await t.context().close();
}

// --- the teacher ends early: the editor hands in by itself --------------------------------
await call(priya, "POST", `/api/teach/competitions/${labId}/end`);
await s.waitForSelector("text=being handed in", { timeout: 15_000 });
await shot(s, "05-arena-handing-in");
const t = await as(PRIYA);
await t.goto(`${BASE}/#/teach/c/${labId}`);
await t.waitForSelector("text=Handing in and grading");
await shot(t, "06-board-handing-in");
await t.waitForSelector("text=Handing in and grading", { state: "detached", timeout: (GRACE_S + 15) * 1000 });
await shot(t, "07-board-final", true);

const board = (await call(priya, "GET", `/api/teach/competitions/${labId}`)).board;
const ada = board.find((r) => r.student_id === STUDENT);
assert.equal(ada.rank, 1, "the handed-in full solve tops the board");
assert.equal(ada.solved, 1);
assert.equal(ada.questions[0].auto, true);
assert.equal(board.find((r) => r.student_id === CLASSMATE).questions[0].auto, false);
await s.waitForSelector("text=At the bell", { timeout: 10_000 });
await shot(s, "08-arena-final", true);

assert.deepEqual(errors, [], "no page errors");
await browser.close();
console.log("hand-in e2e ok:", board.map((r) => [r.handle, r.points, r.solved]));
