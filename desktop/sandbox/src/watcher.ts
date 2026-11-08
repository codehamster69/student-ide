/**
 * The sidecar watcher: fs_change and port_open events that root inside the
 * instance cannot switch off (plan 4.2, "Where the capture runs").
 *
 * `sidwatch-<instance>` runs from the instance's own image (always present),
 * joins the instance's PID namespace, mounts the student's volume read-only
 * at /w and has no network. A POSIX sh loop (busybox works too) prints:
 *
 *   B <size> <sha256> <path>   baseline, the files there when it started
 *   R                          baseline done
 *   F <size> <sha256> <path>   a file was written
 *   D <path>                   a file went away
 *   L <port> <process>         something started listening (tcp, tcp6)
 *   U <port>                   it stopped
 *
 * The host side (FsWatch) turns those into events: it drops the saves the
 * app made itself (editor writes, restores), reads the new text through the
 * sidecar, diffs it against the last text it knew, and records which command
 * was running so the review can say "saved from vim" or "changed outside the
 * app". Build outputs and dot-folders are left out, like snapshots.
 */

import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { sha256, type SandboxEvent } from "./events.ts";
import { HOME, LABEL, type Instance } from "./instance.ts";
import { DEFAULT_EXCLUDES } from "./run.ts";
import { lineDiff } from "./textdiff.ts";

export const WATCH_MS = 1000;
export const MAX_TEXT = 512 * 1024;

const prune = (excludes: string[]) => ["-path '/w/.*'", ...excludes.map((e) => `-name '${e.replace(/'/g, "")}'`)].join(" -o ");

/** The sidecar's script. Kept to sh, find, stat-free ls and sha256sum so busybox images work. */
export function watchScript(excludes = DEFAULT_EXCLUDES, everyMs = WATCH_MS): string {
  const P = prune(excludes);
  const sleep = (everyMs / 1000).toFixed(1);
  return `
set -u
cd /w || exit 1
T=/tmp/sidwatch; mkdir -p $T; touch $T/old; sleep 1; touch $T/stamp # whole-second clocks: no blind second at start
emit() { k=$1; while IFS= read -r f; do [ -f "$f" ] || continue; s=$(wc -c < "$f" 2>/dev/null) || continue; h=$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1); echo "$k $s $h $f"; done; }
list() { find /w \\( ${P} \\) -prune -o -type f -print 2>/dev/null | LC_ALL=C sort; }
list > $T/prev; emit B < $T/prev; echo R
ports() { for t in /proc/1/net/tcp /proc/1/net/tcp6; do [ -r $t ] && awk 'NR>1 && $4=="0A" {split($2,a,":"); print a[2], $10}' $t; done 2>/dev/null | sort -u; }
pname() { for p in /proc/[0-9]*; do ls -l $p/fd 2>/dev/null | grep -q "socket:\\[$1\\]" && { cat $p/comm 2>/dev/null; return; }; done; echo "?"; }
: > $T/ports; n=0
while :; do
  touch $T/next
  # against the stamp from two rounds ago: busybox compares whole seconds; the host drops repeats
  find /w \\( ${P} \\) -prune -o -type f -newer $T/old -print 2>/dev/null | emit F
  mv $T/stamp $T/old; mv $T/next $T/stamp
  n=$((n+1))
  if [ $((n % 3)) -eq 0 ]; then
    list > $T/now; LC_ALL=C comm -23 $T/prev $T/now | sed 's/^/D /'; mv $T/now $T/prev
    ports > $T/pnow
    LC_ALL=C comm -13 $T/ports $T/pnow | while read -r hex ino; do echo "L $(printf %d 0x$hex) $(pname $ino)"; done
    LC_ALL=C comm -23 $T/ports $T/pnow | while read -r hex ino; do echo "U $(printf %d 0x$hex)"; done
    mv $T/pnow $T/ports
  fi
  sleep ${sleep}
done
`;
}

export type WatchLine =
  | { kind: "B" | "F"; size: number; sha: string; path: string }
  | { kind: "D"; path: string }
  | { kind: "L"; port: number; process: string }
  | { kind: "U"; port: number }
  | { kind: "R" };

/** One sidecar output line, or null for anything else. Paths come back under HOME. */
export function parseWatchLine(line: string): WatchLine | null {
  const l = line.replace(/\r$/, "");
  if (l === "R") return { kind: "R" };
  let m = /^([BF]) (\d+) ([0-9a-f]{64}) \/w\/(.+)$/.exec(l);
  if (m) return { kind: m[1] as "B" | "F", size: Number(m[2]), sha: m[3]!, path: `${HOME}/${m[4]}` };
  m = /^D \/w\/(.+)$/.exec(l);
  if (m) return { kind: "D", path: `${HOME}/${m[1]}` };
  m = /^L (\d+) (.*)$/.exec(l);
  if (m) return { kind: "L", port: Number(m[1]), process: m[2]!.trim().slice(0, 64) || "?" };
  m = /^U (\d+)$/.exec(l);
  if (m) return { kind: "U", port: Number(m[1]) };
  return null;
}

/** What the app knows about the moment a file changed. */
export interface WatchContext {
  /** the assignment session that owns this path, or null to ignore it */
  sessionKey(path: string): string | null;
  /** the terminal's foreground command and vim/nano file, if a terminal is open on the instance */
  foreground(): { command: string; editorFile: string | null } | null;
  /** read the file's bytes (through the sidecar, so the instance cannot fake them) */
  read(path: string): Promise<Buffer>;
}

export type FsOrigin = "terminal-editor" | "terminal" | "outside";

export function fsChange(d: {
  path: string; size: number; sha: string; origin: FsOrigin; command: string | null; deleted?: boolean;
  binary?: boolean; diff?: ReturnType<typeof lineDiff> | null;
}): SandboxEvent {
  return {
    type: "fs_change",
    data: {
      path: d.path.slice(0, 512), size: d.size, sha256: d.sha, origin: d.origin,
      command: d.command ? d.command.slice(0, 4096) : null, deleted: d.deleted ?? false, binary: d.binary ?? false,
      added: d.diff?.added ?? "", added_lines: d.diff?.addedLines ?? 0, removed_lines: d.diff?.removedLines ?? 0,
      diff: d.diff?.diff ?? "", truncated: d.diff?.truncated ?? false,
    },
  };
}

export function portOpen(port: number, process: string, open: boolean): SandboxEvent {
  return { type: "port_open", data: { port, process: process.slice(0, 64), open } };
}

const isText = (b: Buffer) => !b.subarray(0, 8000).includes(0);

/**
 * Turns sidecar lines into events. Pure apart from ctx.read, so tests feed it
 * lines directly. Call expect(path, text) before the app itself writes a file:
 * that save is then not reported (the editor already logged it as edits).
 */
export class FsWatch {
  private known = new Map<string, { sha: string; text: string | null }>();
  private expected = new Map<string, string>(); // path -> sha the app is about to write
  private ports = new Set<number>();
  ready = false;

  private ctx: WatchContext;
  private onEvent: (sessionKey: string, ev: SandboxEvent) => void;
  private onPort?: (sessionKey: string | null, ev: SandboxEvent) => void;

  constructor(ctx: WatchContext, onEvent: (sessionKey: string, ev: SandboxEvent) => void, onPort?: (sessionKey: string | null, ev: SandboxEvent) => void) {
    this.ctx = ctx;
    this.onEvent = onEvent;
    this.onPort = onPort;
  }

  /** The app writes this content to path next (editor save, restore, starter files). */
  expect(path: string, content: string | Buffer): void {
    this.expected.set(path, sha256(content));
    this.known.set(path, { sha: sha256(content), text: typeof content === "string" ? content : isText(content) ? content.toString("utf8") : null });
  }

  async line(raw: string): Promise<void> {
    const w = parseWatchLine(raw);
    if (!w) return;
    if (w.kind === "R") { this.ready = true; return; }
    if (w.kind === "L" || w.kind === "U") {
      const open = w.kind === "L";
      if (open === this.ports.has(w.port)) return;
      if (open) this.ports.add(w.port); else this.ports.delete(w.port);
      const ev = portOpen(w.port, w.kind === "L" ? w.process : "", open);
      this.onPort?.(null, ev);
      return;
    }
    const key = this.ctx.sessionKey(w.path);
    if (w.kind === "B") {
      if (this.known.has(w.path)) return;
      // the text of assignment files, so the first save diffs against what was there
      let text: string | null = null;
      if (key && w.size <= MAX_TEXT) {
        const b = await this.ctx.read(w.path).catch(() => null);
        if (b && isText(b) && sha256(b) === w.sha) text = b.toString("utf8");
      }
      this.known.set(w.path, { sha: w.sha, text });
      return;
    }
    if (w.kind === "D") {
      const had = this.known.get(w.path);
      this.known.delete(w.path);
      this.expected.delete(w.path);
      if (key && had) this.onEvent(key, fsChange({ path: w.path, size: 0, sha: "", deleted: true, ...this.who() }));
      return;
    }
    // F: a write. Drop repeats and the app's own saves.
    const prev = this.known.get(w.path);
    if (prev?.sha === w.sha) return;
    if (this.expected.get(w.path) === w.sha) {
      this.expected.delete(w.path);
      return;
    }
    if (!key) {
      this.known.set(w.path, { sha: w.sha, text: null });
      return;
    }
    let text: string | null = null;
    let binary = false;
    if (w.size <= MAX_TEXT) {
      const b = await this.ctx.read(w.path).catch(() => null);
      if (b && isText(b)) text = b.toString("utf8"); else binary = Boolean(b);
    }
    // the file may have changed again while we read it; the sha we report is the one we diffed
    const sha = text !== null ? sha256(text) : w.sha;
    if (prev?.sha === sha) return;
    this.known.set(w.path, { sha, text });
    const diff = text !== null ? lineDiff(prev?.text ?? "", text) : null;
    this.onEvent(key, fsChange({ path: w.path, size: text !== null ? Buffer.byteLength(text) : w.size, sha, binary, diff, ...this.who() }));
  }

  /** Who changed the file: vim/nano in the terminal, another terminal command, or nobody we can see. */
  private who(): { origin: FsOrigin; command: string | null } {
    const fg = this.ctx.foreground();
    if (!fg) return { origin: "outside", command: null };
    return { origin: fg.editorFile !== null ? "terminal-editor" : "terminal", command: fg.command };
  }
}

export const watcherName = (instance: Instance) => `sidwatch-${instance.name}`.slice(0, 63);

/** create/run args for the sidecar; it lives only as long as the instance runs */
export function watcherArgs(instance: Instance, image: string, script: string): string[] {
  return [
    "run", "-d", "--rm", "--name", watcherName(instance), "--label", `${LABEL}=1`, "--label", "studentide.role=watcher",
    "--pid", `container:${instance.name}`, "--network", "none",
    "-v", `${instance.volume}:/w:ro`, "--security-opt", "label=disable",
    "--user", "0", "--memory", "64m", "--pids-limit", "64",
    "--cap-drop", "ALL", "--cap-add", "DAC_READ_SEARCH", "--cap-add", "SYS_PTRACE",
    "--entrypoint", "sh", image, "-c", script,
  ];
}

/**
 * Start the sidecar for a running instance and follow it. Returns stop().
 * The watcher is best effort: if the engine refuses it (old Podman without
 * --pid container:), the lab still runs and the review says file changes in
 * the terminal were not watched.
 */
export async function startWatcher(instance: Instance, w: FsWatch, onDown?: (why: string) => void): Promise<() => void> {
  const e = instance.engine;
  const name = watcherName(instance);
  await e.call(["rm", "-f", name], { timeoutMs: 30_000 });
  await e.ok(watcherArgs(instance, instance.imageRef, watchScript()), { timeoutMs: 60_000 });
  const p: ChildProcessWithoutNullStreams = e.spawn(["logs", "-f", name]);
  let buf = "";
  let chain = Promise.resolve();
  p.stdout.on("data", (b: Buffer) => {
    buf += b.toString("utf8");
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const l of lines) chain = chain.then(() => w.line(l)).catch(() => {});
  });
  p.stderr.on("data", () => {});
  p.stdin.end();
  let stopped = false;
  p.on("exit", () => { if (!stopped) onDown?.("the file watcher stopped"); });
  p.on("error", () => {});
  return () => {
    stopped = true;
    p.kill();
    void e.call(["rm", "-f", name], { timeoutMs: 30_000 });
  };
}

/** Read a file through the sidecar (read-only mount), not through the instance. */
export async function readViaWatcher(instance: Instance, path: string, maxBytes = MAX_TEXT): Promise<Buffer> {
  const rel = path.startsWith(`${HOME}/`) ? path.slice(HOME.length + 1) : path;
  if (rel.split("/").includes("..")) throw new Error("bad path");
  const r = await instance.engine.call(["exec", watcherName(instance), "head", "-c", String(maxBytes), `/w/${rel}`], { timeoutMs: 15_000, maxStdout: maxBytes + 1 });
  if (r.code !== 0) throw new Error(`read ${path}: ${r.stderr.trim()}`);
  return r.stdout;
}
