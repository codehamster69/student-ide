/**
 * Windows 10/11: turn on WSL2 if needed (the only admin step), then import our
 * own small WSL distro "StudentIDE" with rootless Podman inside. No Docker
 * Desktop. Every step checks first, so running setup again (after a reboot,
 * or after a failure) carries on where it stopped.
 */
import path from 'node:path';
import { errors } from './errors';
import { logOf } from './exec';
import type { Host } from './host';
import type { EngineInfo } from './types';

export const DISTRO = 'StudentIDE';
/** Wrapper inside the distro that sets XDG_RUNTIME_DIR and execs podman (see assets/wsl/). */
const WRAPPER = '/usr/local/bin/sid-podman';
const WSL = 'wsl.exe';
const UTF8 = { WSL_UTF8: '1' };
const PS = 'powershell.exe';
const psArgs = (script: string) => ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script];

export const engineCli = () => [WSL, '-d', DISTRO, '--user', 'student', '--', WRAPPER];

export function windowsBuild(release: string): number {
  return Number(release.split('.')[2] ?? 0);
}

/** Virtualization is usable if firmware has it on, or a hypervisor is already running (which hides the firmware flag). */
export async function virtualizationOn(host: Host): Promise<boolean> {
  const r = await host.run(
    PS,
    psArgs(
      '$p=(Get-CimInstance Win32_Processor | Select-Object -First 1).VirtualizationFirmwareEnabled;' +
        '$h=(Get-CimInstance Win32_ComputerSystem).HypervisorPresent;' +
        'Write-Output "$p $h"',
    ),
  );
  // Only "False False" is a clear no; blank values (some VMs) mean we cannot tell, so let WSL report it later.
  return !(r.code === 0 && /^\s*false\s+false\s*$/i.test(r.stdout));
}

export async function isAdmin(host: Host): Promise<boolean> {
  const r = await host.run(
    PS,
    psArgs("([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators')"),
  );
  return /true/i.test(r.stdout);
}

/** WSL2 is ready when `wsl --status` succeeds (store WSL installed and the platform feature on). */
export async function wslReady(host: Host): Promise<boolean> {
  const r = await host.run(WSL, ['--status'], { env: UTF8, timeoutMs: 60_000 });
  return r.code === 0 && !/not (installed|enabled)|0x8007019e|0x80370102/i.test(logOf(r));
}

export async function distroInstalled(host: Host): Promise<boolean> {
  const r = await host.run(WSL, ['--list', '--quiet'], { env: UTF8 });
  return r.code === 0 && r.stdout.split(/\r?\n/).some((l) => l.trim() === DISTRO);
}

/**
 * Turn on WSL2. Runs elevated: through a UAC prompt when not already admin.
 * Returns 'reboot' when Windows needs a restart before WSL works.
 */
export async function enableWsl(host: Host, silent: boolean): Promise<'ready' | 'reboot'> {
  const admin = await isAdmin(host);
  if (!admin && silent) {
    throw errors.needsAdmin('Setup has to turn on the Windows Subsystem for Linux (WSL2).');
  }
  // Newer WSL: one command installs the store WSL and turns on the platform feature.
  const install = admin
    ? await host.run(WSL, ['--install', '--no-distribution'], { env: UTF8, timeoutMs: 15 * 60_000 })
    : await host.run(
        PS,
        psArgs(
          "try { $p = Start-Process -FilePath wsl.exe -ArgumentList '--install','--no-distribution' " +
            '-Verb RunAs -Wait -PassThru -WindowStyle Hidden; exit $p.ExitCode } catch { exit 1223 }',
        ),
        { timeoutMs: 15 * 60_000 },
      );
  if (install.code === 1223 || /canceled by the user|1223/i.test(logOf(install))) {
    throw errors.needsAdmin('Setup has to turn on the Windows Subsystem for Linux (WSL2).', logOf(install));
  }
  if (install.code !== 0 && /--no-distribution|invalid command line|unrecognized/i.test(logOf(install))) {
    // Inbox WSL on older Windows 10 lacks --no-distribution: turn the two features on with DISM.
    if (!admin) throw errors.needsAdmin('Setup has to turn on two Windows features for WSL2.', logOf(install));
    for (const feature of ['Microsoft-Windows-Subsystem-Linux', 'VirtualMachinePlatform']) {
      const r = await host.run('dism.exe', ['/online', '/enable-feature', `/featurename:${feature}`, '/all', '/norestart']);
      // 3010 = success, restart required
      if (r.code !== 0 && r.code !== 3010) throw errors.engineInstallFailed(`turning on ${feature}`, logOf(r));
    }
    return 'reboot';
  }
  if (install.code !== 0) throw errors.engineInstallFailed('turning on WSL2', logOf(install));
  return (await wslReady(host)) ? 'ready' : 'reboot';
}

/** Relaunch the app once at next sign-in so setup resumes after the restart. Per-user key: no admin. */
export async function scheduleResume(host: Host): Promise<void> {
  await host.run('reg.exe', [
    'add',
    'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce',
    '/v',
    'StudentIDESetup',
    '/t',
    'REG_SZ',
    '/d',
    `"${host.appExe}" --resume-setup`,
    '/f',
  ]);
}

export async function importDistro(host: Host): Promise<void> {
  const tar = path.join(host.assetsDir, 'wsl', 'studentide-rootfs.tar.gz');
  if (!host.exists(tar)) throw errors.engineInstallFailed('looking for the bundled Linux engine (file missing)', tar);
  const dir = path.join(host.dataDir, 'engine', 'wsl');
  const r = await host.run(WSL, ['--import', DISTRO, dir, tar, '--version', '2'], { env: UTF8, timeoutMs: 10 * 60_000 });
  if (r.code !== 0) {
    if (/HCS_E_HYPERV_NOT_INSTALLED|0x80370102|virtuali[sz]ation/i.test(logOf(r))) throw errors.virtualizationOff('win32');
    throw errors.engineInstallFailed('unpacking the Linux engine', logOf(r));
  }
}

export async function podmanVersion(host: Host): Promise<string | undefined> {
  const [cmd, ...args] = engineCli();
  const r = await host.run(cmd, [...args, 'version', '--format', '{{.Client.Version}}'], { env: UTF8, timeoutMs: 120_000 });
  return r.code === 0 ? r.stdout.trim() : undefined;
}

export async function setupWindows(host: Host, silent: boolean, say: (pct: number, msg: string) => void): Promise<EngineInfo> {
  const build = windowsBuild(host.release);
  if (build < 19041) throw errors.oldWindows(build);

  say(5, 'Checking virtualization');
  if (!(await virtualizationOn(host))) throw errors.virtualizationOff('win32');

  say(10, 'Checking the Windows Subsystem for Linux');
  if (!(await wslReady(host))) {
    say(15, 'Turning on WSL2 (Windows may ask for permission)');
    if ((await enableWsl(host, silent)) === 'reboot') {
      await scheduleResume(host);
      throw errors.needsReboot();
    }
  }

  if (!(await distroInstalled(host))) {
    say(40, 'Unpacking the Linux engine');
    await importDistro(host);
  }

  say(80, 'Starting the Linux engine');
  const version = await podmanVersion(host);
  if (!version) throw errors.engineNotResponding();
  return { kind: 'wsl-podman', cli: engineCli(), env: UTF8, bundled: true, version, installedAt: new Date().toISOString() };
}
