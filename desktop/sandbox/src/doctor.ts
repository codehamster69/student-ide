/**
 * Setup check ("Lab doctor"): can this machine run Sandbox Labs, and if not, why.
 *
 * Every check says in plain words what it found and, when it fails, what to
 * do. There is no cloud fallback for students (plan 3.2), so a failed check
 * ends with "or move to a machine that works; your files follow you". Used
 * by the installer after setting up the engine and by the app before a lab.
 *
 *   setupCheck(engine, opts?) -> { ok, checks: [{ id, ok, message, fix?, severity }] }
 *   CLI: node bin/sandbox-doctor.mjs --engine engine.json [--image ref]
 */

import { freemem, totalmem, arch as osArch, platform as osPlatform, tmpdir } from "node:os";
import { statfs } from "node:fs/promises";
import { spawn } from "node:child_process";
import { Engine, type EngineInfo } from "./engine.ts";
import { PROXY_IMAGE, newId, pullImage } from "./instance.ts";

export type Severity = "error" | "warning" | "info";

export interface Check {
  id: string;
  ok: boolean;
  message: string;
  fix?: string;
  severity: Severity;
}

export interface CheckReport {
  ok: boolean;
  checks: Check[];
}

export interface HostFacts {
  platform: NodeJS.Platform;
  arch: string;
  totalMemBytes: number;
  freeMemBytes: number;
  freeDiskBytes: number | null;
}

export interface CheckOptions {
  /** image to try a container with; default the proxy image (always pulled by the installer) */
  image?: string;
  /** directory whose disk holds the engine's data (default: the OS temp dir's disk) */
  dataDir?: string;
  /** skip the slower container checks (only engine + host) */
  quick?: boolean;
  host?: Partial<HostFacts>;
  spawnFn?: typeof spawn;
}

const GB = 1024 ** 3;
const MOVE = "If it still fails, use another machine that passes this check: your lab files are saved on the server and follow you.";

/** Known engine error texts → what they mean for a student. */
export function explain(stderr: string, kind: EngineInfo["kind"]): { message: string; fix: string } | null {
  const s = stderr.toLowerCase();
  if (/0x80370102|virtual machine platform|hcs_e_hyperv_not_installed|virtualization.*(disabled|not enabled)|vt-x|svm/.test(s)) {
    return {
      message: "Hardware virtualization is switched off in this PC's BIOS/UEFI, so the Linux engine cannot start.",
      fix: "Restart into the BIOS/UEFI setup and enable Intel VT-x or AMD-V (SVM), or ask IT to do it once for the lab room.",
    };
  }
  if (/wsl.*(not installed|is not enabled)|wsl_e_wsl_optional_component_required|there is no distribution with the supplied name/.test(s)) {
    return {
      message: "Windows Subsystem for Linux (WSL2) or the StudentIDE engine is not set up on this PC.",
      fix: "Run the Student IDE installer again. Turning on WSL2 needs admin rights once; ask IT if you do not have them.",
    };
  }
  if (/cannot connect to the docker daemon|is the docker daemon running|docker_engine.*(cannot find|no such)|error during connect/.test(s)) {
    return { message: "Docker is installed but not running.", fix: "Start Docker Desktop (or the Docker service) and run the check again." };
  }
  if (/cannot connect to podman|unable to connect to podman|podman machine|connection refused/.test(s)) {
    return {
      message: kind === "podman" ? "Podman is installed but its service is not reachable." : "The Student IDE engine is not running.",
      fix: kind === "podman" ? "Run `podman machine start` (macOS/Windows) or `systemctl --user start podman.socket`, then check again." : "Quit and reopen Student IDE; it restarts its engine. If that fails, run the installer again.",
    };
  }
  if (/permission denied.*docker\.sock|got permission denied/.test(s)) {
    return { message: "Your user may not use Docker on this machine.", fix: "Ask the machine's admin to add you to the docker group, or use the Student IDE installer, which brings its own engine." };
  }
  if (/no space left on device/.test(s)) {
    return { message: "The disk is full.", fix: "Free at least 10 GB, then check again." };
  }
  if (/(dial tcp|i\/o timeout|tls handshake|no such host|temporary failure in name resolution|toomanyrequests)/.test(s)) {
    return { message: "Lab images could not be downloaded: the network or the registry is not reachable.", fix: "Check the internet connection (campus Wi-Fi may block it) and try again." };
  }
  return null;
}

function versionOk(kind: EngineInfo["kind"], v: string): boolean {
  const [maj = 0, min = 0] = v.split(/[.+-]/).map((x) => Number(x) || 0);
  return kind === "docker" ? maj > 20 || (maj === 20 && min >= 10) : maj >= 4;
}

async function hostFacts(o: CheckOptions): Promise<HostFacts> {
  let freeDisk: number | null = null;
  try {
    const st = await statfs(o.dataDir ?? tmpdir());
    freeDisk = st.bavail * st.bsize;
  } catch {
    /* unknown */
  }
  return { platform: osPlatform(), arch: osArch(), totalMemBytes: totalmem(), freeMemBytes: freemem(), freeDiskBytes: freeDisk, ...o.host };
}

export async function setupCheck(info: EngineInfo, opts: CheckOptions = {}): Promise<CheckReport> {
  const checks: Check[] = [];
  const add = (c: Omit<Check, "severity"> & { severity?: Severity }) => checks.push({ severity: c.ok ? "info" : "error", ...c });
  const done = (): CheckReport => ({ ok: checks.every((c) => c.ok || c.severity !== "error"), checks });

  // --- host ---
  const h = await hostFacts(opts);
  add({
    id: "host.arch", ok: h.arch === "x64" || h.arch === "arm64",
    message: h.arch === "x64" || h.arch === "arm64" ? `Processor: ${h.arch}.` : `This processor (${h.arch}) has no lab images.`,
    fix: "Use a 64-bit Intel/AMD or ARM machine.",
  });
  const memGb = h.totalMemBytes / GB;
  add({
    id: "host.memory", ok: memGb >= 6, severity: memGb < 3.5 ? "error" : "warning",
    message: memGb >= 6 ? `Memory: ${memGb.toFixed(1)} GB.` : `Only ${memGb.toFixed(1)} GB of memory; a lab needs about 2 GB on top of the system.`,
    fix: memGb < 3.5 ? `This machine is too small for Sandbox Labs. ${MOVE}` : "Close other programs (especially browsers) while a lab runs.",
  });
  if (h.freeDiskBytes !== null) {
    const d = h.freeDiskBytes / GB;
    add({
      id: "host.disk", ok: d >= 12, severity: d < 4 ? "error" : "warning",
      message: d >= 12 ? `Free disk: ${d.toFixed(0)} GB.` : `Only ${d.toFixed(1)} GB of free disk; a subject's environment and files need up to 10 GB.`,
      fix: "Free some disk space, then check again.",
    });
  }

  // --- engine ---
  const engine = new Engine(info, opts.spawnFn);
  const ver = await engine.call(["version", "--format", "json"], { timeoutMs: 30_000 });
  if (/ENOENT/.test(ver.stderr) && !ver.stdout.length) {
    add({ id: "engine.cli", ok: false, message: `The container engine program (${info.cli[0]}) was not found.`, fix: `Run the Student IDE installer, which sets up its own engine. ${MOVE}` });
    return done();
  }
  add({ id: "engine.cli", ok: true, message: `Engine: ${info.kind}.` });
  let server: { version?: string; os?: string } = {};
  try {
    const j = JSON.parse(ver.stdout.toString("utf8"));
    // docker: {Client, Server:{Version,Os}}; podman: {Client, Server?:{Version,OsArch}}
    server = { version: j.Server?.Version ?? (info.kind !== "docker" ? j.Client?.Version : undefined), os: j.Server?.Os ?? j.Server?.OsArch };
  } catch {
    /* handled below */
  }
  if (ver.code !== 0 || !server.version) {
    const why = explain(ver.stderr, info.kind);
    add({ id: "engine.running", ok: false, message: why?.message ?? "The container engine did not answer.", fix: `${why?.fix ?? "Quit and reopen Student IDE, or run the installer again."} ${MOVE}` });
    return done();
  }
  add({ id: "engine.running", ok: true, message: `The engine answers (version ${server.version}).` });
  add({
    id: "engine.version", ok: versionOk(info.kind, server.version), severity: "warning",
    message: versionOk(info.kind, server.version) ? "Engine version is recent enough." : `Engine version ${server.version} is old; some lab features may fail.`,
    fix: info.kind === "docker" ? "Update Docker to 20.10 or newer." : "Update Podman to 4.0 or newer (the installer does this).",
  });
  if (server.os && !/linux/i.test(server.os)) {
    add({ id: "engine.linux", ok: false, message: `The engine runs ${server.os} containers; labs need Linux containers.`, fix: "In Docker Desktop, switch to Linux containers." });
    return done();
  }

  const inf = await engine.call(["info", "--format", "json"], { timeoutMs: 30_000 });
  try {
    const j = JSON.parse(inf.stdout.toString("utf8"));
    const cg = String(j.CgroupVersion ?? j.host?.cgroupVersion ?? "");
    const rootless = Boolean(j.host?.security?.rootless) || (j.SecurityOptions ?? []).some((x: string) => /rootless/.test(x));
    const limited = !(rootless && /^(v?1)$/.test(cg));
    add({
      id: "engine.limits", ok: limited, severity: "warning",
      message: limited ? "CPU and memory limits are available." : "This engine cannot limit CPU and memory (rootless on cgroup v1); labs still run.",
      fix: "Labs run without limits here; a heavy program can slow the whole machine. Updating the OS (cgroup v2) fixes it.",
    });
  } catch {
    /* info is optional */
  }
  if (opts.quick) return done();

  // --- containers ---
  const image = opts.image ?? PROXY_IMAGE;
  if (!(await engine.exists("image", image))) {
    try {
      await pullImage(engine, image);
      add({ id: "engine.pull", ok: true, message: "Lab images can be downloaded." });
    } catch (e: any) {
      const why = explain(String(e?.stderr ?? e), info.kind);
      add({ id: "engine.pull", ok: false, message: why?.message ?? `Could not download ${image}.`, fix: why?.fix ?? "Check the internet connection and try again." });
      return done();
    }
  }
  const run = await engine.call(["run", "--rm", "--network", "none", "--entrypoint", "true", image], { timeoutMs: 120_000 });
  if (run.code !== 0) {
    const why = explain(run.stderr, info.kind);
    add({ id: "engine.run", ok: false, message: why?.message ?? "A test container did not start.", fix: `${why?.fix ?? "Restart the machine and check again."} ${MOVE}` });
    return done();
  }
  add({ id: "engine.run", ok: true, message: "A test container starts and stops." });

  const lim = await engine.call(["run", "--rm", "--network", "none", "--cpus", "0.5", "--memory", "64m", "--pids-limit", "32", "--cap-drop", "ALL", "--entrypoint", "true", image], { timeoutMs: 120_000 });
  if (lim.code !== 0 && !checks.some((c) => c.id === "engine.limits" && !c.ok)) {
    add({ id: "engine.limits", ok: false, severity: "warning", message: "The engine refused resource limits; labs will run without them.", fix: "Update the engine, or ask IT to enable cgroup v2." });
  }

  const vol = `sid-check-${newId()}`;
  const v = await engine.call(["volume", "create", vol], { timeoutMs: 60_000 });
  await engine.call(["volume", "rm", "-f", vol], { timeoutMs: 60_000 });
  add({ id: "engine.volume", ok: v.code === 0, message: v.code === 0 ? "Lab files can be stored." : "The engine cannot create storage for lab files.", fix: explain(v.stderr, info.kind)?.fix ?? "Free disk space or reinstall the engine." });

  const net = `sid-check-${newId()}`;
  const n = await engine.call(["network", "create", "--internal", net], { timeoutMs: 60_000 });
  await engine.call(["network", "rm", net], { timeoutMs: 60_000 });
  add({
    id: "engine.network", ok: n.code === 0, severity: "warning",
    message: n.code === 0 ? "Private lab networks work (needed for registries-only labs)." : "Private lab networks are not available; registries-only labs cannot install packages here.",
    fix: "Update the engine (Podman 4+ with netavark, or Docker 20.10+).",
  });
  return done();
}
