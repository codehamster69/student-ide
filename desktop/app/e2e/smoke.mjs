// Drives the built desktop app with Playwright against real servers.
//
//   BASE=http://127.0.0.1:8000 TOKEN=change-me [GBASE=http://127.0.0.1:8001] [SHOTS=dir] node e2e/smoke.mjs
//
// BASE: a dev-mode server (STUDENTIDE_ADMIN_TOKEN=$TOKEN) with the built frontend.
// GBASE: optional, e2e/fake_google_server.py, to check the browser sign-in handoff.
// On Linux without a display run it under xvfb-run.

import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { _electron: electron, chromium } = require("playwright");
const APP = join(dirname(fileURLToPath(import.meta.url)), "..");
const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "change-me";
const GBASE = process.env.GBASE;
const SHOTS = process.env.SHOTS;

const executablePath = createRequire(join(APP, "package.json"))("electron"); // the app's own Electron
const launch = (server) => electron.launch({
  executablePath,
  args: [...(process.getuid?.() === 0 ? ["--no-sandbox"] : []), APP, `--server=${server}`, `--user-data=${mkdtempSync(join(tmpdir(), "sid-desktop-"))}`],
  env: { ...process.env, ELECTRON_ENABLE_LOGGING: "0" },
});
const shot = async (page, name) => SHOTS && (await page.waitForTimeout(700), page.screenshot({ path: `${SHOTS}/${name}.png` }));

// -- 1. dev mode: the web app works in the window, the bridge is there, the window is locked down
{
  const app = await launch(BASE);
  const page = await app.firstWindow();
  await page.waitForSelector("input");
  assert.equal(new URL(page.url()).origin, new URL(BASE).origin);

  const bridge = await page.evaluate(() => ({
    contract: window.studentDesktop?.contract,
    namespaces: Object.keys(window.studentDesktop ?? {}).filter((k) => typeof window.studentDesktop[k] === "object").sort(),
  }));
  assert.equal(bridge.contract, 2);
  assert.deepEqual(bridge.namespaces, ["app", "auth", "engine", "sandbox", "terminal"]);

  const info = await page.evaluate(() => window.studentDesktop.app.info());
  assert.equal(info.server, new URL(BASE).origin);
  assert.match(info.deviceId, /^[0-9a-f]{32}$/);
  assert.ok(info.chrome);
  assert.deepEqual(await page.evaluate(() => window.studentDesktop.engine.status()), { state: "missing", engine: null });
  const err = await page.evaluate(() => window.studentDesktop.sandbox.openLab("x").then(() => null, (e) => e));
  assert.equal(err.code, "no_engine");
  assert.ok(err.title && err.message);

  // no camera, microphone or screen
  const media = await page.evaluate(() => navigator.mediaDevices.getUserMedia({ video: true }).then(() => "granted", (e) => e.name));
  assert.notEqual(media, "granted");
  // navigation off the server is refused (it would open in the system browser)
  await app.evaluate(({ shell }) => { globalThis.__opened = []; shell.openExternal = async (u) => { globalThis.__opened.push(u); }; });
  await page.evaluate(() => { location.href = "https://example.com/"; });
  await page.waitForTimeout(800);
  assert.equal(new URL(page.url()).origin, new URL(BASE).origin);
  assert.deepEqual(await app.evaluate(() => globalThis.__opened), ["https://example.com/"]);
  await page.goto(BASE); // Playwright still waits on the refused navigation; start clean
  await page.waitForSelector("input");

  // a student session recorded in the app, marked as desktop, with keys timed as on the web
  await shot(page, "desktop-01-login");
  const student = `desk-${Date.now().toString(36)}`;
  await page.fill("input", student);
  await page.click("button[type=submit]");
  await page.waitForSelector("text=Before you start");
  await page.check("input[type=checkbox]");
  await page.click('button:text-is("Start")');
  await page.waitForSelector("text=Choose a task");
  await page.click("text=Warm-up: FizzBuzz");
  await page.waitForSelector(".cm-content");
  await page.click(".cm-content");
  await page.keyboard.press("Control+End");
  await page.keyboard.type("for i in range(n):\n", { delay: 40 });
  await shot(page, "desktop-02-editor");
  const sessionId = await page.evaluate(async () => { await window.__studentide.rec.flush?.(); return window.__studentide.sessionId; });
  await page.waitForTimeout(2500);
  const h = { "X-Admin-Token": TOKEN };
  const sessions = await (await fetch(`${BASE}/api/sessions?student_id=${student}`, { headers: h })).json();
  const s = sessions.find((x) => x.id === sessionId) ?? sessions[0];
  assert.equal(s.client_meta.client.kind, "desktop");
  assert.equal(s.client_meta.client.device, info.deviceId);
  assert.match(s.client_meta.user_agent, /StudentIDE-Desktop\//);
  const events = await (await fetch(`${BASE}/api/sessions/${s.id}/events`, { headers: h })).json();
  const keys = (events.events ?? events).filter((e) => e.type === "key");
  assert.ok(keys.length >= 10, `expected key events, got ${keys.length}`);
  await app.close();
  console.log(`dev mode ok: bridge, lock-down, ${keys.length} key events in a desktop session`);
}

// -- 2. Google mode: sign in through the "system browser" (a separate Chromium) and land signed in
if (GBASE) {
  const app = await launch(GBASE);
  const page = await app.firstWindow();
  await app.evaluate(({ shell }) => { globalThis.__opened = []; shell.openExternal = async (u) => { globalThis.__opened.push(u); }; });
  await page.waitForSelector("text=Sign in with your browser");
  await shot(page, "desktop-03-browser-signin");
  await page.click("text=Sign in with your browser");
  let url;
  for (let i = 0; i < 50 && !url; i++) { url = (await app.evaluate(() => globalThis.__opened))[0]; if (!url) await page.waitForTimeout(100); }
  assert.match(url, /#\/desktop\/signin\?challenge=/);

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 760 } });
  const tab = await ctx.newPage();
  const r = await tab.request.post(`${GBASE}/api/auth/google`, { data: { credential: "pg25cs07@iiitsurat.ac.in" } });
  assert.equal(r.status(), 200);
  await tab.goto(url);
  await tab.waitForSelector("text=Continue to the app");
  await shot(tab, "desktop-04-browser-confirm");
  await tab.click("text=Continue to the app");
  await tab.waitForSelector("text=You're signed in");
  await browser.close();

  await page.waitForSelector("text=Before you start", { timeout: 10_000 });
  const me = await page.evaluate(() => fetch("/api/me").then((x) => x.json()));
  assert.equal(me.student_id, "PG25CS07");
  await shot(page, "desktop-05-signed-in");
  await app.close();
  console.log("google mode ok: browser sign-in handoff");
}
console.log("desktop smoke passed");
