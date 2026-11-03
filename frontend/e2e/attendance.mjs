// End-to-end check of attendance through Roll Call, with screenshots for the thesis:
// a teacher connects Roll Call, attaches two class groups to a lab (one made
// from Student IDE), students work in the lab, the teacher previews who counts
// as present, overrides one mark and sends; Roll Call then shows one session per
// class group, filed under the lab's subject. Also checks that old links still open.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo RC=http://127.0.0.1:3100 node frontend/e2e/attendance.mjs [screenshot-dir] [light|dark]
//
// Student IDE in dev mode (STUDENTIDE_ADMIN_TOKEN=$TOKEN, STUDENTIDE_ATTENDANCE_URL=$RC) and a Roll Call
// with a database (DATABASE_URL set) must both be running.

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const RC = process.env.RC ?? "http://127.0.0.1:3100";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const KEY = `e2e${Date.now().toString(36)}`.padEnd(40, "x");
const SUBJECT = "Data Structures";

const browser = await chromium.launch();
const errors = [];
const open = async (w = 1440, h = 900) => {
  const page = await browser.newPage({ viewport: { width: w, height: h }, colorScheme: SCHEME, deviceScaleFactor: 2 });
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("dialog", (d) => d.accept());
  return page;
};
const shot = async (page, name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(1200);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/attendance-${SCHEME}-${name}.png`, fullPage: full });
};
const api = async (method, path, body, headers = { "x-admin-token": TOKEN }) => {
  const r = await fetch(BASE + path, { method, headers: { "content-type": "application/json", ...headers }, body: body && JSON.stringify(body) });
  assert.ok(r.ok, `${method} ${path}: ${r.status} ${await r.clone().text()}`);
  return r.json();
};
const rc = async (method, path, body) => {
  const r = await fetch(RC + path, { method, headers: { "content-type": "application/json", authorization: `Bearer ${KEY}` }, body: body && JSON.stringify(body) });
  assert.ok(r.ok, `${method} ${path}: ${r.status}`);
  return r.json();
};

// Roll Call already has one class group (G2) and the subject
const g2 = await rc("POST", "/api/v1/classes", {
  branch: "CSE", section: "A", group: "G2", roster: { groups: [{ prefix: "UG23CS", start: 4, end: 6, digits: 3, exclude: [] }] },
});
await rc("POST", "/api/v1/subjects", { name: SUBJECT, code: "CS201" });

// a lab ready to attach
let lab = await api("POST", "/api/teach/labs", { title: "Lab 6: Linked lists", subject: SUBJECT, language: "python" });
lab = await api("POST", `/api/teach/labs/${lab.id}/questions`, { title: "Reverse a list", prompt: "Read numbers, print them reversed.", starter_code: "", sample_input: "1 2 3" });
const qid = lab.questions[0].id;

// --- teacher: getting started, connect Roll Call --------------------------------
const t = await open();
await t.goto(`${BASE}/#/teach/setup`);
await t.fill("input[type=password]", TOKEN);
await t.click("button[type=submit]");
await t.waitForSelector("text=Getting started");
await t.waitForSelector("input[aria-label='Roll Call sync key']");
await shot(t, "01-getting-started");
await t.fill("input[aria-label='Roll Call sync key']", KEY);
await t.click("button:has-text('Connect')");
await t.waitForSelector("text=Connected to");

// an old link opens the lab and is rewritten to the current scheme
await t.goto(`${BASE}/#/teach/l/${lab.id}`);
await t.waitForSelector("text=Class groups and attendance");
assert.equal(new URL(t.url()).hash, `#/teach/labs/${lab.id}`);

// attach G2 and a new G1 made from here
await t.click("button:has-text('Attach class groups')");
await t.waitForSelector("text=CSE · A · G2");
await t.click("text=+ New class group in Roll Call");
const form = t.locator("form:has-text('Create in Roll Call')");
await form.getByPlaceholder("CSE").fill("CSE");
await form.getByPlaceholder("A", { exact: true }).fill("A");
await form.getByPlaceholder("G1").fill("G1");
await form.getByPlaceholder("UG23CS").fill("UG23CS");
const nums = form.locator("input[inputmode=numeric]");
await nums.nth(0).fill("1");
await nums.nth(1).fill("3");
await nums.nth(2).fill("3");
await shot(t, "02-new-class-group");
await form.locator("button[type=submit]").click();
await t.waitForSelector("text=CSE · A · G1");
await t.locator("label:has-text('CSE · A · G2') input[type=checkbox]").check();
await t.click("button:has-text('Save')");
await t.waitForSelector("text=Preview, adjust and send");
lab = await api("GET", `/api/teach/labs/${lab.id}`);
assert.deepEqual(lab.roster, ["UG23CS001", "UG23CS002", "UG23CS003", "UG23CS004", "UG23CS005", "UG23CS006"]);
await api("PATCH", `/api/teach/labs/${lab.id}`, { status: "open" });
await t.reload();
await t.waitForSelector("text=CSE · A · G1");
await shot(t, "03-lab-class-groups");

// --- students work in the lab (dev mode: roll number sign-in) ---------------------
const edit = (seq, ms, text, pos, origin = "input.type") =>
  ({ seq, t: ms, type: "edit", data: { origin, changes: [[pos, pos, text]], len_before: pos, len_after: pos + text.length } });
const work = async (sid, minutes, origin = "input.type", run = false) => {
  await api("POST", "/api/consent", { student_id: sid }, {});
  const { session_id } = await api("POST", "/api/sessions", { student_id: sid, question_id: qid }, {});
  const events = [{ seq: 0, t: 0, type: "session_start", data: { wall_clock_ms: Date.now() } }];
  for (let m = 0; m < minutes; m++) events.push(edit(m + 1, m * 60_000 + 500, "abcdefghij", m * 10, origin));
  await api("POST", `/api/sessions/${session_id}/events`, { schema_version: 1, events }, {});
  if (run) await api("POST", `/api/sessions/${session_id}/run`, { code: "print(1)\n", stdin: "" }, {});
};
await work("UG23CS001", 14, "input.type", true);
await work("UG23CS002", 12, "input.paste");
await work("UG23CS003", 11);
await work("UG23CS004", 4);
await work("UG23CS005", 16, "input.type", true);

// --- preview, override, send -------------------------------------------------------
await t.goto(`${BASE}/#/teach/labs/${lab.id}/attendance`);
await t.waitForSelector("text=Not sent yet");
await shot(t, "04-preview", true);
const row = t.locator("tr:has-text('UG23CS004')");
assert.equal(await row.locator("button").innerText(), "A");
await row.locator("button").click();
assert.equal(await row.locator("button").innerText(), "P");
await t.click("button:has-text('Send to Roll Call')");
await t.waitForSelector("text=Sent: ");
await shot(t, "05-sent", true);

const sessions = (await (await fetch(`${RC}/api/sync`, { headers: { "x-sync-key": KEY } })).json()).sessions;
assert.equal(sessions.length, 2);
const g1 = sessions.find((s) => s.group === "G1");
const two = sessions.find((s) => s.group === "G2");
assert.deepEqual(g1.marks, { UG23CS001: "P", UG23CS002: "A", UG23CS003: "P" });
assert.deepEqual(two.marks, { UG23CS004: "P", UG23CS005: "P", UG23CS006: "A" });
assert.equal(g1.subject, SUBJECT);
assert.equal(g1.source.app, "student-ide");

await t.goto(`${BASE}/#/teach/subjects`);
await t.waitForSelector(`text=${SUBJECT}`);
await shot(t, "06-subjects");
await t.click(`text=${SUBJECT}`);
await t.waitForSelector("text=1 day sent");
assert.equal(new URL(t.url()).hash, "#/teach/subjects/data-structures");
await shot(t, "07-subject");

// --- Roll Call side ------------------------------------------------------------------
const r = await open(1280, 860);
await r.goto(`${RC}/settings`);
await r.evaluate((k) => localStorage.setItem("attendance:sync-key", k), KEY);
await r.goto(`${RC}/sessions`);
await r.waitForSelector("text=Student IDE");
await shot(r, "08-rollcall-sessions");
await r.goto(`${RC}/sessions/${g1.id}/report`);
await r.waitForSelector("text=Recorded by Student IDE");
await shot(r, "09-rollcall-report");
await r.goto(`${RC}/subjects`);
await r.waitForSelector(`text=${SUBJECT}`);
await shot(r, "10-rollcall-subjects");
await r.goto(`${RC}/subjects/data-structures`);
await r.waitForSelector("text=students");
await shot(r, "11-rollcall-subject", true);
await r.goto(`${RC}/classes/${g2.id}`);
await r.waitForSelector("text=Edit roster");
await shot(r, "12-rollcall-class");
await r.goto(`${RC}/settings#student-ide`);
await r.waitForSelector("text=Connect Student IDE");
await r.locator("#student-ide").scrollIntoViewIfNeeded();
await shot(r, "13-rollcall-connect");
await r.goto(`${RC}/start`);
await r.waitForSelector("text=Everything a new faculty member needs");
await shot(r, "14-rollcall-start");
await r.goto(`${RC}/session/${g1.id}/done`); // an old link
await r.waitForURL(`${RC}/sessions/${g1.id}/report`);

await browser.close();
assert.deepEqual(errors, []);
console.log("attendance e2e ok", lab.id);
