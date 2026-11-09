// The public desktop download page (#/download): the installer for this computer first,
// every other system below, a phone gets the list only, no release = a plain note; the
// login page links to it. The release list is stubbed so this needs no GitHub release.
//
//   BASE=http://127.0.0.1:8000 node frontend/e2e/download.mjs [screenshot-dir]

import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const [S] = process.argv.slice(2);
const BASE = process.env.BASE ?? "http://127.0.0.1:8000";
const mk = (os, arch, kind, label, note, file, size) => ({ os, arch, kind, label, note, file, size, href: `/api/desktop/updates/${file}` });
const REL = { version: "0.2.0", published_at: "2026-11-09T06:20:00Z", installers: [
  mk("windows","x64","installer","Windows","Installer for Windows 10 and 11 (64-bit)","StudentIDE-0.2.0-win-x64.exe",98e6),
  mk("windows","x64","portable","Windows, portable","Runs without installing, for lab PCs; does not update itself","StudentIDE-0.2.0-portable.exe",97e6),
  mk("mac","arm64","installer","Mac with Apple silicon","M1 and newer","StudentIDE-0.2.0-mac-arm64.dmg",120e6),
  mk("mac","x64","installer","Mac with Intel","Older Macs (2020 and before)","StudentIDE-0.2.0-mac-x64.dmg",125e6),
  mk("linux","x64","installer","Linux (AppImage)","Any 64-bit distribution","StudentIDE-0.2.0-linux-x86_64.AppImage",110e6),
  mk("linux","x64","deb","Linux (.deb)","Ubuntu and Debian","StudentIDE-0.2.0-linux-amd64.deb",80e6)] };
const b = await chromium.launch();
const errs = [];
for (const [name, ua, scheme, w] of [["win","Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36","light",1280],
  ["mac","Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Version/18 Safari/605.1.15","dark",1280],
  ["phone","Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148","light",390]]) {
  const p = await b.newPage({ userAgent: ua, colorScheme: scheme, viewport: { width: w, height: 900 } });
  p.on("pageerror", (e) => errs.push(e.message));
  await p.route("**/api/desktop/release", (r) => r.fulfill({ json: REL }));
  await p.goto(`${BASE}/#/download`);
  await p.waitForSelector("text=Version 0.2.0");
  const prim = await p.locator("[data-testid=primary-download]").count() ? await p.locator("[data-testid=primary-download]").innerText() : "(none)";
  assert.match(prim, { win: /Download for Windows/, mac: /Download for Mac/, phone: /\(none\)/ }[name]);
  assert.equal(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${name}: no sideways scroll`);
  if (S) { await p.waitForTimeout(600); await p.screenshot({ path: `${S}/download-${name}.png`, fullPage: true }); }
}
// no release
const p = await b.newPage();
await p.goto(`${BASE}/#/download`);
await p.waitForSelector("text=isn't available");

await p.goto(`${BASE}/#/`);
await p.waitForTimeout(1500);
assert.equal(await p.locator("text=Get the desktop app").count(), 1);
await b.close();
assert.deepEqual(errs, []);
console.log("download page e2e: ok");
