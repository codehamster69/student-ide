// The desktop app (desktop/app) shows this web app in its own window and adds
// `window.studentDesktop` for local features; see docs/desktop.md. In a browser
// `desktop` is null and nothing here changes behaviour. Types come from the
// shell's contract, so both sides are checked against one definition.

import type { DesktopBridge, DesktopError } from "../../desktop/app/src/shared/contract";

export type { DesktopBridge, DesktopError };

declare global {
  interface Window { studentDesktop?: DesktopBridge }
}

export const desktop: DesktopBridge | null = window.studentDesktop ?? null;

/** The hash the desktop app opens in the system browser to sign in. */
export const DESKTOP_SIGNIN = "#/desktop/signin";

/** A bridge rejection as an Error whose message is the shell's plain-English text. */
export function desktopError(err: unknown): Error {
  const e = err as Partial<DesktopError> & { message?: string };
  return new Error([e.title ?? e.message ?? String(err), e.fix].filter(Boolean).join(" "));
}

/** Recorded in sessions.client_meta.client, so analysis can separate web and desktop sessions and devices. */
export async function clientInfo(): Promise<Record<string, unknown>> {
  if (!desktop) return { kind: "web" };
  try {
    const i = await desktop.app.info();
    return { kind: "desktop", app_version: i.version, contract: i.contract, platform: i.platform, arch: i.arch,
      chrome: i.chrome, device: i.deviceId, portable: i.portable };
  } catch {
    return { kind: "desktop" };
  }
}
