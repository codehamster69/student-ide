/**
 * Builders for the event schema v2 payloads the sandbox emits.
 *
 * The runtime only builds `{type, data}`; the renderer's recorder adds seq
 * and t, so sandbox events share one ordered stream with editor events.
 * Field names match backend/studentide/schema.py (see docs/event-schema.md).
 */

import { createHash } from "node:crypto";

export const MAX_COMMAND = 4096;
export const MAX_TAIL = 2048;
export const MAX_PASTE = 20_000; // same cap as editor pastes (recorder MAX_CLIPBOARD)

export type Surface = "editor" | "terminal" | "terminal-editor";

export interface SandboxEvent {
  type: "term_cmd" | "term_output" | "term_paste" | "run" | "pkg_install" | "net_conn";
  data: Record<string, unknown>;
}

export type EventSink = (sessionKey: string, ev: SandboxEvent) => void;

const clip = (s: string, n: number): [string, boolean] => (s.length > n ? [s.slice(0, n), true] : [s, false]);
export const sha256 = (s: string | Buffer): string => createHash("sha256").update(s).digest("hex");

export function termCmdStart(termId: string, command: string, cwd: string): SandboxEvent {
  const [c, truncated] = clip(command, MAX_COMMAND);
  return { type: "term_cmd", data: { term_id: termId, phase: "start", command: c, cwd, truncated } };
}

export function termCmdEnd(termId: string, command: string, cwd: string, exitCode: number | null, durationMs: number): SandboxEvent {
  const [c, truncated] = clip(command, MAX_COMMAND);
  return {
    type: "term_cmd",
    data: { term_id: termId, phase: "end", command: c, cwd, truncated, exit_code: exitCode, duration_ms: Math.round(durationMs) },
  };
}

export function termOutput(termId: string, bytes: number, tail: string): SandboxEvent {
  return { type: "term_output", data: { term_id: termId, bytes, tail: tail.slice(-MAX_TAIL), truncated: tail.length > MAX_TAIL } };
}

/** For the renderer: a paste into xterm.js (the text then arrives as terminal input). */
export function termPaste(termId: string, text: string): SandboxEvent {
  const [t, truncated] = clip(text, MAX_PASTE);
  return {
    type: "term_paste",
    data: { term_id: termId, length: text.length, lines: text.split("\n").length, text: t, truncated, sha256: sha256(text) },
  };
}

/** Key event payload for a key typed in a terminal (the renderer owns timing). */
export function terminalKeySurface(fg: { editor: string; file: string | null } | null): { surface: Surface; path?: string } {
  return fg ? { surface: "terminal-editor", ...(fg.file ? { path: fg.file } : {}) } : { surface: "terminal" };
}

export function runEvent(r: {
  runId: string; codeSha256: string; exitCode: number | null; durationMs: number; errorType: string | null;
  source: "button" | "test" | "terminal"; command: string;
}): SandboxEvent {
  return {
    type: "run",
    data: {
      run_id: r.runId, code_sha256: r.codeSha256, exit_code: r.exitCode, duration_ms: Math.round(r.durationMs),
      error_type: r.errorType, source: r.source, command: clip(r.command, MAX_COMMAND)[0],
    },
  };
}

export function pkgInstall(manager: string, action: "install" | "remove", packages: string[], command: string): SandboxEvent {
  return { type: "pkg_install", data: { manager, action, packages: packages.slice(0, 200), command: clip(command, MAX_COMMAND)[0] } };
}

export function netConn(host: string, port: number | null, allowed: boolean): SandboxEvent {
  return { type: "net_conn", data: { host: host.slice(0, 253), port, allowed } };
}

/** Commands that compile or run code, counted as runs for the detector's process channel. */
export function isBuildOrRun(command: string): boolean {
  const w = command.trim().replace(/^(sudo\s+|time\s+)+/, "").split(/\s+/)[0] ?? "";
  if (/^\.{1,2}\//.test(w)) return true; // ./a.out, ./main
  return /^(gcc|g\+\+|cc|c\+\+|clang|clang\+\+|make|cmake|python3?|node|java|javac|mvn|gradle|cargo|rustc|go|ruby|php|bash|sh|pytest|npm|npx|dotnet|gdb|valgrind)$/.test(w)
    && !/^(npm|npx)\s+(i|install|ci|add|uninstall|remove)\b/.test(command.trim());
}
