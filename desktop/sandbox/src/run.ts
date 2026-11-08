/**
 * Run button and local practice tests, executed inside the instance.
 *
 * A run is the assignment's `run` command in its workdir under `bash -lc`,
 * with stdin, a time limit enforced inside the container (coreutils
 * `timeout`) and clipped output. The result has the same fields as the web
 * runner (backend/studentide/runner.py RunResult). Local tests are practice
 * only: grades come from the server, which reruns them on the uploaded
 * workspace (plan 4.4). Output comparison mirrors backend grading.py.
 */

import { runEvent, sha256, type SandboxEvent } from "./events.ts";
import { homePath, newId, type Instance } from "./instance.ts";
import { shq } from "./recipe.ts";

export const MAX_OUTPUT = 64 * 1024; // as runner.py

export interface RunResult {
  run_id: string;
  stdout: string;
  stderr: string;
  exit_code: number | null; // null when killed by the time limit
  duration_ms: number;
  error_type: string | null; // "Timeout", "OutOfMemory", "NonZeroExit" or null
  code_sha256: string;
}

export interface RunOptions {
  workdir: string;
  command: string;
  stdin?: string;
  timeoutMs?: number;
  source?: "button" | "test";
  onEvent?: (ev: SandboxEvent) => void;
}

const clip = (b: Buffer): string => {
  const s = b.subarray(0, MAX_OUTPUT).toString("utf8");
  return b.length > MAX_OUTPUT ? s + "\n… output truncated" : s;
};

/** Build outputs and caches left out of snapshots and hashes (workspace.ts). */
export const DEFAULT_EXCLUDES = ["a.out", "*.o", "*.class", "*.pyc", "core", "core.[0-9]*", "node_modules", "__pycache__", ".venv", "venv", ".cache", ".pytest_cache"];

/**
 * sha256 over the workdir's files (path + content hash), the "code" of a
 * multi-file run and the version id of a workspace snapshot. Leaves out the
 * same build outputs as the snapshot, so a restored folder hashes the same.
 */
export async function workdirHash(instance: Instance, workdir: string, excludes = DEFAULT_EXCLUDES): Promise<string> {
  const w = homePath(workdir);
  const prune = excludes.map((e) => `-name ${shq(e)}`).join(" -o ");
  const r = await instance.exec(["sh", "-c", `cd ${shq(w)} && find . \\( ${prune} \\) -prune -o -type f -print0 | LC_ALL=C sort -z | xargs -0r sha256sum`], { timeoutMs: 30_000 });
  return sha256(r.stdout);
}

export async function runCommand(instance: Instance, o: RunOptions): Promise<RunResult> {
  const w = homePath(o.workdir);
  const limitS = Math.max(1, Math.ceil((o.timeoutMs ?? 10_000) / 1000));
  const code = await workdirHash(instance, w);
  const r = await instance.exec(["timeout", "-s", "KILL", `${limitS}s`, "bash", "-lc", o.command], {
    cwd: w, stdin: o.stdin ?? "", timeoutMs: (limitS + 15) * 1000, maxStdout: MAX_OUTPUT * 2,
  });
  const killed = r.timedOut || r.code === 137;
  // timeout(1) exits 137 when it kills; an OOM kill also gives 137 but well before the limit
  const timedOut = r.timedOut || (r.code === 137 && r.durationMs >= limitS * 1000 - 250);
  const error_type = timedOut ? "Timeout" : killed ? "OutOfMemory" : r.code !== 0 ? "NonZeroExit" : null;
  const res: RunResult = {
    run_id: newId(), stdout: clip(r.stdout), stderr: r.stderr.slice(0, MAX_OUTPUT),
    exit_code: timedOut ? null : r.code, duration_ms: Math.round(r.durationMs), error_type, code_sha256: code,
  };
  o.onEvent?.(runEvent({
    runId: res.run_id, codeSha256: code, exitCode: res.exit_code, durationMs: res.duration_ms,
    errorType: error_type, source: o.source ?? "button", command: o.command,
  }));
  return res;
}

// ---- local tests ----

/** grading.py's compares; "exact" and "trim" are accepted as aliases (trim = text). */
export type Compare = "text" | "tokens" | "json" | "exact" | "trim";

export interface IoTest {
  name: string;
  stdin: string;
  expected: string;
  compare?: Compare;
}

export interface TestSpec {
  kind: "io" | "command";
  command?: string;
  timeout_s?: number;
  visible?: IoTest[];
}

export interface TestResult {
  name: string;
  passed: boolean;
  stdout: string;
  stderr: string;
  expected?: string;
  error_type: string | null;
  duration_ms: number;
}

const text = (s: string): string => s.replace(/\r\n/g, "\n").split("\n").map((l) => l.trimEnd()).join("\n").replace(/\n+$/, "");

const sameToken = (a: string, b: string): boolean => {
  if (a === b) return true;
  const x = Number(a), y = Number(b);
  if (a.trim() === "" || b.trim() === "" || !Number.isFinite(x) || !Number.isFinite(y)) return false;
  return Math.abs(x - y) <= 1e-6 * Math.max(1, Math.abs(y));
};

const sameValue = (a: unknown, b: unknown): boolean => {
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => sameValue(x, b[i]));
  if (a && b && typeof a === "object" && typeof b === "object") {
    const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
    return ka.join("\0") === kb.join("\0") && ka.every((k) => sameValue((a as any)[k], (b as any)[k]));
  }
  if (typeof a === "number" && typeof b === "number") return a === b || Math.abs(a - b) <= 1e-5 * Math.max(1, Math.abs(b));
  return a === b;
};

/** Same rules as backend grading.outputs_match ("text" is the default). */
export function outputsMatch(got: string, expected: string, compare: Compare = "text"): boolean {
  if (compare === "exact") return got === expected;
  if (compare === "tokens") {
    const g = got.split(/\s+/).filter(Boolean), e = expected.split(/\s+/).filter(Boolean);
    return g.length === e.length && g.every((x, i) => sameToken(x, e[i]!));
  }
  if (compare === "json") {
    try {
      return sameValue(JSON.parse(got), JSON.parse(expected));
    } catch {
      return false;
    }
  }
  return text(got) === text(expected);
}

export async function runTests(instance: Instance, workdir: string, runCmd: string, spec: TestSpec, onEvent?: (ev: SandboxEvent) => void): Promise<TestResult[]> {
  const timeoutMs = (spec.timeout_s ?? 10) * 1000;
  if (spec.kind === "command") {
    const r = await runCommand(instance, { workdir, command: spec.command || runCmd, timeoutMs, source: "test", onEvent });
    return [{ name: spec.command || runCmd, passed: r.exit_code === 0, stdout: r.stdout, stderr: r.stderr, error_type: r.error_type, duration_ms: r.duration_ms }];
  }
  const out: TestResult[] = [];
  for (const [i, t] of (spec.visible ?? []).entries()) {
    // one run event per Check, not one per test case, so the process channel sees one action
    const r = await runCommand(instance, { workdir, command: runCmd, stdin: t.stdin, timeoutMs, source: "test", onEvent: i === 0 ? onEvent : undefined });
    out.push({
      name: t.name, passed: r.error_type === null && outputsMatch(r.stdout, t.expected, t.compare ?? "text"),
      stdout: r.stdout, stderr: r.stderr, expected: t.expected, error_type: r.error_type, duration_ms: r.duration_ms,
    });
  }
  return out;
}
