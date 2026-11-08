/**
 * The one-click flow: check the PC, set up the bundled engine for this OS
 * (or reuse a Docker/Podman the user already has), pull lab images, run the
 * setup check, and save engine.json. Safe to run again at any point.
 */
import fs from 'node:fs';
import path from 'node:path';
import { errors, SetupError } from './errors';
import { Host, realHost } from './host';
import { builtinCheck, pullImages, engineRun } from './images';
import { setupLinux } from './linux';
import { setupMacos } from './macos';
import { setupWindows } from './windows';
import type { CheckResult, EngineInfo, ImageRef, Progress, SetupCheck, Step } from './types';

export const ENGINE_FILE = 'engine.json';
const GB = 1024 ** 3;
/** Engine disk (~2 GB) + a few lab images + headroom. */
export const NEED_DISK_GB = 10;
export const WARN_RAM_GB = 6;

export interface SetupOptions {
  /** Electron's app.getPath('userData'). */
  dataDir: string;
  /** Bundled assets; defaults to <resources>/installer when packaged. */
  assetsDir?: string;
  /** Images to pull now (e.g. images.json + the student's subject images). Empty is fine: pull later. */
  images?: ImageRef[];
  /** No prompts: fail with NEEDS_ADMIN instead of asking (lab-room scripts). */
  silent?: boolean;
  /** 'bundled' (default) sets up our engine; 'existing' prefers a Docker/Podman already installed. */
  prefer?: 'bundled' | 'existing';
  onProgress?: (p: Progress) => void;
  /** desktop/sandbox's setupCheck; the built-in subset is used when absent. */
  check?: SetupCheck;
  /** Tests only. */
  host?: Host;
}

export interface SetupResult {
  engine: EngineInfo;
  check: CheckResult;
  /** Non-fatal notes for the student, e.g. low memory. */
  warnings: string[];
}

/** Packaged: <resources>/installer (electron-builder extraResources). Dev: this package's assets/ folder. */
export function defaultAssets(): string {
  const res = (process as NodeJS.Process & { resourcesPath?: string }).resourcesPath;
  const packaged = res && fs.existsSync(path.join(res, 'installer')) ? path.join(res, 'installer') : undefined;
  return packaged ?? path.join(__dirname, '..', 'assets');
}

/** Fast: the saved engine, or null if setup has not finished on this machine. */
export function detectEngine(dataDir: string, host?: Host): EngineInfo | null {
  const h = host ?? realHost(dataDir, '');
  const raw = h.readFile(path.join(dataDir, ENGINE_FILE));
  if (!raw) return null;
  try {
    const e = JSON.parse(raw) as EngineInfo;
    return Array.isArray(e.cli) && e.cli.length ? e : null;
  } catch {
    return null;
  }
}

/** A Docker or Podman the user already runs, if it answers. */
export async function existingEngine(host: Host): Promise<EngineInfo | null> {
  for (const [kind, cmd] of [['docker', 'docker'], ['podman', 'podman']] as const) {
    const r = await host.run(cmd, ['version', '--format', '{{.Server.Version}}'], { timeoutMs: 20_000 });
    const version = r.stdout.trim();
    if (r.code === 0 && version) return { kind, cli: [cmd], bundled: false, version, installedAt: new Date().toISOString() };
  }
  return null;
}

export async function runSetup(opts: SetupOptions): Promise<SetupResult> {
  const host = opts.host ?? realHost(opts.dataDir, opts.assetsDir ?? defaultAssets());
  const emit = (step: Step) => (percent: number, message: string) => opts.onProgress?.({ step, percent, message });
  const warnings: string[] = [];

  // 1. Checking your PC
  const sayCheck = emit('check');
  sayCheck(0, 'Checking your PC');
  if (!['win32', 'darwin', 'linux'].includes(host.platform)) throw errors.unsupportedOs(host.platform);
  const freeGb = (await host.freeDiskBytes()) / GB;
  if (freeGb < NEED_DISK_GB) throw errors.lowDisk(freeGb, NEED_DISK_GB);
  const ramGb = host.totalMemBytes / GB;
  if (ramGb < WARN_RAM_GB) {
    warnings.push(
      `This computer has ${Math.round(ramGb)} GB of memory. Labs will work but may feel slow; close other apps while you work.`,
    );
  }
  sayCheck(100, 'Your PC is ready');

  // 2. Setting up the Linux engine
  const sayEngine = emit('engine');
  let engine = opts.prefer === 'existing' ? await existingEngine(host) : null;
  if (!engine) {
    try {
      engine =
        host.platform === 'win32'
          ? await setupWindows(host, !!opts.silent, sayEngine)
          : host.platform === 'darwin'
            ? await setupMacos(host, sayEngine)
            : await setupLinux(host, !!opts.silent, sayEngine);
    } catch (e) {
      // Our engine could not be set up for a reason the student cannot fix right now
      // (no admin, BIOS): a working Docker/Podman they already have still lets them start.
      if (e instanceof SetupError && !e.needsReboot && (e.needsAdmin || e.code === 'VIRTUALIZATION_OFF')) {
        const fallback = await existingEngine(host);
        if (!fallback) throw e;
        warnings.push(`Using the ${fallback.kind} already installed on this computer.`);
        engine = fallback;
      } else throw e;
    }
  }
  sayEngine(100, 'Linux engine ready');

  // 3. Downloading your subjects
  const images = opts.images ?? [];
  await pullImages(host, engine, images, emit('images'));

  // 4. Final check
  const sayVerify = emit('verify');
  sayVerify(0, 'Checking everything works');
  const check = opts.check ? await opts.check(engine, images) : await builtinCheck(host, engine, images);
  if (!check.ok) {
    const failed = check.checks.filter((c) => !c.ok);
    throw errors.checkFailed(
      failed.map((c) => c.id),
      failed.map((c) => `${c.id}: ${c.message}${c.fix ? ` (${c.fix})` : ''}`).join('\n'),
    );
  }
  host.writeFile(path.join(host.dataDir, ENGINE_FILE), JSON.stringify(engine, null, 2));
  sayVerify(100, 'All set');
  return { engine, check, warnings };
}

/** Removes the bundled engine and its disk image (uninstall, or "Reset engine" in the Lab doctor). */
export async function removeEngine(dataDir: string, host?: Host): Promise<void> {
  const h = host ?? realHost(dataDir, defaultAssets());
  const engine = detectEngine(dataDir, h);
  if (engine?.kind === 'wsl-podman') await h.run('wsl.exe', ['--unregister', 'StudentIDE'], { env: { WSL_UTF8: '1' } });
  if (engine?.kind === 'lima-podman') {
    await h.run(engine.cli[0], ['delete', '--force', 'studentide'], { env: engine.env });
  }
  if (engine?.bundled && engine.kind === 'podman' && engine.cli[0] !== 'podman') {
    await engineRun(h, engine, ['system', 'reset', '--force']);
  }
  h.writeFile(path.join(dataDir, ENGINE_FILE), '');
}

/** Quick health ping for a saved engine (Lab doctor, app start). Starts a stopped Lima VM or WSL distro as a side effect. */
export async function engineAlive(engine: EngineInfo, host?: Host): Promise<boolean> {
  const h = host ?? realHost('', '');
  return (await engineRun(h, engine, ['version', '--format', '{{.Client.Version}}'], 120_000)).code === 0;
}
