// End-to-end check of the lab wizard extras, with thesis screenshots: import a
// question, grading mode + late policy with the "What students will see" card,
// the History step after a mid-lab test fix (with Undo), and "Set up by hand".
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/sandbox-wizard.mjs [screenshot-dir] [light|dark]
//
// The server needs STUDENTIDE_ADMIN_TOKEN=$TOKEN and previews (a real driver, or
// a dev server with previews.FakeDriver; with FakeDriver the terminal stays empty
// and the script fills the shell history through FAKE_HISTORY=1 + /__fake/history).

import { createRequire } from "node:module";
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

const browser = await chromium.launch();
const errors = [];
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
page.on("pageerror", (e) => errors.push(e.message));
page.on("dialog", (d) => d.accept());
if (process.env.DEBUG) page.on("request", (r) => r.url().includes("/api/sandbox/labs") && r.method() !== "GET" && console.log(r.method(), r.url(), r.postData()));
page.on("response", async (r) => { if (r.status() >= 400 && r.url().includes("/api/")) errors.push(`${r.status()} ${r.url()} ${await r.text().catch(() => "")}`); });
const shot = async (name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(900);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/sandbox-${SCHEME}-${name}.png`, fullPage: full });
};

// a subject and a lab with one written assignment, through the API
const subject = await api("POST", "/api/sandbox/subjects", { title: "Programming in C", code: "CS101", semester: "Autumn 2026",
  recipe: { base: "c-cpp", tools: ["valgrind"] } });
await api("PUT", `/api/sandbox/subjects/${subject.id}/roster`, { text: "A: UG24CS001 to UG24CS030" });
let lab = await api("POST", `/api/sandbox/subjects/${subject.id}/labs`, { title: "Lab 2: Conditions" });
lab = await api("POST", `/api/sandbox/labs/${lab.id}/assignments`, {
  title: "Sign of a number", run: "gcc -o main main.c && ./main", files: [{ path: "main.c", content: "int main(void) { return 0; }\n" }],
  open: ["main.c"], tests: { kind: "io", cases: [{ name: "positive", stdin: "5\n", expected: "positive" }, { name: "zero", stdin: "0\n", expected: "zero", hidden: true }] },
  solution_files: [{ path: "main.c", content: "/* answer */" }] });

await page.goto(`${BASE}/#/sandbox`);
await page.waitForSelector("text=Teacher access");
await page.fill("input[type=password]", TOKEN);
await page.click("button[type=submit]");
await page.waitForSelector("text=Sandbox Labs");
await page.goto(`${BASE}/#/sandbox/labs/${lab.id}`);
await page.waitForSelector("text=Basics");

// 1. import a question from the bundled Student IDE sets
await page.click("nav button:has-text('Assignments')");
await page.click("button:has-text('Import a question')");
await page.waitForSelector("text=Add a question from a platform");
await page.click("[role=tab]:has-text('Student IDE sets')");
await page.fill("input[placeholder^='Search']", "leap");
await page.click("text=Leap Year Detective");
await page.waitForSelector("button:has-text('Add to lab')");
await shot("13-import");
await page.click("button:has-text('Add to lab')");
await page.waitForSelector("text=Add a question from a platform", { state: "detached" });
let d = await api("GET", `/api/sandbox/labs/${lab.id}`);
assert.deepEqual(d.definition.assignments.map((a) => a.title), ["Sign of a number", "Leap Year Detective"]);
assert.ok(d.definition.assignments[1].tests.cases.length >= 3 && d.definition.assignments[1].run.startsWith("gcc"));

// 2. Publish: grading mode, late policy, summary card
await page.click("nav button:has-text('Publish')");
await page.fill("input[type=datetime-local] >> nth=1", "2026-11-20T17:00");
await page.click("label:has-text('Tests, then your review')");
await page.click("label:has-text('Accepted with a penalty')");
await page.locator("input[type=number]").nth(0).fill("20");
await page.waitForSelector("text=Late work loses 20% per day, not accepted after 3 days.");
await page.waitForSelector("text=What students will see");
await page.locator("text=Grading").first().scrollIntoViewIfNeeded();
await page.mouse.wheel(0, 250);
await shot("11-publish-grading");
if (process.env.DEBUG) console.log(await page.locator("button:has-text('Publish to students')").evaluateAll((bs) => bs.map((b) => [b.disabled, b.outerHTML.slice(0, 80)])));
await page.getByRole("button", { name: "Publish to students" }).click();
await page.waitForTimeout(500);
await page.waitForSelector("text=Close lab").catch(async (e) => { await page.screenshot({ path: "/tmp/claude-0/wiz/fail.png" }); console.log(errors); throw e; });
d = await api("GET", `/api/sandbox/labs/${lab.id}`);
assert.equal(d.status, "published");
assert.equal(d.grading_mode, "tests_manual");
assert.deepEqual(d.late, { mode: "penalty", per_day_pct: 20, max_days: 3 });

// 3. a mid-lab fix to the tests, through the wizard: the note says what students notice, History lists it
await page.click("nav button:has-text('Assignments')");
// the first assignment is open by default
await page.getByRole("button", { name: "tests", exact: true }).click();
await page.locator("tbody tr").first().locator("textarea").nth(1).fill("positive\n");
await page.click("button:has-text('Save assignment')");
await page.waitForSelector("text=Students get a quiet note about the change.");
await page.click("nav button:has-text('History')");
await page.waitForSelector("text=Changed the tests of");
await page.waitForSelector("text=Published to students.");
await shot("12-history");
await page.click("button:has-text('Undo') >> nth=0");
await page.waitForSelector("text=Undid: Changed the tests of");

// 4. set up by hand on the subject's environment
await page.goto(`${BASE}/#/sandbox/subjects/${subject.id}`);
await page.click("button:has-text('Set up by hand')");
await page.waitForSelector("text=Your recipe");
const pid = (await page.evaluate(() => location.hash)).split("/").at(-1);
if (process.env.FAKE_HISTORY === "1") {
  const hist = ["ls", "sudo apt update", "sudo apt install postgresql-client", "psql --version", "pip install --break-system-packages cs50", "clear"].join("\n");
  await fetch(`${BASE}/__fake/history/${pid}?text=${encodeURIComponent(hist)}`);
}
await page.waitForFunction(() => document.querySelector("textarea[placeholder^='Nothing yet']")?.value.includes("apt install -y"), null, { timeout: 15000 });
await shot("14-setup-by-hand");
await page.click("button:has-text('Save as environment')");
await page.waitForSelector("text=It is being built now.");
const env = await api("GET", `/api/sandbox/environments/${subject.environment.id}`);
assert.match(env.versions.at(-1).recipe.setup, /apt install -y postgresql-client/);

// 5. Vim keys in a file editor: i, type, Esc, then x deletes the last character
await page.evaluate(() => localStorage.setItem("studentide.vim", "1"));
await page.goto(`${BASE}/#/sandbox/labs/${lab.id}`);
await page.reload();
await page.click("nav button:has-text('Assignments')");
await page.getByRole("button", { name: "Starter files", exact: true }).click();
await page.click(".cm-content");
await page.keyboard.press("i");
await page.keyboard.type(" abc");
await page.keyboard.press("Escape");
await page.keyboard.press("x");
await page.waitForFunction(() => document.querySelector(".cm-content")?.textContent?.endsWith(" ab"));
await page.evaluate(() => localStorage.removeItem("studentide.vim"));

assert.deepEqual(errors, []);
await browser.close();
console.log("sandbox wizard e2e ok");
