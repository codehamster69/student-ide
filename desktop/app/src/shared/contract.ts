/**
 * The contract between the desktop shell and the web app it hosts.
 *
 * The renderer is the server's own web app (same origin as the site), so every
 * existing feature runs unchanged. On top of it the shell exposes one object,
 * `window.studentDesktop`, made of namespaces. Each namespace is declared in
 * `api/<name>.ts` (its methods, events and types) and implemented by one module
 * in `src/main/modules/<name>.ts`; the thread that owns a namespace edits only
 * those two files.
 *
 * Rules every namespace follows (see docs/desktop.md):
 *  - Methods are async and take/return structured-clonable JSON only.
 *  - A failure rejects with a `DesktopError` (code + plain-English title/detail/fix),
 *    which the web app can show as is.
 *  - Events are pushed from main as `on("<ns>.<event>", cb)`; `on` returns an unsubscribe.
 *  - Nothing here imports Electron or Node, so the frontend can import these types.
 *
 * Bump CONTRACT_VERSION when a method or event changes shape (adding one is fine).
 */

import type { AppApi, AppEvents } from "./api/app";
import type { AuthApi, AuthEvents } from "./api/auth";
import type { EngineApi, EngineEvents } from "./api/engine";
import type { SandboxApi, SandboxEvents } from "./api/sandbox";
import type { TerminalApi, TerminalEvents } from "./api/terminal";
import type { UpdatesApi, UpdatesEvents } from "./api/updates";

export const CONTRACT_VERSION = 2; // 2: sandbox.* / terminal.* from @studentide/sandbox

/** IPC channel prefix: method "engine.setup" travels as "sid:engine.setup". */
export const CHANNEL_PREFIX = "sid:";
/** Synchronous channel the preload uses once to learn which methods exist. */
export const MANIFEST_CHANNEL = "sid:manifest";
/** Channel main uses to push every event: payload { name, data }. */
export const EVENT_CHANNEL = "sid:event";

/** What every failing call rejects with. Text is written for students and teachers. */
export interface DesktopError {
  code: string;          // stable id, e.g. "not_implemented", "engine_missing", "signin_cancelled"
  title: string;         // one short sentence
  detail?: string;       // what happened
  fix?: string;          // what to do about it
  needsAdmin?: boolean;
  needsReboot?: boolean;
}

/** All events, by full name. Each namespace file adds its own. */
export type DesktopEvents = AppEvents & AuthEvents & EngineEvents & SandboxEvents & TerminalEvents & UpdatesEvents;

export interface DesktopBridge {
  contract: number;
  app: AppApi;
  auth: AuthApi;
  engine: EngineApi;
  sandbox: SandboxApi;
  terminal: TerminalApi;
  /** absent in apps older than 0.2.0 */
  updates?: UpdatesApi;
  on<K extends keyof DesktopEvents>(name: K, cb: (data: DesktopEvents[K]) => void): () => void;
}

/** What main tells the preload: namespace -> method names. */
export type Manifest = { contract: number; namespaces: Record<string, string[]> };

export type { AppInfo } from "./api/app";
export type { SignInResult } from "./api/auth";
export type { EngineInfo, EngineStatus, SetupProgress } from "./api/engine";
export type { UpdateStatus } from "./api/updates";
