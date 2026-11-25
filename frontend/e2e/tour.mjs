// Screenshot tour of every main screen (student + teacher), for before/after comparison
// of a UI redesign. Runs against a server seeded by teach/live/compete/learn.mjs.
// Unreachable screens are skipped with a warning; the run never aborts.
//
//   BASE=http://127.0.0.1:8000 TOKEN=demo node frontend/e2e/tour.mjs <out-dir> [light|dark]
// Files: <out-dir>/tour-<scheme>-NN-<name>.png (1440x900, scale 1)

import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const TOKEN = process.env.TOKEN ?? "demo";
const STUDENT = process.env.STUDENT ?? "DEMO02";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
if (!OUT) throw new Error("usage: tour.mjs <out-dir> [light|dark]");
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const ctxOpts = { viewport: { width: 1440, height: 900 }, colorScheme: SCHEME, deviceScaleFactor: 1 };
const T = 15000; // bounded wait per selector
let n = 0;
const captured = [], skipped = [];

/** Run one screen; any failure is a warning, never a crash. */
async function step(page, name, fn, { full = false } = {}) {
  n += 1;
  const label = `${String(n).padStart(2, "0")}-${name}`;
  try {
    await fn();
    await page.waitForTimeout(1200);
    // a sticky header would be painted mid-page in a full-page capture
    if (full) await page.addStyleTag({ content: "header.sticky, .sticky { position: relative !important; }" });
    await page.screenshot({ path: `${OUT}/tour-${SCHEME}-${label}.png`, fullPage: full });
    captured.push(label);
  } catch (e) {
    skipped.push(label);
    console.warn(`skip ${label}: ${String(e.message).split("\n")[0]}`);
  }
}
// alternatives are separated by " | " (so text= selectors can be mixed with CSS)
const wait = (page, sel, timeout = T) => Promise.any(sel.split(" | ").map((x) => page.waitForSelector(x, { timeout })))
  .catch(() => { throw new Error(`timed out waiting for ${sel}`); });
const go = async (page, hash) => { await page.goto(`${BASE}/${hash}`); await page.reload(); };
const adminApi = (page, path) => page.evaluate(async ([p, tok]) => {
  const r = await fetch(p, { headers: { "X-Admin-Token": tok } });
  if (!r.ok) throw new Error(`${p} ${r.status}`);
  return r.json();
}, [path, TOKEN]);

// ---------- student ----------
{
  const ctx = await browser.newContext(ctxOpts);
  const page = await ctx.newPage();
  page.setDefaultTimeout(T);
  const fresh = `TOUR${Date.now().toString(36).toUpperCase()}`;

  await step(page, "student-signin", async () => { await page.goto(BASE); await wait(page, "input"); await page.waitForTimeout(2500); });
  await step(page, "student-consent", async () => {
    await page.fill("input", fresh);
    await page.click("button[type=submit]");
    await wait(page, "text=Before you start");
    await page.check("input[type=checkbox]");
  });
  await ctx.close();

  const c2 = await browser.newContext(ctxOpts);
  const s = await c2.newPage();
  s.setDefaultTimeout(T);
  let signedIn = false;
  try {
    await s.goto(BASE);
    await s.fill("input", STUDENT);
    await s.click("button[type=submit]");
    await wait(s, "text=Before you start | text=Your labs | text=Choose a task");
    if (await s.locator("text=Before you start").count()) {
      await s.check("input[type=checkbox]");
      await s.click('button:text-is("Start")');
    }
    await wait(s, "text=Your labs | text=Choose a task");
    signedIn = true;
  } catch (e) { console.warn(`student sign-in failed: ${e.message.split("\n")[0]}`); }

  // the sign-in is not kept across page loads, so signing in again is how we get back home
  const home = async () => {
    await s.goto(BASE); await s.fill("input", STUDENT); await s.click("button[type=submit]");
    await wait(s, "text=Before you start | text=Your labs | text=Choose a task");
    if (await s.locator("text=Before you start").count()) { await s.check("input[type=checkbox]"); await s.click('button:text-is("Start")'); }
    await wait(s, "text=Your labs | text=Choose a task");
  };
  if (signedIn) {
    await step(s, "student-home", async () => {});
    await step(s, "student-home-full", async () => {}, { full: true });
    await step(s, "student-sandbox-shelf", async () => {
      const el = s.locator("text=Sandbox").first();
      await el.waitFor({ timeout: 3000 });
      await el.scrollIntoViewIfNeeded();
    });
    await step(s, "student-attendance-button", async () => {
      const b = s.locator("button:has-text('My attendance'), button[aria-label*='ttendance']").first();
      await b.waitFor({ timeout: 3000 });
      await b.hover(); // opens external Roll Call, so only the button is shown
    });
    // back to home -> learning lab
    await step(s, "student-learn-home", async () => {
      await home();
      await wait(s, "button:has-text('Learning lab')");
      await s.click("button:has-text('Learning lab')");
      await wait(s, "h2");
    });
    await step(s, "student-learn-lesson", async () => {
      await s.click("button:has-text('Loops'):has-text('for and while')");
      await wait(s, "text=lesson 8 of 16");
    });
    await step(s, "student-arena", async () => {
      await home();
      await s.click("button:has-text('Friday sprint')");
      await wait(s, "text=Join the competition | text=Leaderboard | text=You're in | text=Final standings");
    });
    await step(s, "student-workspace", async () => {
      const q = s.locator("button:has-text('Count vowels'), button:has-text('Top three words'), button:has-text('Warm-up: FizzBuzz')").first();
      await q.click();
      await wait(s, ".cm-content");
      await s.click(".cm-content");
      await s.keyboard.press("Control+End");
      await s.keyboard.type("word = input()\nprint(sum(c in 'aeiou' for c in word))\n", { delay: 5 });
      await s.keyboard.press("Control+Enter");
      await s.waitForFunction(() => { const o = document.querySelector(".output"); return o && !o.textContent.startsWith("Running"); }, null, { timeout: T }).catch(() => {});
    });
    await step(s, "student-saved", async () => {
      await s.click("header button:text-is(\"Finish lab\"), header button:text-is(\"Finish\")");
      await s.click("[role=dialog] button:text-is(\"Finish lab\"), [role=dialog] button:text-is(\"Finish session\")");
      await wait(s, ":text('Lab saved'), :text('Session saved')");
    });
  } else console.warn("student screens after sign-in skipped");
  await c2.close();
}

// ---------- teacher ----------
{
  const ctx = await browser.newContext(ctxOpts);
  const t = await ctx.newPage();
  t.setDefaultTimeout(T);
  let unlocked = false;
  await step(t, "teacher-gate", async () => { await t.goto(`${BASE}/#/teach`); await wait(t, "text=Teacher access"); });
  try {
    await t.fill("input[type=password]", TOKEN);
    await t.click("button[type=submit]");
    await wait(t, "text=A lab is one sitting");
    unlocked = true;
  } catch (e) { console.warn(`teacher token gate failed: ${e.message.split("\n")[0]}`); }

  if (unlocked) {
    let labs = [], sessions = [];
    try { labs = await adminApi(t, "/api/teach/labs"); } catch (e) { console.warn(`labs api: ${e.message}`); }
    try { sessions = await adminApi(t, "/api/review/sessions"); } catch (e) { console.warn(`sessions api: ${e.message}`); }
    const lab = labs.find((l) => l.kind === "lab" && l.n_sessions > 0) ?? labs.find((l) => l.kind === "lab");
    const comp = labs.find((l) => l.kind === "competition");
    const hasHash = async (sel) => t.locator(sel).first().getAttribute("href").catch(() => null);

    await step(t, "teach-labs", async () => { await go(t, "#/teach"); await wait(t, "a[href^='#/teach/labs/']"); });
    await step(t, "teach-lab-editor", async () => {
      const h = lab ? `#/teach/labs/${lab.id}` : await hasHash("a[href^='#/teach/labs/']");
      await go(t, h); await wait(t, "text=Count vowels | text=Anagram check | strong");
    });
    await step(t, "teach-lab-attendance", async () => {
      if (!lab) throw new Error("no lab");
      await go(t, `#/teach/labs/${lab.id}/attendance`); await wait(t, "table | text=ttendance");
    });
    await step(t, "teach-competition-board", async () => {
      if (!comp) throw new Error("no competition");
      await go(t, `#/teach/labs/${comp.id}/board`); await wait(t, "text=Rohan | text=Leaderboard");
    });
    await step(t, "teach-similar", async () => {
      if (!lab) throw new Error("no lab");
      await go(t, `#/teach/labs/${lab.id}/similar`); await wait(t, "main, h1, h2");
    });
    await step(t, "teach-subjects", async () => { await go(t, "#/teach/subjects"); await wait(t, "h1, h2"); });
    await step(t, "teach-setup", async () => { await go(t, "#/teach/setup"); await wait(t, "h1, h2"); });
    await step(t, "teach-people", async () => { await go(t, "#/teach/people"); await wait(t, "h1, h2"); });
    await step(t, "live-labs", async () => { await go(t, "#/live"); await wait(t, "a[href^='#/live/labs/']"); });
    await step(t, "live-class", async () => {
      const h = await hasHash("a[href^='#/live/labs/']") ?? (lab ? `#/live/labs/${lab.id}` : null);
      if (!h) throw new Error("no live lab");
      await go(t, h); await wait(t, "main, h1, h2");
    });
    await step(t, "review-overview", async () => { await go(t, "#/review"); await wait(t, "text=Lab sessions"); await t.waitForTimeout(1500); }, { full: true });
    await step(t, "review-sessions", async () => { await go(t, "#/review/sessions"); await wait(t, "a[href^='#/review/sessions/']"); });
    await step(t, "review-session-timeline", async () => {
      const pick = sessions.find((r) => r.episodes?.length) ?? sessions[0];
      if (!pick) throw new Error("no session");
      await go(t, `#/review/sessions/${pick.id}`); await wait(t, "text=Moment 1 | svg[aria-label='Evidence timeline'] | text=Nothing stood out");
    }, { full: true });
    await step(t, "sandbox-home", async () => { await go(t, "#/sandbox"); await wait(t, "h1, h2"); });
    await step(t, "sandbox-library", async () => { await go(t, "#/sandbox/library"); await wait(t, "h1, h2"); });
  } else console.warn("teacher screens after the gate skipped");
  await ctx.close();
}

await browser.close();
console.log(`captured ${captured.length}: ${captured.join(", ")}`);
if (skipped.length) console.log(`skipped ${skipped.length}: ${skipped.join(", ")}`);
