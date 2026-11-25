/**
 * macOS self-update without a code signature: download the new .dmg and swap the
 * app bundle in place. Squirrel.Mac (electron-updater's Mac path) refuses unsigned
 * apps, so this does what a person would do by hand: mount the image, copy the app
 * next to the old one, swap them after this app has quit, and open the new one.
 * The download is checked against the SHA-256 GitHub records for the release asset.
 * It only runs where this account may replace the bundle; otherwise the update page
 * offers the download link (mode "manual").
 */

import { app, net } from "electron";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { accessSync, constants, createWriteStream, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";

export interface MacRelease { version: string; href: string; digest?: string | null; size?: number | null }

/** /Applications/Scribelab.app, from the running executable (…/Scribelab.app/Contents/MacOS/Scribelab). */
export function macBundle(): string {
  return dirname(dirname(dirname(process.execPath)));
}

/** Why this copy can't replace itself, or "" when it can. */
export function macBlocker(bundle = macBundle()): string {
  if (!bundle.endsWith(".app")) return "This copy of the app can't update itself: download the new version.";
  if (bundle.includes("/AppTranslocation/") || bundle.startsWith("/Volumes/")) {
    return "Scribelab is running from the download. Drag it to Applications once; after that it updates itself.";
  }
  try {
    accessSync(dirname(bundle), constants.W_OK);
    accessSync(bundle, constants.W_OK);
  } catch {
    return "This Mac account can't replace the app in Applications. Download the new version, or ask the lab admin to.";
  }
  return "";
}

/** The newest Mac installer for this machine from /api/desktop/release, or null. */
export async function macRelease(server: string): Promise<MacRelease | null> {
  const r = await net.fetch(`${server}/api/desktop/release`, { cache: "no-store" });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`the server answered ${r.status}`);
  const rel = (await r.json()) as { version: string; installers: { os: string; arch: string; href: string; digest?: string | null; size?: number | null }[] };
  const arch = process.arch === "arm64" ? "arm64" : "x64";
  const dmg = rel.installers.find((i) => i.os === "mac" && i.arch === arch) ?? rel.installers.find((i) => i.os === "mac");
  return dmg ? { version: rel.version, href: dmg.href, digest: dmg.digest, size: dmg.size } : null;
}

/** Downloads the .dmg into the app's data folder and checks it. Returns its path. */
export async function macDownload(server: string, rel: MacRelease, onPercent: (p: number) => void): Promise<string> {
  const dir = join(app.getPath("userData"), "updates");
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const file = join(dir, `Scribelab-${rel.version}.dmg`);
  const r = await net.fetch(new URL(rel.href, server).href, { cache: "no-store" });
  if (!r.ok || !r.body) throw new Error(`the download failed (${r.status})`);
  const total = Number(r.headers.get("content-length")) || rel.size || 0;
  const hash = createHash("sha256");
  const out = createWriteStream(file);
  let got = 0;
  const reader = r.body.getReader();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      hash.update(value);
      got += value.length;
      if (!out.write(value)) await new Promise<void>((ok) => out.once("drain", () => ok()));
      if (total) onPercent(Math.min(99, Math.round((got / total) * 100)));
    }
  } finally {
    await new Promise<void>((ok) => out.end(() => ok()));
  }
  const want = rel.digest?.startsWith("sha256:") ? rel.digest.slice(7).toLowerCase() : "";
  if (want && hash.digest("hex") !== want) {
    rmSync(file, { force: true });
    throw new Error("the download was damaged (checksum mismatch); it will be fetched again");
  }
  return file;
}

// Runs after the app has quit: mount, copy beside, swap, unmount, reopen. A failed
// swap puts the old app back, so the student always has a working copy.
const SWAP = `
pid="$1"; dmg="$2"; target="$3"
exec >>"$4" 2>&1
while kill -0 "$pid" 2>/dev/null; do sleep 0.5; done
mnt=$(mktemp -d /tmp/scribelab-update.XXXXXX) || { open "$target"; exit 1; }
if hdiutil attach -nobrowse -noautoopen -readonly -mountpoint "$mnt" "$dmg"; then
  src=$(ls -d "$mnt"/*.app 2>/dev/null | head -n 1)
  new="$target.new.$$"; old="$target.old.$$"
  if [ -n "$src" ] && ditto "$src" "$new"; then
    xattr -dr com.apple.quarantine "$new" 2>/dev/null
    if mv "$target" "$old"; then
      if mv "$new" "$target"; then rm -rf "$old"; else mv "$old" "$target"; fi
    fi
  fi
  rm -rf "$new"
  hdiutil detach "$mnt" -quiet || hdiutil detach "$mnt" -force -quiet
fi
rmdir "$mnt" 2>/dev/null; rm -f "$dmg"
open "$target"
`;

/** Hands the swap to a detached shell and quits; the new version opens by itself. */
export function macInstall(dmg: string, bundle = macBundle()) {
  const log = join(app.getPath("userData"), "update.log");
  const child = spawn("/bin/sh", ["-c", SWAP, "scribelab-update", String(process.pid), dmg, bundle, log],
    { detached: true, stdio: "ignore" });
  child.unref();
  app.quit();
}
