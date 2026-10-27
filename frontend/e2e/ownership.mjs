// End-to-end check of lab ownership, with screenshots for the thesis: an admin
// hands the demo lab (made before ownership, so admins only) to a teacher; she
// sees only her labs, shares one with a colleague and reviews it lab session by
// lab session; a third teacher who opens its link is refused without being
// signed out.
//
//   BASE=http://127.0.0.1:8011 node frontend/e2e/ownership.mjs [screenshot-dir] [light|dark]
//
// Needs a server in Google mode whose token check accepts the address as the
// credential (tests' fake_google), admin pg25cs07@iiitsurat.ac.in, seeded with
// `python -m studentide.seed`.

import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8011";
const [OUT, SCHEME = "light"] = process.argv.slice(2);
const D = "@iiitsurat.ac.in";
const ADMIN = `pg25cs07${D}`, PRIYA = `priya.shah${D}`, MEERA = `meera.rao${D}`, ARJUN = `arjun.mehta${D}`;

const browser = await chromium.launch();
const errors = [];

/** A browser signed in as `email` (its own cookie jar). */
const as = async (email, w = 1440, h = 900) => {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: SCHEME, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  const r = await page.request.post(`${BASE}/api/auth/google`, { data: { credential: email } });
  assert.equal(r.status(), 200, `sign in ${email}`);
  return page;
};
const go = async (page, hash, ready) => {
  await page.goto(`${BASE}/${hash}`);
  if (ready) await page.waitForSelector(ready);
};
const shot = async (page, name, full = false) => {
  if (!OUT) return;
  await page.waitForTimeout(1200);
  await page.addStyleTag({ content: "header.sticky { position: relative !important; }" });
  await page.screenshot({ path: `${OUT}/ownership-${SCHEME}-${name}.png`, fullPage: full });
};

// --- admin: labs from before ownership are theirs until handed over ---------------
const admin = await as(ADMIN);
await go(admin, "#/teach", "text=Lab 5: Strings and dictionaries");
assert.ok(await admin.isVisible("text=No owner yet"), "unowned labs are marked for admins");
await shot(admin, "01-admin-unowned");
await admin.click("text=Lab 5: Strings and dictionaries");
await admin.waitForSelector("h2:has-text('Teachers')");
await admin.fill("input[aria-label=Owner]", PRIYA);
await admin.click("button:has-text('Hand over')");
await admin.waitForSelector(`text=${PRIYA}`);

// --- a colleague makes a lab of her own -----------------------------------------------
const meera = await as(MEERA);
await meera.request.post(`${BASE}/api/teach/labs`, { data: { title: "Lab 3: Arrays", subject: "Programming in C", language: "c" } });

// --- the owner: only her labs; shares one; reviews it by lab session --------------
const priya = await as(PRIYA);
await go(priya, "#/teach", "text=Lab 5: Strings and dictionaries");
assert.ok(!(await priya.isVisible("text=Lab 3: Arrays")), "another teacher's lab is not listed");
assert.ok(!(await priya.isVisible("text=Lab 6: Recursion")), "an unowned lab is not listed");
await priya.click("text=Lab 5: Strings and dictionaries");
await priya.waitForSelector("h2:has-text('Teachers')");
await priya.fill("input[aria-label='Share with a co-teacher']", MEERA);
await priya.click("button:has-text('Share')");
await priya.waitForSelector(`button:has-text('${MEERA}')`);
const panel = priya.locator("aside > div", { has: priya.locator("h2:has-text('Teachers')") });
if (OUT) { await priya.waitForTimeout(800); await panel.screenshot({ path: `${OUT}/ownership-${SCHEME}-02-teachers-panel.png` }); }

await go(priya, "#/review", "text=Lab sessions");
await priya.waitForSelector("a[href^='#/review/l/lab_demo1/']");
assert.ok(!(await priya.isVisible("text=Practice tasks")), "practice sessions are for admins only");
await shot(priya, "03-review-lab-sessions");
await priya.click("a[href^='#/review/l/lab_demo1/']");
await priya.waitForSelector("h1:has-text('Lab 5: Strings and dictionaries')");
await priya.waitForSelector("a[href^='#/review/s/']");
await shot(priya, "04-review-one-lab", true);
await priya.click("a[href^='#/review/s/']");
await priya.waitForSelector("text=Back to the lab session");

// --- the co-teacher sees the shared lab next to her own -----------------------------
await go(meera, "#/teach", "text=Lab 5: Strings and dictionaries");
assert.ok(await meera.isVisible("text=Shared with you"), "shared lab is marked");
assert.ok(await meera.isVisible("text=Lab 3: Arrays"));
await shot(meera, "05-co-teacher-labs");

// --- anyone else: refused with a message, still signed in -------------------------------
const arjun = await as(ARJUN);
await go(arjun, "#/teach/l/lab_demo1", "text=this lab belongs to another teacher");
assert.ok(await arjun.isVisible("text=Sign out"), "a refusal does not sign the teacher out");
await shot(arjun, "06-not-yours");

// --- admins still see everything -------------------------------------------------------
await go(admin, "#/review", "text=Practice tasks");
await shot(admin, "07-admin-review");

await browser.close();
assert.deepEqual(errors, [], "no page errors");
console.log("ownership e2e ok");
