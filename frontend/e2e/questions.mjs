// End-to-end check of question sources and optional tests, with screenshots
// for the thesis: a teacher makes a Python lab with a subject, picks a
// question from Exercism (fetched live), links a HackerRank problem, writes one
// question with a hidden test, and opens the lab; a student checks their code
// against the tests (failing, then passing). A second lab in C++ shows the
// language setting reaching the editor and the runner.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/questions.mjs [screenshot-dir] [light|dark]
//
// The server needs STUDENTIDE_ADMIN_TOKEN=$TOKEN and internet access to
// raw.githubusercontent.com (Exercism's public repositories).

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const STUDENT = `Q${Date.now().toString(36).toUpperCase()}`;

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
  await page.screenshot({ path: `${OUT}/questions-${SCHEME}-${name}.png`, fullPage: full });
};
const get = async (path) => {
  const r = await fetch(BASE + path, { headers: { "X-Admin-Token": TOKEN } });
  assert.ok(r.ok, `${path}: ${r.status}`);
  return r.json();
};

// --- teacher: a Python lab ----------------------------------------------------
const t = await open();
await t.goto(`${BASE}/#/teach`);
await t.waitForSelector("text=Teacher access");
await t.fill("input[type=password]", TOKEN);
await t.click("button[type=submit]");
await t.waitForSelector("text=A lab is one sitting");

const newLab = async (title, subject, language) => {
  await t.goto(`${BASE}/#/teach`);
  await t.click("button:has-text('New lab')");
  await t.fill("input[placeholder^='Lab 5']", title);
  await t.fill("input[placeholder='Data Structures']", subject);
  await t.selectOption("select[aria-label='Programming language']", language);
  return t;
};
await newLab("Lab 8: Strings (e2e)", "Programming in Python", "python");
await shot(t, "01-new-lab");
await t.click("button:has-text('Create and add questions')");
await t.waitForSelector("text=Add the first question");
const labId = (await t.evaluate(() => location.hash)).split("/").at(-1);

// from a platform: Exercism, fetched live
await t.click("button:has-text('From a platform') >> nth=0");
await t.click("button[role=tab]:has-text('Exercism')");
await t.waitForSelector("button[aria-pressed=true]:has-text('Easy')");
await t.waitForSelector("ul[aria-label=Questions] button");
await shot(t, "02-picker");
await t.fill("input[aria-label='Search questions']", "isogram");
await t.click("ul[aria-label=Questions] button:has-text('Isogram')");
await t.waitForSelector("button:has-text('Add to lab')");
await shot(t, "03-preview");
await t.click("button:has-text('Add to lab')");
await t.waitForSelector("strong:text-is('Isogram')");

// HackerRank is link-only
await t.click("button:has-text('From a platform') >> nth=0");
await t.click("button[role=tab]:has-text('HackerRank')");
await t.waitForSelector("text=HackerRank can't be fetched automatically");
await t.fill("input[placeholder^='https://hackerrank.com']", "https://www.hackerrank.com/challenges/anagram/problem");
await t.fill("input[placeholder='Two sum']", "Valid anagram");
await shot(t, "04-link-only");
await t.click("button:has-text('Add linked question')");
await t.waitForSelector("text=Edit question"); // opens straight into writing the prompt
await t.fill("textarea[placeholder^='Read two words']", "Read two words, one per line. Print YES if they are anagrams, otherwise NO.");
await t.click("form button[type=submit]:has-text('Save')");
await t.waitForSelector("text=HackerRank link");

// a teacher-written question with one visible and one hidden test
await t.click("button:has-text('Add question') >> nth=0");
await t.fill("input[placeholder='Anagram check']", "Sum of two");
await t.fill("textarea[placeholder^='Read two words']", "Read two integers on one line and print their sum.");
await t.fill("textarea[placeholder^='listen']", "2 3");
await t.click("button:has-text('Test cases')");
await t.click("button:has-text('Add test')");
await t.fill("input[aria-label='Test 1 name']", "sample");
await t.fill("textarea[aria-label='Test 1 input']", "2 3");
await t.fill("textarea[aria-label='Test 1 expected output']", "5");
await t.click("button:has-text('Add test')");
await t.fill("textarea[aria-label='Test 2 input']", "-7 10");
await t.fill("textarea[aria-label='Test 2 expected output']", "3");
await t.check("label:has(+ button[aria-label='Remove test 2']) input[type=checkbox]");
await shot(t, "05-tests-editor");
await t.click("form button[type=submit]:has-text('Add question')");
await t.waitForSelector("strong:text-is('Sum of two')");

await t.click("label:has-text('Everyone who signs in') input[type=checkbox]");
await t.click("button[role=radio]:has-text('Open')");
await t.waitForSelector("button[role=radio][aria-checked=true]:has-text('Open')");
await shot(t, "06-lab", true);

const lab = await get(`/api/teach/labs/${labId}`);
assert.equal(lab.language, "python");
assert.equal(lab.subject, "Programming in Python");
const iso = lab.questions.find((q) => q.title === "Isogram");
assert.equal(iso.source.provider, "exercism");
assert.ok(iso.tests.length >= 10 && iso.harness.includes("is_isogram("), "Exercism tests imported");
assert.ok(lab.questions.find((q) => q.title === "Valid anagram").source.linked_only);
assert.deepEqual(lab.questions.find((q) => q.title === "Sum of two").tests.map((x) => x.hidden), [false, true]);

// --- student -------------------------------------------------------------------
const s = await open();
await s.goto(BASE);
await s.fill("input", STUDENT);
await s.click("button[type=submit]");
await s.waitForSelector("text=Before you start");
await s.check("input[type=checkbox]");
await s.click("button:text-is(\"Start\")");
await s.waitForSelector("text=Lab 8: Strings (e2e)");
await s.click("button:has-text('Isogram')");
await s.waitForSelector(".cm-content");
await s.click("button:has-text('Check')");
await s.waitForSelector("text=/0 of \\d+ passed/");
await s.click(".cm-content");
await s.keyboard.press("Control+a");
await s.keyboard.type("def is_isogram(p): s = [c.lower() for c in p if c.isalpha()]; return len(s) == len(set(s))", { delay: 12 });
await s.click("button:has-text('Check')");
await s.waitForSelector(`text=${iso.tests.length} of ${iso.tests.length} passed`);
await shot(s, "07-student-check");
const sessionId = await s.evaluate(() => window.__studentide.sessionId);
await s.click("button:text-is(\"Finish\")");
await s.click("[role=dialog] button:text-is(\"Finish session\")");
await s.waitForSelector("text=Session saved");

const checks = await get(`/api/sessions/${sessionId}/checks`);
assert.deepEqual(checks.map((c) => c.passed === c.total), [false, true]);

// --- a C++ lab: the language reaches the editor and the runner -----------------
await newLab("Lab 9: Loops in C++ (e2e)", "Problem Solving", "cpp");
await t.click("button:has-text('Create and add questions')");
await t.waitForSelector("text=Add the first question");
const cppLab = (await t.evaluate(() => location.hash)).split("/").at(-1);
await t.click("button:has-text('Add question') >> nth=0");
await t.fill("input[placeholder='Anagram check']", "Sum of two");
await t.fill("textarea[placeholder^='a = input()']", "#include <iostream>\nusing namespace std;\n\nint main() {\n    int a, b;\n    cin >> a >> b;\n    \n}\n");
await t.fill("textarea[placeholder^='listen']", "20 22");
await t.click("form button[type=submit]:has-text('Add question')");
await t.waitForSelector("strong:text-is('Sum of two')");
await t.click("label:has-text('Everyone who signs in') input[type=checkbox]");
await t.click("button[role=radio]:has-text('Open')");
await t.waitForSelector("button[role=radio][aria-checked=true]:has-text('Open')");

await s.close();
const s2 = await open();
await s2.goto(BASE);
await s2.fill("input", STUDENT);
await s2.click("button[type=submit]");
await s2.waitForSelector("text=Lab 9: Loops in C++ (e2e)");
await s2.click("button:has-text('Sum of two') >> nth=0"); // newest lab is listed first
await s2.waitForSelector("text=main.cpp");
await s2.click(".cm-line:has-text('cin')");
await s2.keyboard.press("End");
await s2.keyboard.press("Enter");
await s2.keyboard.type("cout << a + b << endl;", { delay: 12 });
await s2.keyboard.press("Control+Enter");
await s2.waitForFunction(() => document.querySelector(".output")?.textContent?.trim() === "42", null, { timeout: 30_000 });
await shot(s2, "08-student-cpp");

await browser.close();
assert.deepEqual(errors, [], `page errors: ${errors.join("; ")}`);
console.log(JSON.stringify({ lab: labId, cppLab, session: sessionId, checks: checks.length }));
console.log("questions e2e OK");
