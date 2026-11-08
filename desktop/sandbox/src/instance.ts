/**
 * One Linux instance per (student, subject): create, start, stop, reset, limits, files.
 *
 * The instance is a long-lived container `sid-<student>-<subject>` with the
 * student's home on a named volume `sidv-…`, kept for the semester (plan
 * section 3.3/3.5). It is isolated from the host but open inside: sudo and a
 * writable root, never --privileged, no host mounts, only listed capabilities,
 * and CPU, memory and pids limits. Network modes:
 *   off         --network none
 *   registries  an --internal network shared only with a proxy sidecar that
 *               allows package registries and logs host names (net_conn)
 *   open        the engine's default network
 */

import { createHash, randomBytes } from "node:crypto";
import { Engine, EngineError, type ExecResult } from "./engine.ts";
import { installScript } from "./hooks.ts";
import { REGISTRY_HOSTS } from "./registries.ts";
import { shq } from "./recipe.ts";

export type NetworkMode = "off" | "registries" | "open";

export interface Limits {
  cpus: number;
  memoryMb: number;
  diskGb: number;
  pids: number;
}

export const DEFAULT_LIMITS: Limits = { cpus: 2, memoryMb: 2048, diskGb: 10, pids: 512 };

export interface InstanceSpec {
  studentId: string;
  subjectId: string;
  image: string;            // ref; pulled as image@digest when digest is set
  digest?: string | null;
  limits?: Partial<Limits>;
  network: NetworkMode;
  hostname?: string;
  /** gdb/strace need ptrace (default on); networking labs need NET_ADMIN/NET_RAW */
  ptrace?: boolean;
  netAdmin?: boolean;
  /** override names from the lab definition ("sid-{student}-…"); {student} is filled in */
  name?: string;
  volume?: string;
  proxyImage?: string;
}

export const USER = "student";
export const HOME = "/home/student";
export const PROXY_IMAGE = "ghcr.io/codehamster69/studentide-sidproxy:1";
export const PROXY_PORT = 8888;
export const LABEL = "studentide.instance";

// Docker's default set minus MKNOD and NET_RAW, plus ptrace for debuggers.
const BASE_CAPS = ["CHOWN", "DAC_OVERRIDE", "FOWNER", "FSETID", "KILL", "SETGID", "SETUID", "SETPCAP", "NET_BIND_SERVICE", "SYS_CHROOT", "AUDIT_WRITE"];

export const slug = (s: string): string => s.toLowerCase().replace(/[^a-z0-9_.-]+/g, "-").replace(/^[-.]+|-+$/g, "").slice(0, 60) || "x";

export interface InstanceStatus {
  state: "missing" | "created" | "running" | "paused" | "exited" | "other";
  image?: string;
  startedAt?: string;
  limitsEnforced: boolean;
}

export interface InstanceStats {
  cpuPercent: number | null;
  memoryBytes: number | null;
  memoryLimitBytes: number | null;
  pids: number | null;
  diskUsedBytes: number | null;
  diskLimitBytes: number;
}

export interface FileEntry {
  path: string; // relative to the listed directory
  type: "file" | "dir" | "link" | "other";
  size: number;
  mtimeMs: number;
}

export class Instance {
  readonly engine: Engine;
  readonly spec: InstanceSpec;
  readonly name: string;
  readonly volume: string;
  readonly network: string;
  readonly proxy: string;
  readonly limits: Limits;
  limitsEnforced = true;
  private lastActivity = Date.now();

  constructor(engine: Engine, spec: InstanceSpec) {
    this.engine = engine;
    this.spec = spec;
    const student = slug(spec.studentId);
    const subject = slug(spec.subjectId);
    this.name = slug((spec.name ?? `sid-{student}-${subject}`).replace("{student}", student));
    this.volume = slug((spec.volume ?? `sidv-{student}-${subject}`).replace("{student}", student));
    this.network = `sidnet-${this.name}`.slice(0, 63);
    this.proxy = `sidproxy-${this.name}`.slice(0, 63);
    const given = Object.fromEntries(Object.entries(spec.limits ?? {}).filter(([, v]) => typeof v === "number" && v > 0));
    this.limits = { ...DEFAULT_LIMITS, ...given };
  }

  /** RFC 1123 label: lower-case letters, digits and hyphens */
  get hostname(): string {
    return slug(this.spec.hostname ?? this.spec.subjectId).replace(/[_.]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 63) || "lab";
  }

  get imageRef(): string {
    if (!this.spec.digest) return this.spec.image;
    const repo = this.spec.image.replace(/:[^/:]+$/, "");
    return `${repo}@${this.spec.digest}`;
  }

  /** Hash of everything that needs a new container when it changes (not the volume). */
  get specHash(): string {
    const s = this.spec;
    return createHash("sha256")
      .update(JSON.stringify([this.imageRef, this.limits, s.network, s.hostname ?? "", s.ptrace ?? true, s.netAdmin ?? false]))
      .digest("hex")
      .slice(0, 16);
  }

  touch(): void {
    this.lastActivity = Date.now();
  }

  idleMs(): number {
    return Date.now() - this.lastActivity;
  }

  createArgs(withLimits = true): string[] {
    const s = this.spec;
    const caps = [...BASE_CAPS];
    if (s.ptrace ?? true) caps.push("SYS_PTRACE");
    if (s.netAdmin) caps.push("NET_ADMIN", "NET_RAW");
    const args = [
      "create", "--name", this.name, "--init",
      "--hostname", this.hostname, "--add-host", `${this.hostname}:127.0.0.1`, // sudo resolves its own host name
      "--user", USER, "--workdir", HOME,
      "--cap-drop", "ALL", ...caps.flatMap((c) => ["--cap-add", c]), // Docker wants one flag per capability
      "--security-opt", "label=disable", // SELinux hosts: the volume is ours alone
      "-v", `${this.volume}:${HOME}`,
      "--label", `${LABEL}=1`,
      "--label", `studentide.subject=${s.subjectId}`,
      "--label", `studentide.spec=${this.specHash}`,
      "--env", "LANG=C.UTF-8",
    ];
    if (withLimits) {
      const mem = `${this.limits.memoryMb}m`;
      args.push("--cpus", String(this.limits.cpus), "--memory", mem, "--memory-swap", mem, "--pids-limit", String(this.limits.pids));
    }
    if (s.network === "off") args.push("--network", "none");
    if (s.network === "registries") {
      const p = `http://sidproxy:${PROXY_PORT}`;
      args.push("--network", this.network);
      for (const k of ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"]) args.push("--env", `${k}=${p}`);
      args.push("--env", "no_proxy=localhost,127.0.0.1", "--env", "NO_PROXY=localhost,127.0.0.1");
    }
    args.push(this.imageRef, "sleep", "infinity");
    return args;
  }

  async status(): Promise<InstanceStatus> {
    const r = await this.engine.call(["container", "inspect", this.name], { timeoutMs: 30_000 });
    if (r.code !== 0) return { state: "missing", limitsEnforced: this.limitsEnforced };
    const info = (JSON.parse(r.stdout.toString("utf8")) as Array<Record<string, any>>)[0] ?? {};
    const st = String(info.State?.Status ?? "other").toLowerCase();
    const state = (["created", "running", "paused", "exited"].includes(st) ? st : st === "stopped" || st === "configured" ? "exited" : "other") as InstanceStatus["state"];
    const mem = Number(info.HostConfig?.Memory ?? 0);
    this.limitsEnforced = mem > 0;
    return { state, image: info.Config?.Image, startedAt: info.State?.StartedAt, limitsEnforced: this.limitsEnforced };
  }

  private async specOf(): Promise<string | null> {
    const r = await this.engine.call(["container", "inspect", "--format", "{{index .Config.Labels \"studentide.spec\"}}", this.name], { timeoutMs: 30_000 });
    return r.code === 0 ? r.stdout.toString("utf8").trim() : null;
  }

  /** Pull the image if it is not here yet. onLine gets the engine's progress lines. */
  async ensureImage(onLine?: (line: string) => void): Promise<void> {
    if (await this.engine.exists("image", this.imageRef)) return;
    await pullImage(this.engine, this.imageRef, onLine);
  }

  /**
   * Make sure the container exists with the current spec. Returns "created"
   * for a fresh container (the caller replays the setup recipe), else "kept".
   */
  async ensure(): Promise<"created" | "kept"> {
    const have = await this.specOf();
    if (have === this.specHash) return "kept";
    if (have !== null) await this.engine.call(["rm", "-f", this.name], { timeoutMs: 60_000 });
    if (!(await this.engine.exists("volume", this.volume))) {
      await this.engine.ok(["volume", "create", "--label", `${LABEL}=1`, this.volume], { timeoutMs: 60_000 });
    }
    if (this.spec.network === "registries") await this.ensureProxy();
    try {
      await this.engine.ok(this.createArgs(true), { timeoutMs: 120_000 });
      this.limitsEnforced = true;
    } catch (e) {
      // rootless Podman on cgroup v1 cannot set limits; run without and say so (setup check warns)
      if (!(e instanceof EngineError) || !/cgroup|memory|cpu|pids/i.test(e.stderr)) throw e;
      await this.engine.call(["rm", "-f", this.name], { timeoutMs: 60_000 });
      await this.engine.ok(this.createArgs(false), { timeoutMs: 120_000 });
      this.limitsEnforced = false;
    }
    return "created";
  }

  private async ensureProxy(): Promise<void> {
    const e = this.engine;
    if (!(await e.exists("network", this.network))) {
      await e.ok(["network", "create", "--internal", "--label", `${LABEL}=1`, this.network], { timeoutMs: 60_000 });
    }
    if (!(await e.exists("container", this.proxy))) {
      const img = this.spec.proxyImage ?? PROXY_IMAGE;
      if (!(await e.exists("image", img))) await pullImage(e, img);
      await e.ok([
        "create", "--name", this.proxy, "--label", `${LABEL}=1`, "--label", "studentide.role=proxy",
        "--memory", "64m", "--pids-limit", "64", "--cap-drop", "ALL", "--cap-add", "SETUID", "--cap-add", "SETGID",
        "--env", `SID_ALLOW=${REGISTRY_HOSTS.join(",")}`, img,
      ], { timeoutMs: 120_000 });
      await e.ok(["network", "connect", "--alias", "sidproxy", this.network, this.proxy], { timeoutMs: 60_000 });
    }
    await e.call(["start", this.proxy], { timeoutMs: 60_000 });
  }

  /** Start (creating if needed), stop other instances, install the terminal hooks. */
  async start(opts: { stopOthers?: boolean } = {}): Promise<"created" | "kept"> {
    const made = await this.ensure();
    if (opts.stopOthers ?? true) await this.stopOthers();
    if (this.spec.network === "registries") await this.ensureProxy();
    await this.engine.ok(["start", this.name], { timeoutMs: 120_000 });
    await this.installHooks();
    this.touch();
    return made;
  }

  async installHooks(): Promise<void> {
    let script = installScript();
    if (this.spec.network === "registries") {
      const p = `http://sidproxy:${PROXY_PORT}`;
      // sudo resets the environment; apt reads its own config
      script += `\nprintf 'Acquire::http::Proxy "${p}";\\nAcquire::https::Proxy "${p}";\\n' > /etc/apt/apt.conf.d/95studentide-proxy`;
      script += `\nmkdir -p /etc/sudoers.d && printf 'Defaults env_keep += "http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY"\\n' > /etc/sudoers.d/studentide-proxy && chmod 440 /etc/sudoers.d/studentide-proxy`;
    }
    await this.engine.ok(["exec", "-u", "0", this.name, "sh", "-c", script], { timeoutMs: 60_000 });
  }

  async stop(): Promise<void> {
    await this.engine.call(["stop", "-t", "5", this.name], { timeoutMs: 60_000 });
    if (this.spec.network === "registries") await this.engine.call(["stop", "-t", "2", this.proxy], { timeoutMs: 60_000 });
  }

  /** One running instance at a time (plan 3.5): stop the student's others. */
  async stopOthers(): Promise<string[]> {
    const r = await this.engine.call(["ps", "--filter", `label=${LABEL}=1`, "--format", "{{.Names}}"], { timeoutMs: 30_000 });
    const names = r.stdout.toString("utf8").split(/\s+/).filter((n) => n && n !== this.name && n !== this.proxy && n.startsWith("sid-"));
    for (const n of names) await this.engine.call(["stop", "-t", "5", n], { timeoutMs: 60_000 });
    return names;
  }

  /** "Reset instance": a fresh container from the environment; lab files (the volume) stay. */
  async reset(): Promise<void> {
    await this.engine.call(["rm", "-f", this.name], { timeoutMs: 60_000 });
    await this.start();
  }

  /** Remove everything, including the student's files. Only for uninstall / tests. */
  async destroy(): Promise<void> {
    await this.engine.call(["rm", "-f", this.name, this.proxy], { timeoutMs: 60_000 });
    await this.engine.call(["network", "rm", this.network], { timeoutMs: 60_000 });
    await this.engine.call(["volume", "rm", "-f", this.volume], { timeoutMs: 60_000 });
  }

  async stats(): Promise<InstanceStats> {
    const out: InstanceStats = {
      cpuPercent: null, memoryBytes: null, memoryLimitBytes: null, pids: null, diskUsedBytes: null,
      diskLimitBytes: this.limits.diskGb * 1024 ** 3,
    };
    const r = await this.engine.call(["stats", "--no-stream", "--format", "{{json .}}", this.name], { timeoutMs: 30_000 });
    if (r.code === 0) {
      try {
        const j = JSON.parse(r.stdout.toString("utf8").trim().split("\n")[0] ?? "{}") as Record<string, string>;
        out.cpuPercent = parseFloat(String(j.CPUPerc ?? j.CPU ?? "").replace("%", "")) || 0;
        const [used, lim] = String(j.MemUsage ?? "").split("/").map((x) => parseSize(x.trim()));
        out.memoryBytes = used ?? null;
        out.memoryLimitBytes = lim ?? null;
        out.pids = Number(j.PIDs ?? j.PIDS) || null;
      } catch {
        /* leave nulls */
      }
    }
    const d = await this.exec(["du", "-sxk", HOME], { timeoutMs: 30_000 });
    const kb = Number(d.stdout.toString("utf8").split(/\s/)[0]);
    if (Number.isFinite(kb)) out.diskUsedBytes = kb * 1024;
    return out;
  }

  /** Run a command in the instance (as the student unless user is given). */
  exec(argv: string[], opts: { user?: string; cwd?: string; stdin?: string | Buffer; timeoutMs?: number; env?: Record<string, string>; maxStdout?: number } = {}): Promise<ExecResult> {
    this.touch();
    const args = ["exec", ...(opts.stdin !== undefined ? ["-i"] : []), "-u", opts.user ?? USER];
    if (opts.cwd) args.push("-w", opts.cwd);
    for (const [k, v] of Object.entries(opts.env ?? {})) args.push("-e", `${k}=${v}`);
    args.push(this.name, ...argv);
    return this.engine.call(args, { stdin: opts.stdin, timeoutMs: opts.timeoutMs, maxStdout: opts.maxStdout });
  }

  // ---- files (the editor's file tree) ----

  async listFiles(dir: string, depth = 6): Promise<FileEntry[]> {
    const d = homePath(dir);
    const r = await this.exec(["find", d, "-mindepth", "1", "-maxdepth", String(depth), "-printf", "%y\\t%s\\t%T@\\t%P\\n"], { timeoutMs: 30_000 });
    if (r.code !== 0 && !r.stdout.length) throw new EngineError(`cannot list ${d}`, r.code, r.stderr);
    const kinds: Record<string, FileEntry["type"]> = { f: "file", d: "dir", l: "link" };
    return r.stdout.toString("utf8").split("\n").filter(Boolean).map((line) => {
      const [y, size, mt, ...p] = line.split("\t");
      return { path: p.join("\t"), type: kinds[y ?? ""] ?? "other", size: Number(size), mtimeMs: Math.round(Number(mt) * 1000) };
    }).sort((a, b) => a.path.localeCompare(b.path));
  }

  async readFile(path: string, maxBytes = 2 * 1024 * 1024): Promise<Buffer> {
    const r = await this.exec(["head", "-c", String(maxBytes), homePath(path)], { timeoutMs: 30_000, maxStdout: maxBytes });
    if (r.code !== 0) throw new EngineError(`cannot read ${path}`, r.code, r.stderr);
    return r.stdout;
  }

  async writeFile(path: string, content: string | Buffer, opts: { executable?: boolean } = {}): Promise<void> {
    const p = homePath(path);
    const chmod = opts.executable ? ` && chmod +x ${shq(p)}` : "";
    const r = await this.exec(["sh", "-c", `mkdir -p "$(dirname ${shq(p)})" && cat > ${shq(p)}${chmod}`], { stdin: content, timeoutMs: 30_000 });
    if (r.code !== 0) throw new EngineError(`cannot write ${path}`, r.code, r.stderr);
  }

  /** Write starter files only when the assignment folder does not exist yet (never overwrite work). */
  async seedAssignment(workdir: string, files: Array<{ path: string; content: string; executable?: boolean }>): Promise<boolean> {
    const w = homePath(workdir);
    const probe = await this.exec(["test", "-e", w], { timeoutMs: 30_000 });
    if (probe.code === 0) return false;
    await this.exec(["mkdir", "-p", w], { timeoutMs: 30_000 });
    for (const f of files) await this.writeFile(`${w}/${f.path}`, f.content, { executable: f.executable });
    return true;
  }
}

/** Absolute path inside the student's home; refuses anything that escapes it. */
export function homePath(p: string): string {
  const abs = p.startsWith("/") ? p : `${HOME}/${p}`;
  const parts: string[] = [];
  for (const seg of abs.split("/")) {
    if (!seg || seg === ".") continue;
    if (seg === "..") parts.pop();
    else parts.push(seg);
  }
  const norm = "/" + parts.join("/");
  if (norm !== HOME && !norm.startsWith(`${HOME}/`)) throw new Error(`path outside the student's home: ${p}`);
  return norm;
}

export function parseSize(s: string | undefined): number | undefined {
  if (!s) return undefined;
  const m = /^([\d.]+)\s*([kKmMgGtT]?i?)[bB]?$/.exec(s.trim());
  if (!m) return undefined;
  const n = parseFloat(m[1]!);
  const u = (m[2] ?? "").toLowerCase();
  const pow = { "": 0, k: 1, m: 2, g: 3, t: 4 }[u.replace("i", "")] ?? 0;
  const base = u.endsWith("i") ? 1024 : 1000;
  return Math.round(n * base ** pow);
}

export async function pullImage(engine: Engine, ref: string, onLine?: (line: string) => void): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const p = engine.spawn(["pull", ref]);
    let err = "";
    const lines = (b: Buffer) => b.toString("utf8").split(/\r?\n|\r/).filter(Boolean).forEach((l) => onLine?.(l));
    p.stdout.on("data", lines);
    p.stderr.on("data", (b: Buffer) => {
      err += b.toString("utf8");
      lines(b);
    });
    p.stdin.end();
    p.on("error", reject);
    p.on("close", (code) => (code === 0 ? resolve() : reject(new EngineError(`could not download ${ref}`, code, err))));
  });
}

export const newId = (): string => randomBytes(6).toString("hex");
