/**
 * Where the app keeps its settings and which server it is locked to.
 *
 * Server, first match wins: `--server=<origin>`, $STUDENTIDE_SERVER, settings.json,
 * DEFAULT_SERVER. Only https origins are accepted, plus http on localhost for
 * development. Portable mode (`--portable`, or the portable .exe, which sets
 * $PORTABLE_EXECUTABLE_DIR) keeps settings and the cookie jar next to the app.
 */

import { app } from "electron";
import { createHash, randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

export const DEFAULT_SERVER = "https://studentide.hokora.xyz";

export interface Settings {
  server?: string;
  installId?: string;
}

const arg = (name: string) => process.argv.find((a) => a.startsWith(`--${name}=`))?.slice(name.length + 3);

/** Must run before app "ready". Returns whether the app is portable. */
export function setupPaths(): boolean {
  const exeDir = process.env.PORTABLE_EXECUTABLE_DIR || (process.argv.includes("--portable") ? dirname(process.execPath) : "");
  const dataDir = arg("user-data");
  if (dataDir) app.setPath("userData", dataDir);
  else if (exeDir) app.setPath("userData", join(exeDir, "StudentIDE-data"));
  return Boolean(exeDir);
}

export function normaliseOrigin(raw: string): string | null {
  try {
    const u = new URL(raw.trim());
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(u.hostname);
    if (u.protocol !== "https:" && !(u.protocol === "http:" && local)) return null;
    return u.origin;
  } catch {
    return null;
  }
}

export class Config {
  private file: string;
  private data: Settings;

  constructor(readonly portable: boolean) {
    this.file = join(app.getPath("userData"), "settings.json");
    this.data = this.read();
    if (!this.data.installId) this.save({ installId: randomBytes(16).toString("hex") });
  }

  private read(): Settings {
    try { return existsSync(this.file) ? JSON.parse(readFileSync(this.file, "utf8")) : {}; } catch { return {}; }
  }

  save(patch: Partial<Settings>) {
    this.data = { ...this.data, ...patch };
    mkdirSync(dirname(this.file), { recursive: true });
    writeFileSync(this.file, JSON.stringify(this.data, null, 2));
  }

  server(): string {
    for (const c of [arg("server"), process.env.STUDENTIDE_SERVER, this.data.server]) {
      const o = c && normaliseOrigin(c);
      if (o) return o;
    }
    return DEFAULT_SERVER;
  }

  /** Hashed so the server can tell devices apart (RQ3) without learning anything about the machine. */
  deviceId(): string {
    return createHash("sha256").update(`studentide-device:${this.data.installId}`).digest("hex").slice(0, 32);
  }
}

/** -1, 0 or 1; "0.10.0" > "0.9.3". Pre-release tags are ignored. */
export function compareVersions(a: string, b: string): number {
  const pa = a.split("-")[0].split(".").map(Number), pb = b.split("-")[0].split(".").map(Number);
  for (let i = 0; i < 3; i++) {
    const d = (pa[i] || 0) - (pb[i] || 0);
    if (d) return d > 0 ? 1 : -1;
  }
  return 0;
}
