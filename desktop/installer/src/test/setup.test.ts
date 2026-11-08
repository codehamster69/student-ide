/**
 * Setup flow tests on faked Windows, macOS and Linux machines: every stop
 * reason produces the right plain error, and reruns are idempotent.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fakeHost, Rule } from './fake';
import { runSetup, detectEngine } from '../setup';
import { SetupError } from '../errors';
import { packageManager } from '../linux';

const opts = (host: ReturnType<typeof fakeHost>['host'], extra = {}) => ({ dataDir: '/data', host, ...extra });
const engineOk: Rule[] = [
  [/ version --format \{\{\.Client\.Version\}\}/, { stdout: '5.3.1\n' }],
  [/ info --format/, { stdout: 'true' }],
  [/ image inspect /, { code: 1 }],
  [/ pull /, {}],
  [/ volume (create|rm)/, {}],
  [/ run --rm /, {}],
  [/ version$/, { stdout: 'ok' }],
];
async function rejects(p: Promise<unknown>, code: string) {
  await assert.rejects(p, (e: unknown) => e instanceof SetupError && e.code === code);
}

// ---------- Windows ----------
const win = (rules: Rule[], extra = {}) => fakeHost({ platform: 'win32', release: '10.0.22631', rules, ...extra });
const virtOn: Rule = [/VirtualizationFirmwareEnabled/, { stdout: 'True False' }];

test('windows: WSL already on, imports our distro, saves engine.json, pulls images', async () => {
  let listed = false;
  const { host, calls, files } = win([
    virtOn,
    [/wsl\.exe --status/, {}],
    [/wsl\.exe --list --quiet/, () => ({ stdout: listed ? 'StudentIDE\r\n' : 'Ubuntu\r\n' })],
    [/wsl\.exe --import StudentIDE/, () => ((listed = true), {})],
    ...engineOk,
  ]);
  const progress: string[] = [];
  const res = await runSetup(opts(host, { images: [{ ref: 'ghcr.io/x/env-c@sha256:1' }], onProgress: (p: { step: string }) => progress.push(p.step) }));
  assert.equal(res.engine.kind, 'wsl-podman');
  assert.deepEqual(res.engine.cli.slice(0, 3), ['wsl.exe', '-d', 'StudentIDE']);
  assert.ok(calls.some((c) => /--import StudentIDE [\\/]data[\\/]engine[\\/]wsl [\\/]assets[\\/]wsl[\\/]studentide-rootfs\.tar\.gz --version 2/.test(c)));
  assert.ok(calls.some((c) => / pull ghcr\.io\/x\/env-c@sha256:1/.test(c)));
  assert.deepEqual([...new Set(progress)], ['check', 'engine', 'images', 'verify']);
  assert.equal(detectEngine('/data', host)?.kind, 'wsl-podman');
  assert.ok(Object.keys(files).some((f) => f.endsWith('engine.json')));
});

test('windows: rerun with the distro present does not import again', async () => {
  const { host, calls } = win([virtOn, [/--status/, {}], [/--list --quiet/, { stdout: 'StudentIDE\n' }], ...engineOk]);
  await runSetup(opts(host));
  assert.ok(!calls.some((c) => c.includes('--import')));
});

test('windows: WSL off, UAC accepted, restart needed -> NEEDS_REBOOT and resume registered', async () => {
  const { host, calls } = win([
    virtOn,
    [/--status/, { code: 1, stdout: 'WSL is not installed' }],
    [/IsInRole/, { stdout: 'False' }],
    [/Start-Process -FilePath wsl\.exe/, {}],
    [/reg\.exe add/, {}],
  ]);
  await rejects(runSetup(opts(host)), 'NEEDS_REBOOT');
  assert.ok(calls.some((c) => /RunOnce .*--resume-setup/.test(c)));
});

test('windows: UAC declined -> NEEDS_ADMIN with the IT note', async () => {
  const { host } = win([
    virtOn,
    [/--status/, { code: 1 }],
    [/IsInRole/, { stdout: 'False' }],
    [/Start-Process/, { code: 1223 }],
  ]);
  await assert.rejects(runSetup(opts(host)), (e: SetupError) => e.code === 'NEEDS_ADMIN' && !!e.needsAdmin && /IT/.test(e.fix));
});

test('windows: no admin but Docker Desktop works -> uses it with a warning', async () => {
  const { host } = win([
    virtOn,
    [/--status/, { code: 1 }],
    [/IsInRole/, { stdout: 'False' }],
    [/Start-Process/, { code: 1223 }],
    [/^docker version --format \{\{\.Server\.Version\}\}/, { stdout: '27.3.1' }],
    ...engineOk,
  ]);
  const res = await runSetup(opts(host));
  assert.equal(res.engine.kind, 'docker');
  assert.equal(res.engine.bundled, false);
  assert.match(res.warnings.join(), /docker already installed/);
});

test('windows: silent and not admin -> NEEDS_ADMIN without any prompt', async () => {
  const { host, calls } = win([virtOn, [/--status/, { code: 1 }], [/IsInRole/, { stdout: 'False' }]]);
  await rejects(runSetup(opts(host, { silent: true })), 'NEEDS_ADMIN');
  assert.ok(!calls.some((c) => c.includes('Start-Process')));
});

test('windows: inbox WSL without --no-distribution falls back to DISM, then asks for restart', async () => {
  const { host, calls } = win([
    virtOn,
    [/--status/, { code: 1 }],
    [/IsInRole/, { stdout: 'True' }],
    [/wsl\.exe --install --no-distribution/, { code: 1, stdout: 'Invalid command line option: --no-distribution' }],
    [/dism\.exe/, { code: 3010 }],
    [/reg\.exe/, {}],
  ]);
  await rejects(runSetup(opts(host)), 'NEEDS_REBOOT');
  assert.equal(calls.filter((c) => c.startsWith('dism.exe')).length, 2);
});

test('windows: virtualization off in BIOS, and old builds, stop early', async () => {
  await rejects(runSetup(opts(win([[/VirtualizationFirmwareEnabled/, { stdout: 'False False' }]]).host)), 'VIRTUALIZATION_OFF');
  await rejects(runSetup(opts(fakeHost({ platform: 'win32', release: '10.0.18363', rules: [] }).host)), 'OLD_WINDOWS');
});

test('windows: unknown virtualization (blank values) does not block', async () => {
  const { host } = win([[/VirtualizationFirmwareEnabled/, { stdout: ' ' }], [/--status/, {}], [/--list/, { stdout: 'StudentIDE' }], ...engineOk]);
  assert.equal((await runSetup(opts(host))).engine.kind, 'wsl-podman');
});

// ---------- macOS ----------
const mac = (rules: Rule[], release = '23.4.0') => fakeHost({ platform: 'darwin', release, arch: 'arm64', rules });

test('macos: creates the Lima VM from our template and exposes the socket', async () => {
  const { host, calls } = mac([
    [/sysctl -n kern\.hv_support/, { stdout: '1' }],
    [/limactl list --json/, { stdout: '' }],
    [/limactl start --name=studentide --tty=false .*studentide\.yaml/, {}],
    ...engineOk,
  ]);
  const res = await runSetup(opts(host));
  assert.equal(res.engine.kind, 'lima-podman');
  assert.equal(res.engine.dockerHost, `unix://${path.join('/data', 'engine', 'lima', 'studentide', 'sock', 'podman.sock')}`);
  assert.equal(res.engine.env?.LIMA_HOME, path.join('/data', 'engine', 'lima'));
  assert.ok(calls.some((c) => /limactl shell --workdir \/ studentide podman version/.test(c)));
});

test('macos: a stopped VM is started, not recreated', async () => {
  const { host, calls } = mac([
    [/sysctl/, { stdout: '1' }],
    [/limactl list --json/, { stdout: '{"name":"studentide","status":"Stopped"}\n' }],
    [/limactl start --tty=false studentide$/, {}],
    ...engineOk,
  ]);
  await runSetup(opts(host));
  assert.ok(!calls.some((c) => c.includes('--name=studentide')));
});

test('macos: macOS 12 and no hypervisor stop with plain errors', async () => {
  await rejects(runSetup(opts(mac([], '21.6.0').host)), 'OLD_MACOS');
  await rejects(runSetup(opts(mac([[/sysctl/, { stdout: '0' }]]).host)), 'VIRTUALIZATION_OFF');
});

// ---------- Linux ----------
const UBUNTU = 'ID=ubuntu\nID_LIKE=debian\n';

test('linux: package managers from os-release', () => {
  assert.equal(packageManager(UBUNTU)![0], 'sh');
  assert.equal(packageManager('ID=fedora\n')![0], 'dnf');
  assert.equal(packageManager('ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n')![0], 'zypper');
  assert.equal(packageManager('ID=manjaro\nID_LIKE=arch\n')![0], 'pacman');
  assert.equal(packageManager('ID=nixos\n'), undefined);
});

test('linux: existing rootless podman is used as is, with the user socket', async () => {
  const { host } = fakeHost({ rules: [[/systemctl --user enable --now podman\.socket/, {}], ...engineOk] });
  const res = await runSetup(opts(host));
  assert.deepEqual(res.engine.cli, ['podman']);
  assert.equal(res.engine.dockerHost, 'unix:///run/user/1000/podman/podman.sock');
  assert.equal(res.engine.bundled, false);
});

test('linux: missing podman is installed through pkexec in one prompt', async () => {
  let installed = false;
  const { host, calls } = fakeHost({
    files: { '/etc/os-release': UBUNTU },
    rules: [
      [/^podman /, (l) => (installed ? (/info/.test(l) ? { stdout: 'true' } : { stdout: '5.0.0' }) : { code: 127 })],
      [/^id -u/, { stdout: '1000' }],
      [/^pkexec sh -c apt-get update && apt-get install -y podman/, () => ((installed = true), {})],
      [/systemctl/, {}],
      ...engineOk,
    ],
  });
  const res = await runSetup(opts(host));
  assert.equal(res.engine.bundled, true);
  assert.equal(calls.filter((c) => c.startsWith('pkexec')).length, 1);
});

test('linux: password prompt dismissed -> static rootless podman in the home folder', async () => {
  const { host, files } = fakeHost({
    files: { '/etc/os-release': UBUNTU },
    rules: [
      [/^podman /, { code: 127 }],
      [/^id -u/, { stdout: '1000' }],
      [/^pkexec/, { code: 126 }],
      [/^unshare --user/, {}],
      [/^tar -xzf .*podman-linux-amd64\.tar\.gz/, {}],
      ...engineOk,
    ],
  });
  const res = await runSetup(opts(host));
  assert.equal(res.engine.cli[0], path.join('/data', 'engine', 'podman', 'podman-linux-amd64', 'usr', 'local', 'bin', 'podman'));
  assert.equal(res.engine.env!.XDG_CONFIG_HOME, path.join('/data', 'engine', 'podman', 'config'));
  assert.match(files[path.join('/data', 'engine', 'podman', 'config', 'containers', 'storage.conf')], /ignore_chown_errors/);
});

test('linux: no admin and user namespaces blocked -> NO_USER_NAMESPACES', async () => {
  const { host } = fakeHost({
    files: { '/etc/os-release': UBUNTU },
    rules: [[/^podman /, { code: 127 }], [/^id -u/, { stdout: '1000' }], [/^pkexec/, { code: 126 }], [/^unshare/, { code: 1 }]],
  });
  await rejects(runSetup(opts(host)), 'NO_USER_NAMESPACES');
});

// ---------- whole flow ----------
test('low disk stops before anything is installed; low RAM only warns', async () => {
  const { host, calls } = fakeHost({ rules: engineOk, freeDiskBytes: async () => 3 * 1024 ** 3 });
  await rejects(runSetup(opts(host)), 'LOW_DISK');
  assert.equal(calls.length, 0);
  const small = fakeHost({ rules: [[/systemctl/, {}], ...engineOk], totalMemBytes: 4 * 1024 ** 3 });
  assert.match((await runSetup(opts(small.host))).warnings.join(), /4 GB of memory/);
});

test('images already present are not pulled again; duplicates pulled once', async () => {
  const { host, calls } = fakeHost({
    rules: [[/systemctl/, {}], [/ image inspect a$/, {}], ...engineOk],
  });
  await runSetup(opts(host, { images: [{ ref: 'a' }, { ref: 'b' }, { ref: 'b' }] }));
  assert.deepEqual(calls.filter((c) => / pull /.test(c)), ['podman pull b']);
});

test('pull failing twice -> IMAGE_PULL_FAILED; a failing check -> CHECK_FAILED, engine.json not written', async () => {
  const bad = fakeHost({ rules: [[/systemctl/, {}], [/ pull /, { code: 1, stderr: 'timeout' }], ...engineOk] });
  await rejects(runSetup(opts(bad.host, { images: [{ ref: 'x' }] })), 'IMAGE_PULL_FAILED');

  const { host, files } = fakeHost({ rules: [[/systemctl/, {}], ...engineOk] });
  const check = async () => ({ ok: false, checks: [{ id: 'network', ok: false, message: 'proxy down' }] });
  await assert.rejects(runSetup(opts(host, { check })), (e: SetupError) => e.code === 'CHECK_FAILED' && /network/.test(e.detail));
  assert.ok(!Object.keys(files).some((f) => f.endsWith('engine.json')));
});

test('SetupError survives IPC as plain JSON', () => {
  const e = new SetupError({ code: 'NEEDS_ADMIN', title: 't', detail: 'd', fix: 'f', needsAdmin: true });
  assert.deepEqual(JSON.parse(JSON.stringify(e)), { code: 'NEEDS_ADMIN', title: 't', detail: 'd', fix: 'f', needsAdmin: true });
});
