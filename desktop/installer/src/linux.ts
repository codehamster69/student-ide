/**
 * Linux: use rootless Podman. Install it from the distro's packages through a
 * graphical password prompt (pkexec); without admin rights, unpack the
 * bundled static rootless Podman into the app's userData folder instead,
 * which works wherever unprivileged user namespaces are allowed.
 */
import path from 'node:path';
import { errors } from './errors';
import { logOf } from './exec';
import type { Host } from './host';
import type { EngineInfo } from './types';

/** argv to run as root; apt is wrapped in one sh -c so the password is asked once. */
type Pm = string[];

/** Package-manager command for /etc/os-release (ID and ID_LIKE). */
export function packageManager(osRelease: string): Pm | undefined {
  const field = (k: string) => (osRelease.match(new RegExp(`^${k}="?([^"\\n]*)"?`, 'm'))?.[1] ?? '').toLowerCase();
  const ids = `${field('ID')} ${field('ID_LIKE')}`.split(/\s+/);
  const has = (...n: string[]) => n.some((x) => ids.includes(x));
  if (has('debian', 'ubuntu')) return ['sh', '-c', 'apt-get update && apt-get install -y podman uidmap slirp4netns'];
  if (has('fedora', 'rhel', 'centos')) return ['dnf', 'install', '-y', 'podman'];
  if (has('suse', 'opensuse')) return ['zypper', '--non-interactive', 'install', 'podman'];
  if (has('arch')) return ['pacman', '-S', '--noconfirm', 'podman'];
  return undefined;
}

let lastLog = '';
/** Version if this podman answers `version` and `info`; failures are kept in lastLog for the error. */
async function podmanWorks(host: Host, cli: string[], env?: Record<string, string>): Promise<string | undefined> {
  const r = await host.run(cli[0], [...cli.slice(1), 'version', '--format', '{{.Client.Version}}'], { env, timeoutMs: 60_000 });
  if (r.code !== 0) return void (lastLog = logOf(r));
  const info = await host.run(cli[0], [...cli.slice(1), 'info', '--format', '{{.Host.Security.Rootless}}'], { env, timeoutMs: 60_000 });
  // Running as root (lab-room provisioning) is fine for the check; the app itself always runs as the student.
  if (info.code !== 0) return void (lastLog = logOf(info));
  return r.stdout.trim();
}

async function userSocket(host: Host): Promise<string | undefined> {
  const r = await host.run('systemctl', ['--user', 'enable', '--now', 'podman.socket']);
  const runtime = host.env.XDG_RUNTIME_DIR;
  return r.code === 0 && runtime ? `unix://${runtime}/podman/podman.sock` : undefined;
}

async function installPackage(host: Host, silent: boolean): Promise<{ ok: boolean; log: string }> {
  const pm = packageManager(host.readFile('/etc/os-release') ?? '');
  if (!pm) return { ok: false, log: 'unknown distribution' };
  const isRoot = (await host.run('id', ['-u'])).stdout.trim() === '0';
  // Root: run directly. Silent (IT script): sudo without a prompt. Otherwise: pkexec's graphical password prompt.
  const elevated = (argv: string[]): [string, string[]] =>
    isRoot ? [argv[0], argv.slice(1)] : silent ? ['sudo', ['-n', ...argv]] : ['pkexec', argv];
  const r = await host.run(...elevated(pm), { timeoutMs: 15 * 60_000 });
  return { ok: r.code === 0, log: logOf(r) };
}

/** The no-admin route: unpack podman-static and write configs pointing at its helpers. */
async function unpackStatic(host: Host): Promise<{ cli: string[]; env: Record<string, string> }> {
  const userns = await host.run('unshare', ['--user', '--map-root-user', 'true']);
  if (userns.code !== 0) throw errors.noUserNamespaces(logOf(userns));
  // With subuid ranges set for this user, podman insists on the setuid newuidmap helper,
  // which we cannot ship; without ranges it runs with a single uid mapping.
  const user = host.env.USER ?? (await host.run('id', ['-un'])).stdout.trim();
  const hasRange = (host.readFile('/etc/subuid') ?? '').split('\n').some((l) => l.startsWith(`${user}:`));
  if (hasRange && (await host.run('newuidmap', [])).code === 127) {
    throw errors.needsAdmin(
      'Podman needs the small "uidmap" package (the newuidmap helper), which only an administrator can install.',
      undefined,
      'Ask the administrator to run "sudo apt install podman uidmap" (Fedora: sudo dnf install podman), then open ' +
        'Student IDE again.',
    );
  }
  const arch = host.arch === 'arm64' ? 'arm64' : 'amd64';
  const tar = path.join(host.assetsDir, 'podman-static', `podman-linux-${arch}.tar.gz`);
  if (!host.exists(tar)) throw errors.engineInstallFailed('looking for the bundled Podman (file missing)', tar);
  const root = path.join(host.dataDir, 'engine', 'podman');
  const bin = path.join(root, `podman-linux-${arch}`, 'usr', 'local');
  if (!host.exists(path.join(bin, 'bin', 'podman'))) {
    host.writeFile(path.join(root, '.keep'), '');
    const r = await host.run('tar', ['-xzf', tar, '-C', root], { timeoutMs: 5 * 60_000 });
    if (r.code !== 0) throw errors.engineInstallFailed('unpacking Podman', logOf(r));
  }
  // Podman reads containers.conf, storage.conf, registries.conf and policy.json from
  // $XDG_CONFIG_HOME/containers, so a private XDG_CONFIG_HOME keeps all of it inside our folder.
  const xdg = path.join(root, 'config');
  const conf = path.join(xdg, 'containers');
  host.writeFile(
    path.join(conf, 'containers.conf'),
    `[engine]\nhelper_binaries_dir = ["${bin}/lib/podman", "${bin}/bin"]\nconmon_path = ["${bin}/lib/podman/conmon"]\n` +
      `cgroup_manager = "cgroupfs"\nevents_logger = "file"\n\n[engine.runtimes]\ncrun = ["${bin}/bin/crun"]\n`,
  );
  // Without setuid newuidmap only one uid maps into the container; ignore_chown_errors keeps images usable.
  host.writeFile(
    path.join(conf, 'storage.conf'),
    `[storage]\ndriver = "overlay"\ngraphroot = "${path.join(root, 'storage')}"\n\n` +
      `[storage.options.overlay]\nignore_chown_errors = "true"\n`,
  );
  host.writeFile(path.join(conf, 'policy.json'), JSON.stringify({ default: [{ type: 'insecureAcceptAnything' }] }));
  // Image pulls read policy.json only from ~/.config or /etc; add the default "accept" policy if neither has one.
  const userPolicy = path.join(host.env.HOME ?? root, '.config', 'containers', 'policy.json');
  if (!host.exists(userPolicy) && !host.exists('/etc/containers/policy.json')) {
    host.writeFile(userPolicy, JSON.stringify({ default: [{ type: 'insecureAcceptAnything' }] }));
  }
  host.writeFile(path.join(conf, 'registries.conf'), 'unqualified-search-registries = ["ghcr.io", "docker.io"]\n');
  const env: Record<string, string> = { XDG_CONFIG_HOME: xdg };
  // Podman needs a private runtime dir; without a login session (su, sudo -u, some kiosks) there is none.
  const runtime = host.env.XDG_RUNTIME_DIR;
  if (!runtime || !host.exists(runtime)) {
    env.XDG_RUNTIME_DIR = path.join(root, 'run');
    await host.run('mkdir', ['-p', '-m', '700', env.XDG_RUNTIME_DIR]);
  }
  return { cli: [path.join(bin, 'bin', 'podman')], env };
}

export async function setupLinux(host: Host, silent: boolean, say: (pct: number, msg: string) => void): Promise<EngineInfo> {
  const now = () => new Date().toISOString();

  say(10, 'Looking for Podman');
  let version = await podmanWorks(host, ['podman']);
  let bundled = false;
  if (!version) {
    say(20, 'Installing Podman (your password may be asked)');
    const pkg = await installPackage(host, silent);
    if (pkg.ok) {
      version = await podmanWorks(host, ['podman']);
      bundled = true;
    }
    if (!version) {
      say(50, 'Setting up Podman in your home folder');
      const s = await unpackStatic(host);
      const v = await podmanWorks(host, s.cli, s.env);
      if (!v) throw errors.engineNotResponding(`${lastLog}\n\npackage route: ${pkg.log}`);
      return { kind: 'podman', cli: s.cli, env: s.env, bundled: true, version: v, installedAt: now() };
    }
  }
  say(80, 'Starting the Podman service');
  const dockerHost = await userSocket(host);
  return { kind: 'podman', cli: ['podman'], dockerHost, bundled, version, installedAt: now() };
}
