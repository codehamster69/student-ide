/**
 * Container engine access through the docker or podman command line.
 *
 * The installer saves an EngineInfo (engine.json in the app's userData); the
 * `cli` argv prefix is all we need: ["docker"], ["podman"], or on Windows
 * ["wsl.exe", "-d", "StudentIDE", "--", "podman"]. Docker and Podman share
 * every subcommand used here, so one driver serves both, and no native
 * modules or socket clients are needed.
 */

import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";

export type EngineKind = "wsl-podman" | "lima-podman" | "podman" | "docker";

export interface EngineInfo {
  kind: EngineKind;
  /** argv prefix, e.g. ["podman"] or ["wsl.exe", "-d", "StudentIDE", "--", "podman"] */
  cli: string[];
  /** unix socket path (macOS/Linux only); passed as DOCKER_HOST / CONTAINER_HOST */
  dockerHost?: string;
  /** extra environment for the cli (LIMA_HOME, XDG_CONFIG_HOME, WSL_UTF8…), set by the installer */
  env?: Record<string, string>;
}

export interface ExecResult {
  code: number | null;
  stdout: Buffer;
  stderr: string;
  timedOut: boolean;
  durationMs: number;
}

export interface CallOptions {
  stdin?: string | Buffer;
  timeoutMs?: number;
  /** stop reading stdout after this many bytes (the process keeps running to its end) */
  maxStdout?: number;
}

export class EngineError extends Error {
  readonly code: number | null;
  readonly stderr: string;
  constructor(message: string, code: number | null, stderr: string) {
    super(message);
    this.name = "EngineError";
    this.code = code;
    this.stderr = stderr;
  }
}

export const isPodman = (e: EngineInfo): boolean => e.kind !== "docker";

/** Spawns engine commands. Tests swap `spawnFn` for a fake. */
export class Engine {
  readonly info: EngineInfo;
  spawnFn: typeof spawn;

  constructor(info: EngineInfo, spawnFn: typeof spawn = spawn) {
    if (!info.cli.length) throw new Error("engine.cli is empty");
    this.info = info;
    this.spawnFn = spawnFn;
  }

  get podman(): boolean {
    return isPodman(this.info);
  }

  private env(): NodeJS.ProcessEnv {
    const env = { ...process.env, ...this.info.env };
    if (this.info.dockerHost) {
      const url = this.info.dockerHost.includes("://") ? this.info.dockerHost : `unix://${this.info.dockerHost}`;
      env.DOCKER_HOST = url;
      env.CONTAINER_HOST = url;
    }
    return env;
  }

  /** Start a long-lived engine process (terminals, log followers). */
  spawn(args: string[]): ChildProcessWithoutNullStreams {
    const [cmd, ...pre] = this.info.cli as [string, ...string[]];
    return this.spawnFn(cmd, [...pre, ...args], { env: this.env(), windowsHide: true }) as ChildProcessWithoutNullStreams;
  }

  /** Run one engine command to completion. Never throws for a non-zero exit. */
  call(args: string[], opts: CallOptions = {}): Promise<ExecResult> {
    const started = performance.now();
    return new Promise((resolve) => {
      let child: ChildProcessWithoutNullStreams;
      try {
        child = this.spawn(args);
      } catch (e) {
        resolve({ code: null, stdout: Buffer.alloc(0), stderr: String(e), timedOut: false, durationMs: 0 });
        return;
      }
      const out: Buffer[] = [];
      let outLen = 0;
      let err = "";
      let timedOut = false;
      const max = opts.maxStdout ?? 64 * 1024 * 1024;
      child.stdout.on("data", (b: Buffer) => {
        if (outLen < max) out.push(b.subarray(0, max - outLen));
        outLen += b.length;
      });
      child.stderr.on("data", (b: Buffer) => {
        if (err.length < 64 * 1024) err += b.toString("utf8");
      });
      const timer = opts.timeoutMs
        ? setTimeout(() => {
            timedOut = true;
            child.kill("SIGKILL");
          }, opts.timeoutMs)
        : undefined;
      let settled = false;
      const finish = (code: number | null) => {
        if (settled) return;
        settled = true;
        if (timer) clearTimeout(timer);
        resolve({ code, stdout: Buffer.concat(out), stderr: err, timedOut, durationMs: performance.now() - started });
      };
      child.on("error", (e: NodeJS.ErrnoException) => {
        err += String(e);
        if (e.code === "ENOENT") finish(null); // the program is not installed: no "close" follows reliably
      });
      child.on("close", (code) => finish(code));
      child.stdin.on("error", () => {}); // process may exit before reading stdin
      if (opts.stdin !== undefined) child.stdin.end(opts.stdin);
      else child.stdin.end();
    });
  }

  /** call() that throws EngineError on a non-zero exit; returns stdout as text. */
  async ok(args: string[], opts: CallOptions = {}): Promise<string> {
    const r = await this.call(args, opts);
    if (r.code !== 0) {
      const msg = r.timedOut ? `${args[0]} timed out` : (r.stderr.trim().split("\n").pop() ?? `${args[0]} failed`);
      throw new EngineError(msg, r.code, r.stderr);
    }
    return r.stdout.toString("utf8");
  }

  async json<T>(args: string[], opts: CallOptions = {}): Promise<T> {
    return JSON.parse(await this.ok(args, opts)) as T;
  }

  /** True when the container exists (any state). */
  async exists(kind: "container" | "volume" | "network" | "image", name: string): Promise<boolean> {
    const sub = kind === "image" ? ["image", "inspect"] : [kind, "inspect"];
    const r = await this.call([...sub, name], { timeoutMs: 30_000 });
    return r.code === 0;
  }
}
