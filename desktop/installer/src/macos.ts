/**
 * macOS 13+ (Intel and Apple Silicon): start a small Fedora VM with rootless
 * Podman through the bundled Lima (Apple Virtualization framework). Nothing
 * needs admin rights; the VM lives in the app's userData folder.
 */
import path from 'node:path';
import { errors } from './errors';
import { logOf } from './exec';
import type { Host } from './host';
import type { EngineInfo } from './types';

export const VM = 'studentide';

export const limaPaths = (host: Host) => {
  const limaHome = path.join(host.dataDir, 'engine', 'lima');
  return {
    limactl: path.join(host.assetsDir, 'lima', 'bin', 'limactl'),
    template: path.join(host.assetsDir, 'lima', 'studentide.yaml'),
    limaHome,
    socket: path.join(limaHome, VM, 'sock', 'podman.sock'),
  };
};

/** Darwin kernel 22 = macOS 13 Ventura, the first with what Lima's vz driver needs. */
export const macosMajor = (darwinRelease: string) => Number(darwinRelease.split('.')[0]) - 9;

type VmStatus = 'missing' | 'Running' | 'Stopped' | 'Broken' | string;

export async function vmStatus(host: Host): Promise<VmStatus> {
  const p = limaPaths(host);
  const r = await host.run(p.limactl, ['list', '--json'], { env: { LIMA_HOME: p.limaHome } });
  if (r.code !== 0) return 'missing';
  for (const line of r.stdout.split('\n')) {
    if (!line.trim()) continue;
    try {
      const vm = JSON.parse(line) as { name: string; status: string };
      if (vm.name === VM) return vm.status;
    } catch {
      /* ignore non-JSON lines */
    }
  }
  return 'missing';
}

export async function setupMacos(host: Host, say: (pct: number, msg: string) => void): Promise<EngineInfo> {
  const major = macosMajor(host.release);
  if (major < 13) throw errors.oldMacos(`macOS ${major}`);

  say(5, 'Checking virtualization');
  const hv = await host.run('sysctl', ['-n', 'kern.hv_support']);
  if (hv.code === 0 && hv.stdout.trim() === '0') throw errors.virtualizationOff('darwin');

  const p = limaPaths(host);
  if (!host.exists(p.limactl)) throw errors.engineInstallFailed('looking for the bundled Linux engine (file missing)', p.limactl);
  const env = { LIMA_HOME: p.limaHome };

  const status = await vmStatus(host);
  if (status === 'Broken') {
    say(10, 'Repairing the Linux engine');
    await host.run(p.limactl, ['delete', '--force', VM], { env });
  }
  if (status !== 'Running') {
    const fresh = status === 'missing' || status === 'Broken';
    say(15, fresh ? 'Creating the Linux engine (first time takes a few minutes)' : 'Starting the Linux engine');
    let pct = 15;
    const args = fresh ? ['start', `--name=${VM}`, '--tty=false', p.template] : ['start', '--tty=false', VM];
    const r = await host.run(p.limactl, args, {
      env,
      timeoutMs: 20 * 60_000,
      onOutput: (s) => {
        // Lima logs one line per stage; nudge the bar so the student sees it moving.
        if (/Downloading|Attempting|provision|Waiting/i.test(s) && pct < 75) say((pct += 5), 'Setting up the Linux engine');
      },
    });
    if (r.code !== 0) {
      if (/Virtualization\.framework|VZErrorDomain|not supported/i.test(logOf(r))) throw errors.virtualizationOff('darwin');
      throw errors.engineInstallFailed(fresh ? 'creating the Linux VM' : 'starting the Linux VM', logOf(r));
    }
  }

  say(80, 'Checking the Linux engine');
  const cli = [p.limactl, 'shell', '--workdir', '/', VM, 'podman'];
  const v = await host.run(cli[0], [...cli.slice(1), 'version', '--format', '{{.Client.Version}}'], { env, timeoutMs: 120_000 });
  if (v.code !== 0) throw errors.engineNotResponding(logOf(v));
  return {
    kind: 'lima-podman',
    cli,
    env,
    dockerHost: `unix://${p.socket}`,
    bundled: true,
    version: v.stdout.trim(),
    installedAt: new Date().toISOString(),
  };
}
