/**
 * Interactive terminal in the instance, wired for xterm.js in the renderer.
 *
 * `exec -i` carries the bytes; `script` inside the container gives bash a
 * real PTY, so no native module is needed on the host. The shell's marks
 * (hooks.ts) become term_cmd / term_output events, package commands feed the
 * setup recipe, and while vim or nano is in the foreground `surface()` tells
 * the renderer to tag keys "terminal-editor" with the file.
 *
 * Key timing is never taken from here: the renderer captures it (plan 4.2).
 */

import { EventEmitter } from "node:events";
import { StringDecoder } from "node:string_decoder";
import type { ChildProcessWithoutNullStreams } from "node:child_process";
import { resizeCommand, terminalCommand } from "./hooks.ts";
import { MarkParser, terminalEditor, type Mark } from "./marks.ts";
import { isBuildOrRun, pkgInstall, runEvent, sha256, termCmdEnd, termCmdStart, termOutput, terminalKeySurface, type SandboxEvent } from "./events.ts";
import { HOME, newId, type Instance } from "./instance.ts";
import { parseCommandLine } from "./recipe.ts";

export const SCROLLBACK_LINES = 5000;
const TAIL_KEEP = 4096;

export interface TerminalOptions {
  cwd?: string;
  cols?: number;
  rows?: number;
  /** called for every sandbox event this terminal produces */
  onEvent?: (ev: SandboxEvent) => void;
  /** a package command succeeded (for the setup recipe) */
  onPackageCommand?: (command: string, cwd: string) => void;
}

interface Running {
  n: number;
  command: string;
  cwd: string;
  started: number;
  bytes: number;
  tail: string;
}

export class Terminal extends EventEmitter {
  readonly id = newId();
  readonly instance: Instance;
  private proc: ChildProcessWithoutNullStreams | null = null;
  private parser = new MarkParser();
  private decoder = new StringDecoder("utf8");
  private running: Running | null = null;
  private lastN = -1;
  private lastMarkAt = 0;
  private scroll: string[] = [""];
  private opts: TerminalOptions;
  closed = false;

  constructor(instance: Instance, opts: TerminalOptions = {}) {
    super();
    this.instance = instance;
    this.opts = opts;
  }

  get cwd(): string {
    return this.opts.cwd ?? HOME;
  }

  /** Spawn the shell. Emits "data" (string for xterm.js) and "exit" (code). */
  open(): this {
    const cols = this.opts.cols ?? 80;
    const rows = this.opts.rows ?? 24;
    const args = ["exec", "-i", "-u", "student", "-w", this.opts.cwd ?? HOME, this.instance.name, ...terminalCommand(this.id, cols, rows)];
    const p = this.instance.engine.spawn(args);
    this.proc = p;
    p.stdout.on("data", (b: Buffer) => this.onOutput(b));
    p.stderr.on("data", (b: Buffer) => this.onOutput(b));
    p.stdin.on("error", () => {});
    p.on("close", (code) => {
      this.closed = true;
      this.emit("exit", code);
    });
    p.on("error", (e) => this.emit("error", e));
    return this;
  }

  /** Bytes typed or pasted in xterm.js. */
  write(data: string): void {
    if (!this.proc || this.closed) return;
    this.instance.touch();
    this.proc.stdin.write(data);
  }

  async resize(cols: number, rows: number): Promise<void> {
    if (this.closed) return;
    await this.instance.exec(resizeCommand(this.id, cols, rows), { timeoutMs: 10_000 });
  }

  close(): void {
    if (this.proc && !this.closed) {
      this.proc.stdin.end();
      this.proc.kill();
    }
  }

  /** Where keys typed into this terminal right now belong. */
  surface(): ReturnType<typeof terminalKeySurface> {
    return terminalKeySurface(this.running ? terminalEditor(this.running.command) : null);
  }

  /** The command in the foreground, if any. */
  foreground(): { command: string; cwd: string; sinceMs: number } | null {
    return this.running ? { command: this.running.command, cwd: this.running.cwd, sinceMs: Date.now() - this.running.started } : null;
  }

  /** Last lines of output for restoring the view after a reload (not synced between machines). */
  scrollback(): string {
    return this.scroll.join("\n");
  }

  /** Seconds since the shell last reported a command or prompt (hooks removed or long command). */
  hooksQuietMs(): number {
    return this.lastMarkAt ? Date.now() - this.lastMarkAt : Infinity;
  }

  private emitEvent(ev: SandboxEvent): void {
    this.opts.onEvent?.(ev);
    this.emit("event", ev);
  }

  private onOutput(b: Buffer): void {
    let screen = "";
    for (const seg of this.parser.segments(this.decoder.write(b))) {
      if (typeof seg !== "string") {
        this.onMark(seg);
        continue;
      }
      if (this.running) {
        this.running.bytes += Buffer.byteLength(seg);
        this.running.tail = (this.running.tail + seg).slice(-TAIL_KEEP);
      }
      screen += seg;
    }
    if (screen) {
      this.keepScroll(screen);
      this.emit("data", screen);
    }
  }

  private keepScroll(text: string): void {
    const parts = text.split("\n");
    this.scroll[this.scroll.length - 1] = (this.scroll[this.scroll.length - 1] ?? "") + (parts[0] ?? "");
    for (let i = 1; i < parts.length; i++) this.scroll.push(parts[i]!);
    if (this.scroll.length > SCROLLBACK_LINES) this.scroll.splice(0, this.scroll.length - SCROLLBACK_LINES);
  }

  private onMark(m: Mark): void {
    this.lastMarkAt = Date.now();
    if (m.kind === "start") {
      if (m.n === this.lastN || !m.command.trim()) return; // history did not move: empty line or ignored command
      this.lastN = m.n;
      this.running = { n: m.n, command: m.command, cwd: m.cwd, started: Date.now(), bytes: 0, tail: "" };
      this.emitEvent(termCmdStart(this.id, m.command, m.cwd));
      return;
    }
    const r = this.running;
    if (!r) return; // a prompt with no command (Enter on an empty line, first prompt)
    this.running = null;
    const dur = Date.now() - r.started;
    this.emitEvent(termCmdEnd(this.id, r.command, r.cwd, m.exitCode, dur));
    if (r.bytes) this.emitEvent(termOutput(this.id, r.bytes, stripAnsi(r.tail)));
    if (isBuildOrRun(r.command)) {
      this.emitEvent(runEvent({
        runId: `t-${this.id}-${r.n}`, codeSha256: sha256(r.command), exitCode: m.exitCode, durationMs: dur,
        errorType: m.exitCode === 0 ? null : "NonZeroExit", source: "terminal", command: r.command,
      }));
    }
    if (m.exitCode === 0) {
      const pk = parseCommandLine(r.command);
      for (const p of pk) this.emitEvent(pkgInstall(p.manager, p.action, p.packages, r.command));
      if (pk.length) this.opts.onPackageCommand?.(r.command, r.cwd);
    }
  }
}

// eslint-disable-next-line no-control-regex
const ANSI = /\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(\x07|\x1b\\)|\x1b[@-Z\\-_]/g;
export const stripAnsi = (s: string): string => s.replace(ANSI, "").replace(/\r(?!\n)/g, "");
