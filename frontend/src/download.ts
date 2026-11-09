// Desktop app downloads for browsers: which installer fits this computer, and the
// newest release as the server lists it (GET /api/desktop/release, from GitHub Releases).
// Used by the public #/download page and the "Get the app" button on the student home.

import { href } from "./routes";

export type DesktopOs = "windows" | "mac" | "linux";
export type Installer = { os: DesktopOs; arch: "x64" | "arm64"; kind: "installer" | "portable" | "deb"; label: string;
  note: string; file: string; size: number | null; href: string };
export type Release = { version: string; published_at: string | null; installers: Installer[] };

export const DOWNLOAD_PAGE = href.download;

type UAData = { platform?: string; getHighEntropyValues?: (h: string[]) => Promise<{ architecture?: string }> };

/** This computer's OS and, where the browser says, its CPU. Phones and tablets get null. */
export async function detectPlatform(): Promise<{ os: DesktopOs; arch: "x64" | "arm64" | null } | null> {
  const ua = navigator.userAgent;
  const data = (navigator as Navigator & { userAgentData?: UAData }).userAgentData;
  if (/Android|iPhone|iPad|iPod/i.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return null;
  const p = `${data?.platform ?? ""} ${navigator.platform ?? ""} ${ua}`;
  const os: DesktopOs | null = /Win/i.test(p) ? "windows" : /Mac/i.test(p) ? "mac" : /Linux|X11|CrOS/i.test(p) ? "linux" : null;
  if (!os) return null;
  let arch: "x64" | "arm64" | null = null;
  try {
    const a = (await data?.getHighEntropyValues?.(["architecture"]))?.architecture;
    if (a) arch = a === "arm" ? "arm64" : "x64";
  } catch { /* not offered: guess below */ }
  // Safari reports Intel on every Mac; nearly all Macs students bring now are Apple silicon
  if (os === "mac" && arch === null) arch = "arm64";
  return { os, arch };
}

/** The installer to offer first for this computer, or null if the release has none. */
export function bestInstaller(rel: Release, p: { os: DesktopOs; arch: "x64" | "arm64" | null } | null): Installer | null {
  if (!p) return null;
  const mine = rel.installers.filter((i) => i.os === p.os && i.kind === "installer");
  return mine.find((i) => i.arch === (p.arch ?? "x64")) ?? mine[0] ?? null;
}

export async function latestRelease(): Promise<Release | null> {
  try {
    const r = await fetch("/api/desktop/release", { credentials: "same-origin" });
    return r.ok ? await r.json() : null;
  } catch { return null; }
}

export const megabytes = (n: number | null) => (n ? `${Math.round(n / 1e6)} MB` : "");
