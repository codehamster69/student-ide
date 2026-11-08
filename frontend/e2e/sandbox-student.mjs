// End-to-end check of Sandbox Labs (student side), with thesis screenshots:
// a teacher publishes a lab of two assignments to a roster; the student sees it
// on their home grouped by subject. On the website the card says to open it in
// the app; with a stand-in desktop bridge (window.studentDesktop, the same
// contract as desktop/app) the lab opens: files, editor, terminal, Run, Check,
// Submit, and the editor, terminal and runtime events land in one session per
// assignment, linked by one sitting id.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/sandbox-student.mjs [screenshot-dir] [light|dark]
//
// The bridge is a stand-in: the real runtime is tested by desktop/sandbox (npm run test:engine).

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const STUDENT = "UG24CS042";
const H = { "x-admin-token": TOKEN, "content-type": "application/json" };
const api = async (method, path, body) => {
  const r = await fetch(BASE + path, { method, headers: H, body: body && JSON.stringify(body) });
  const text = await r.text();
  assert.ok(r.ok, `${method} ${path}: ${r.status} ${text}`);
  return JSON.parse(text);
};

// --- teacher: subject, roster, a published lab of two assignments (and a second subject)
const subj = await api("POST", "/api/sandbox/subjects", { title: "Data Structures", code: "CS201", semester: "Autumn 2026", color: "teal",
  recipe: { base: "c-cpp", tools: ["valgrind"] } });
await api("PUT", `/api/sandbox/subjects/${subj.id}/roster`, { text: `A: UG24CS001 to UG24CS060` });
let lab = await api("POST", `/api/sandbox/subjects/${subj.id}/labs`, { title: "Lab 3: Strings in C" });
await api("PATCH", `/api/sandbox/labs/${lab.id}`, { description: "Reverse a line, then count words. Use the terminal for valgrind." });
const MAIN = "#include <stdio.h>\n\nint main(void) {\n    char s[256];\n    /* your code */\n    return 0;\n}\n";
for (const [title, statement] of [["Reverse a line", "Read one line and print it **backwards**.\n\n- Use `fgets`\n- Check with `valgrind ./main`"],
                                  ["Count the words", "Print how many words the line has."]]) {
  await api("POST", `/api/sandbox/labs/${lab.id}/assignments`, {
    title, statement, run: "make -s && ./main",
    files: [{ path: "main.c", content: MAIN }, { path: "Makefile", content: "main: main.c\n\tcc -Wall -g -o main main.c\n" }],
    open: ["main.c"],
    tests: { kind: "io", timeout_s: 5, cases: [
      { name: "word", stdin: "abc\n", expected: "cba", hidden: false, compare: "text" },
      { name: "spaces", stdin: "a b\n", expected: "b a", hidden: false, compare: "text" },
      { name: "empty", stdin: "\n", expected: "", hidden: true, compare: "text" }] },
    solution_files: [{ path: "main.c", content: "/* answer */" }],
  });
}
await api("PATCH", `/api/sandbox/labs/${lab.id}`, { status: "published", due_at: Math.floor(Date.now() / 1000) + 3 * 86400 });
const os = await api("POST", "/api/sandbox/subjects", { title: "Operating Systems", code: "CS301", semester: "Autumn 2026", color: "violet", recipe: { base: "linux" } });
await api("PUT", `/api/sandbox/subjects/${os.id}/roster`, { students: [{ id: STUDENT }] });
const shell = await api("POST", `/api/sandbox/subjects/${os.id}/labs`, { title: "Lab 1: Processes and signals" });
await api("POST", `/api/sandbox/labs/${shell.id}/assignments`, { title: "fork and wait", statement: "Write `forks.c`.", run: "make -s && ./forks",
  files: [{ path: "forks.c", content: "int main(void){return 0;}\n" }], open: ["forks.c"], tests: { kind: "io", cases: [] } });
await api("PATCH", `/api/sandbox/labs/${shell.id}`, { status: "published", network: "off" });
await fetch(`${BASE}/api/consent`, { method: "POST", headers: H, body: JSON.stringify({ student_id: STUDENT }) });

const browser = await chromium.launch();
const errors = [];
const open = async (bridge) => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 2 });
  if (bridge) await ctx.addInitScript(fakeDesktop);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(BASE + "/");
  await page.fill("input[placeholder^='e.g.']", STUDENT);
  await page.keyboard.press("Enter");
  await page.waitForSelector("[data-testid=sandbox-labs]");
  return page;
};
const shot = async (page, name) => {
  if (!OUT) return;
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/sandbox-student-${SCHEME}-${name}.png` });
};

// --- website: listed, with the note to open them in the app
let page = await open(false);
await page.waitForSelector("text=Open these in the Student IDE app.");
assert.ok(await page.locator("button:has-text('Lab 3: Strings in C')").isDisabled());
await page.locator("[data-testid=sandbox-labs]").scrollIntoViewIfNeeded();
await shot(page, "01-website");
await page.context().close();

// --- desktop app (stand-in bridge)
page = await open(true);
assert.equal(await page.locator("text=Open these in the Student IDE app.").count(), 0);
await page.locator("[data-testid=sandbox-labs]").scrollIntoViewIfNeeded();
await shot(page, "02-home");
await page.click("button:has-text('Lab 3: Strings in C')");
await page.waitForSelector(".xterm", { timeout: 20_000 });
await page.waitForSelector(".cm-content");
await shot(page, "03-workspace");

// editor: type into main.c; terminal: a command
await page.click(".cm-content");
await page.keyboard.press("Control+End");
await page.keyboard.type("\n// reversed with a loop\n", { delay: 25 });
await page.click(".xterm");
await page.keyboard.type("make && ./main\r", { delay: 30 });
await page.waitForSelector("text=fake shell ran: make && ./main");
await page.click("button:has-text('Run')");
await page.waitForSelector("text=exit 0");
await shot(page, "04-run");
await page.click("button:has-text('Check')");
await page.waitForSelector("text=1 of 2 tests pass");
await shot(page, "05-check");
await page.click("button:has-text('Submit')");
await page.click("[role=dialog] button:has-text('Submit')");
await page.waitForSelector("text=Submitted. This copy");
await shot(page, "06-submitted");
// second assignment: its own session, Ctrl+2
await page.keyboard.press("Control+2");
await page.waitForSelector("text=Print how many words");
await page.waitForTimeout(2500);  // a recorder flush
const writes = await page.evaluate(() => window.__fakeDesktop.writes);
assert.ok(writes.some((w) => w.path.endsWith("/main.c") && w.content.includes("reversed with a loop")), "editor saved into the instance");
await page.click("button:has-text('Labs')");
await page.waitForSelector("[data-testid=sandbox-labs]");

// --- the server got one session per assignment, one sitting, with editor, terminal and runtime events
const sessions = (await api("GET", `/api/sessions?student_id=${STUDENT}`)).filter((s) => s.lab_id === lab.id);
assert.equal(sessions.length, 2, JSON.stringify(sessions));
assert.equal(new Set(sessions.map((s) => s.sitting_id)).size, 1);
const first = sessions.sort((a, b) => a.started_at - b.started_at)[0];
const events = await api("GET", `/api/sessions/${first.id}/events`);
const types = new Set(events.map((e) => e.type));
for (const t of ["session_start", "snapshot", "key", "edit", "term_cmd", "run", "session_end"]) assert.ok(types.has(t), `missing ${t}: ${[...types]}`);
assert.ok(events.some((e) => e.type === "edit" && e.data.path === "main.c"), "edit carries its path");
assert.ok(events.some((e) => e.type === "key" && e.data.surface === "terminal"), "terminal keys tagged");
assert.deepEqual(errors, []);
await browser.close();
console.log("sandbox student e2e ok", lab.id, first.id);

// A stand-in for window.studentDesktop (desktop/app/src/shared/contract.ts), run in the page before the app.
function fakeDesktop() {
  const listeners = new Map();
  const emit = (name, data) => setTimeout(() => (listeners.get(name) ?? []).forEach((cb) => cb(data)), 0);
  const files = new Map();
  const writes = [];
  let def = null;
  const key = (a) => `${def.id}/${a}`;
  const asgOf = (p) => def.assignments.find((a) => p.startsWith(a.workdir + "/"));
  const ev = (asg, type, data) => emit("sandbox.event", { sessionKey: key(asg), type, data });
  const term = new Map();
  window.__fakeDesktop = { writes };
  window.studentDesktop = {
    contract: 2,
    on(name, cb) { listeners.set(name, [...(listeners.get(name) ?? []), cb]); return () => listeners.set(name, listeners.get(name).filter((x) => x !== cb)); },
    app: { info: async () => ({ version: "0.3.0", contract: 2, platform: "darwin", arch: "arm64", electron: "33", chrome: "130", deviceId: "dev", portable: false, server: location.origin }),
           openExternal: async () => {}, setServer: async () => {} },
    auth: {}, engine: {},
    sandbox: {
      async setupCheck() { return { ok: true, checks: [] }; },
      async openLab(labId) {
        def = await (await fetch(`/api/sandbox/my/labs/${labId}?student_id=UG24CS042`)).json();
        for (const [i, m] of ["Getting the lab environment ready…", "Starting your Linux instance…", "Bringing back your files…"].entries()) {
          emit("sandbox.progress", { message: m, percent: 20 + i * 30 });
          await new Promise((r) => setTimeout(r, 250));
        }
        for (const a of def.assignments) for (const f of a.files) files.set(`${a.workdir}/${f.path}`, f.content);
        return { instanceId: "sid-ug24cs042-" + def.subject.id, labId, subjectId: def.subject.id, limitsEnforced: true, network: def.network, setup: null,
          assignments: def.assignments.map((a) => ({ id: a.id, title: a.title, workdir: a.workdir, sessionKey: key(a.id), files: "new", open: a.open })) };
      },
      async stop() {}, async reset() { return null; },
      async stats() { return { state: "running", cpuPercent: 3.2, memoryBytes: 412 * 2 ** 20, memoryLimitBytes: 2 * 2 ** 30, diskUsedBytes: 0, diskLimitBytes: 0 }; },
      async listFiles(_i, dir) { return [...files.keys()].filter((p) => p.startsWith(dir + "/")).map((p) => ({ path: p.slice(dir.length + 1), type: "file", size: files.get(p).length, mtimeMs: 0 })); },
      async readFile(_i, p) { if (!files.has(p)) throw { code: "missing", title: "No such file." }; return files.get(p); },
      async writeFile(_i, p, content) { files.set(p, content); writes.push({ path: p, content }); },
      async run(_i, asg, o = {}) {
        ev(asg, "run", { run_id: "r1", source: "button", command: "make -s && ./main", exit_code: 0, duration_ms: 412, code_sha256: "0".repeat(64) });
        return { run_id: "r1", stdout: (o.stdin || "hello").trim().split("").reverse().join("") || "olleh", stderr: "", exit_code: 0, duration_ms: 412, error_type: null, code_sha256: "0".repeat(64) };
      },
      async test(_i, asg) {
        ev(asg, "run", { run_id: "r2", source: "test", command: "make -s && ./main", exit_code: 0, duration_ms: 800, code_sha256: "0".repeat(64) });
        return [{ name: "word", passed: true, stdout: "cba", stderr: "", expected: "cba", error_type: null, duration_ms: 9 },
                { name: "spaces", passed: false, stdout: "a b", stderr: "", expected: "b a", error_type: null, duration_ms: 8 }];
      },
      async submit() { return { sha256: "f".repeat(64) }; },
      async recipe() { return { steps: [] }; },
    },
    terminal: {
      async open(_i, o) {
        const id = "t" + (term.size + 1);
        term.set(id, { asg: o.assignmentId, line: "" });
        emit("terminal.data", { id, data: `\x1b[32mstudent@cs201\x1b[0m:\x1b[34m~/labs/…\x1b[0m$ ` });
        return { id };
      },
      async write(id, data) {
        const t = term.get(id);
        for (const ch of data) {
          if (ch === "\r") {
            const cmd = t.line; t.line = "";
            ev(t.asg, "term_cmd", { term_id: id, phase: "start", command: cmd, cwd: "~" });
            emit("terminal.data", { id, data: `\r\nfake shell ran: ${cmd}\r\n\x1b[32mstudent@cs201\x1b[0m$ ` });
            ev(t.asg, "term_cmd", { term_id: id, phase: "end", command: cmd, cwd: "~", exit_code: 0, duration_ms: 120 });
          } else { t.line += ch; emit("terminal.data", { id, data: ch }); }
        }
      },
      async paste(id, text) { await this.write(id, text); },
      async resize() {}, async close() {},
    },
  };
}
