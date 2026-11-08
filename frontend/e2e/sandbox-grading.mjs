// End-to-end check of Sandbox Lab grading (teacher side), with thesis screenshots:
// a published lab with two assignments (visible + hidden tests), students
// submit through the workspace upload the desktop app uses, the server grades
// each Submit, and the lab opens on its Submissions gradebook; one cell opens
// the test results. Also checks that a student sees hidden tests by name only
// and that a Submit after the due time is refused.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/sandbox-grading.mjs [screenshot-dir] [light|dark]
//
// The server needs STUDENTIDE_ADMIN_TOKEN=$TOKEN and a grading driver: previews on
// this machine (STUDENTIDE_PREVIEW_DOCKER=1 STUDENTIDE_PREVIEW_BUILD_LOCAL=1, Docker
// running) or STUDENTIDE_PREVIEW_URL. Students' files below say which tests they pass
// only to a stand-in driver; with real Docker they are graded as C programs.

import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const H = { "x-admin-token": TOKEN, "content-type": "application/json" };
const api = async (method, path, body) => {
  const r = await fetch(BASE + path, { method, headers: H, body: body && JSON.stringify(body) });
  const text = await r.text();
  assert.ok(r.ok, `${method} ${path}: ${r.status} ${text}`);
  return JSON.parse(text);
};

/** A gzip tar of {name: text}, as the desktop app uploads a workspace. */
function tgz(files) {
  const blocks = [];
  for (const [name, text] of Object.entries(files)) {
    const data = Buffer.from(text);
    const h = Buffer.alloc(512);
    h.write(`./${name}`, 0); h.write("0000644\0", 100); h.write("0001750\0", 108); h.write("0001750\0", 116);
    h.write(data.length.toString(8).padStart(11, "0") + "\0", 124); h.write("00000000000\0", 136);
    h.write("        ", 148); h.write("0", 156); h.write("ustar\0" + "00", 257);
    let sum = 0; for (const b of h) sum += b;
    h.write(sum.toString(8).padStart(6, "0") + "\0 ", 148);
    blocks.push(h, data, Buffer.alloc((512 - (data.length % 512)) % 512));
  }
  return gzipSync(Buffer.concat([...blocks, Buffer.alloc(1024)]));
}
const submit = (student, labId, aid, main, reason = "submit") => fetch(
  `${BASE}/api/workspaces/${labId}/${aid}?student_id=${student}`, {
    method: "PUT", body: tgz({ "main.c": main, Makefile: "main: main.c\n\tcc -o main main.c\n" }),
    headers: { "content-type": "application/gzip", "x-workspace-reason": reason,
               "x-workspace-sha256": createHash("sha256").update(student + main + reason).digest("hex") } });

// a published lab of two assignments, each with two visible and two hidden tests
const subject = await api("POST", "/api/sandbox/subjects", { title: "Programming in C (e2e)", code: "CS101", semester: "Autumn 2026", recipe: { base: "c-cpp", tools: [] } });
await api("PUT", `/api/sandbox/subjects/${subject.id}/roster`, { text: "A: UG24CS001 to UG24CS008\nB: UG24CS009 to UG24CS010" });
let lab = await api("POST", `/api/sandbox/subjects/${subject.id}/labs`, { title: "Loops and arrays" });
const cases = (pairs) => pairs.map(([stdin, expected, hidden], i) => ({ name: hidden ? `hidden ${i - 1}` : `sample ${i + 1}`, stdin, expected, hidden }));
for (const [title, tests] of [["Sum of N numbers", cases([["3\n1 2 3\n", "6\n"], ["1\n5\n", "5\n"], ["0\n", "0\n", true], ["4\n-1 -2 3 4\n", "4\n", true]])],
                              ["Reverse an array", cases([["3\n1 2 3\n", "3 2 1\n"], ["1\n9\n", "9\n"], ["2\n0 0\n", "0 0\n", true], ["5\n5 4 3 2 1\n", "1 2 3 4 5\n", true]])]]) {
  lab = await api("POST", `/api/sandbox/labs/${lab.id}/assignments`, {
    title, statement: "Read N, then N integers.", files: [{ path: "main.c", content: "#include <stdio.h>\nint main(void) {\n    return 0;\n}\n" }],
    open: ["main.c"], run: "make -s && ./main", tests: { kind: "io", timeout_s: 5, cases: tests } });
}
await api("PATCH", `/api/sandbox/labs/${lab.id}`, { status: "published" });
const [a1, a2] = (await api("GET", `/api/sandbox/labs/${lab.id}`)).definition.assignments.map((a) => a.id);

// students submit: all pass, some pass, a retry, one never submits. With the stand-in
// driver main.c names the program and its bug; real Docker compiles whatever it holds.
const ok = { sum: "// sum", rev: "// reverse" };
const plan = {
  UG24CS001: [[ok.sum], [ok.rev]], UG24CS002: [[ok.sum], ["// reverse neg", ok.rev]],
  UG24CS003: [["// sum neg zero"], null], UG24CS004: [[ok.sum], ["// reverse neg"]],
  UG24CS005: [["// wrong"], null], UG24CS006: [[ok.sum], [ok.rev]], UG24CS007: [["// sum zero", "// sum neg"], [ok.rev]],
  UG24CS009: [[ok.sum], ["// reverse zero"]],
};
for (const [student, [x1, x2]] of Object.entries(plan)) {
  for (const [aid, tries] of [[a1, x1], [a2, x2]]) for (const main of tries ?? []) {
    const r = await submit(student, lab.id, aid, main);
    assert.equal(r.status, 200, await r.text());
  }
}

// the student's view: hidden tests by name and pass only
for (let i = 0; i < 40; i++) {  // grading is a queue: wait for it
  const t = await api("GET", `/api/sandbox/labs/${lab.id}/submissions`);
  if (!t.grader.queued) break;
  await new Promise((r) => setTimeout(r, 500));
}
const mine = await (await fetch(`${BASE}/api/sandbox/my/labs/${lab.id}/submissions?student_id=UG24CS003`)).json();
const hidden = mine.assignments[a1].results.find((r) => r.hidden);
assert.deepEqual(Object.keys(hidden).sort(), ["hidden", "name", "passed", "timed_out"]);
assert.equal(mine.assignments[a1].passed, 2);  // the two samples; both hidden tests fail

const browser = await chromium.launch();
const errors = [];
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
page.on("pageerror", (e) => errors.push(e.message));
const shot = async (name) => {
  if (!OUT) return;
  await page.waitForTimeout(900);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/sandbox-${SCHEME}-${name}.png` });
};

await page.goto(`${BASE}/#/sandbox`);
await page.waitForSelector("text=Teacher access");
await page.fill("input[type=password]", TOKEN);
await page.click("button[type=submit]");
await page.waitForSelector("text=Sandbox Labs");
await page.goto(`${BASE}/#/sandbox/labs/${lab.id}`);
await page.waitForSelector("text=All tests passed");  // a published lab opens on Submissions
await page.waitForSelector("text=UG24CS010");
assert.ok(await page.locator("text=not submitted").count() >= 3);
await shot("11-submissions");
await page.click("button:has-text('Failing a test')");
await page.waitForTimeout(300);
assert.equal(await page.locator("text=UG24CS001").count(), 0);
await page.click("button:has-text('Everyone')");
await page.locator("tr:has-text('UG24CS003') td button").first().click();
await page.waitForSelector("text=Expected");
await page.waitForSelector("aside >> text=hidden 1");
await shot("12-submission-results");

// after the due time a Submit is refused with a reason; a backup is still kept
await api("PATCH", `/api/sandbox/labs/${lab.id}`, { due_at: Date.now() / 1000 - 3600 });
const late = await submit("UG24CS008", lab.id, a1, ok.sum);
assert.equal(late.status, 409);
assert.match((await late.json()).detail, /can no longer be submitted/);
assert.equal((await submit("UG24CS008", lab.id, a1, ok.sum, "change")).status, 200);

await browser.close();
assert.deepEqual(errors, []);
console.log("sandbox grading e2e: ok");
