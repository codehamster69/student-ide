// End-to-end check of Sandbox Labs (teacher side), with thesis screenshots:
// a teacher creates a subject with a C environment, adds a lab with one
// assignment (starter, tests, reference solution), checks it in a cloud
// preview, tries it as a student (editor, terminal, Check), publishes it and
// shares it to the library.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/sandbox.mjs [screenshot-dir] [light|dark]
//
// The server needs STUDENTIDE_ADMIN_TOKEN=$TOKEN and previews on this machine:
// STUDENTIDE_PREVIEW_DOCKER=1 STUDENTIDE_PREVIEW_BUILD_LOCAL=1 (Docker running).

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
const shot = async (name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(900);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/sandbox-${SCHEME}-${name}.png`, fullPage: full });
};

await page.goto(`${BASE}/#/sandbox`);
await page.waitForSelector("text=Teacher access");
await page.fill("input[type=password]", TOKEN);
await page.click("button[type=submit]");
await page.waitForSelector("text=Sandbox Labs");
await shot("01-home");

// subject with an environment from the builder
await page.click("button:has-text('New subject')");
await page.fill("input[placeholder='Data Structures']", "Data Structures (e2e)");
await page.fill("input[placeholder='CS201']", "CS201");
await page.click("button:has-text('C and C++')");
await page.locator("label:has-text('Valgrind') input").check();
await shot("02-new-subject", true);
await page.click("button:has-text('Create subject')");
await page.waitForSelector("text=Copy for next semester");
const subjectId = (await page.evaluate(() => location.hash)).split("/").at(-1);
await page.fill("textarea[placeholder^='UG24CS001']", "A: UG24CS001 to UG24CS030\nB: UG24CS031 to UG24CS060");
await page.click("button:has-text('Save roster')");
await page.waitForSelector("text=Students (60)");

// lab + assignment through the API (the wizard's forms are exercised below)
await page.fill("input[placeholder^='New lab']", "Lab 3: Reverse a line");
await page.click("button:has-text('Add')");
await page.waitForSelector("text=Basics");
const labId = (await page.evaluate(() => location.hash)).split("/").at(-1);
await api("POST", `/api/sandbox/labs/${labId}/assignments`, {
  title: "Reverse it", run: "make -s && ./main",
  statement: "Read one line and print it **backwards**.\n\n- Use `fgets`\n- Check with `valgrind ./main`",
  files: [{ path: "main.c", content: "#include <stdio.h>\n\nint main(void) {\n    char s[256];\n    /* your code */\n    return 0;\n}\n" },
          { path: "Makefile", content: "main: main.c\n\tcc -Wall -g -o main main.c\n" }],
  open: ["main.c"],
  tests: { kind: "io", timeout_s: 5, cases: [
    { name: "word", stdin: "abc\n", expected: "cba", hidden: false, compare: "text" },
    { name: "spaces", stdin: "a b\n", expected: "b a", hidden: false, compare: "text" },
    { name: "empty", stdin: "\n", expected: "", hidden: true, compare: "text" }] },
  solution_files: [{ path: "main.c", content: "#include <stdio.h>\n#include <string.h>\nint main(void){char s[256];if(!fgets(s,sizeof s,stdin))return 0;size_t n=strcspn(s,\"\\n\");while(n--)putchar(s[n]);putchar('\\n');}\n" }],
});
await page.reload();
await page.waitForSelector("text=Basics");
await page.click("nav button:has-text('Assignments')");
await page.click("text=Reverse it");
await page.waitForSelector("text=Run command");
await shot("03-assignment");
await page.click("button:has-text('Tests')");
await shot("04-tests");

// Check: reference solution passes, starter fails, in the real environment
await page.click("nav button:has-text('Check')");
await page.click("button:has-text('Check lab')");
await page.waitForSelector("text=solution 3/3", { timeout: 900_000 });
await shot("05-check");

// Try as a student
await page.click("button:has-text('Try as a student')");
await page.waitForSelector(".xterm", { timeout: 600_000 });
await page.waitForSelector("text=main.c");
await page.click(".xterm");
await page.keyboard.type("ls && gcc --version | head -1\n", { delay: 20 });
await page.waitForTimeout(1500);
await page.click("button:has-text('Check')");
await page.waitForSelector("text=1 of 3 tests pass");
await shot("06-try-as-student");
const previewId = (await page.evaluate(() => location.hash)).split("/").at(-1);
const files = await api("GET", `/api/sandbox/previews/${previewId}/files?assignment_id=${(await api("GET", `/api/sandbox/labs/${labId}`)).definition.assignments[0].id}`);
assert.deepEqual(files.files.map((f) => f.path).filter((p) => !p.startsWith("main")), ["Makefile"]);
await page.click("button:has-text('Stop')");
await page.waitForSelector("text=This preview stopped");

// Publish and share
await page.goto(`${BASE}/#/sandbox/labs/${labId}`);
await page.click("nav button:has-text('Publish')");
await page.click("button:has-text('Publish to students')");
await page.waitForSelector("text=published");
await page.fill("input[placeholder^='Pointers and malloc']", "Strings in C, one part, with hidden tests");
await page.fill("input[placeholder^='pointers,']", "strings, fgets");
await page.click("button:has-text('Share')");
await page.waitForSelector("text=Shared (library version 1)");
await shot("07-publish", true);

await page.goto(`${BASE}/#/sandbox/library`);
await page.waitForSelector("text=Lab 3: Reverse a line");
await page.click("text=Lab 3: Reverse a line");
await page.waitForSelector("text=Use this lab");
await shot("08-library");
await page.goto(`${BASE}/#/sandbox/subjects/${subjectId}`);
await page.waitForSelector("text=in library");
await shot("09-subject");
await page.goto(`${BASE}/#/sandbox`);
await page.waitForSelector("text=Data Structures (e2e)");
await shot("10-subjects");

const def = await api("GET", `/api/sandbox/labs/${labId}/definition`);
assert.equal(def.format, "studentide.sandbox-lab/1");
assert.equal(def.assignments[0].tests.n_hidden, 1);
assert.deepEqual(errors, []);
await browser.close();
console.log("sandbox e2e ok", labId);
