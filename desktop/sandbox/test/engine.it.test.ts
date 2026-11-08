/**
 * Integration tests against a real engine (SANDBOX_IT=1; Docker by default,
 * SANDBOX_CLI="podman" for Podman). Needs the dev image and the proxy image:
 *   docker build -t studentide-dev-base:test images/dev-base
 *   docker build -t ghcr.io/codehamster69/studentide-sidproxy:1 images/sidproxy
 * Covers the student path end to end through registerSandboxIpc with a fake
 * server: open a lab, terminal, run, tests, submit, then a second machine that
 * gets the files and the setup recipe back.
 */

import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createSandbox, registerSandboxIpc, setupCheck, type EngineInfo, type Instance } from "../src/index.ts";

const RUN = process.env.SANDBOX_IT === "1";
const cli = (process.env.SANDBOX_CLI ?? "docker").split(" ");
const ENGINE: EngineInfo = { kind: cli[0] === "podman" ? "podman" : "docker", cli };
const IMAGE = process.env.SANDBOX_IMAGE ?? "studentide-dev-base:test";
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function until(f: () => boolean, ms = 10_000): Promise<void> {
  const end = Date.now() + ms;
  while (!f()) {
    if (Date.now() > end) throw new Error("timed out waiting");
    await wait(100);
  }
}

const LAB = {
  format: "studentide.sandbox-lab/1", id: "slab_it", version: 1, title: "IT lab",
  subject: { id: "subj_it", code: "CS101", title: "Intro" },
  environment: { id: "env_it", version: 1, image: IMAGE, digest: null, resources: { cpus: 1, memory_mb: 512, disk_gb: 2, pids: 256 } },
  instance: { name: "sid-{student}-subj_it", volume: "sidv-{student}-subj_it", user: "student", home: "/home/student" },
  network: "off", assessed: true,
  assignments: [{
    id: "asg_double", position: 0, title: "Double it", statement: "",
    workdir: "/home/student/labs/slab_it/asg_double",
    files: [{ path: "main.c", content: "#include <stdio.h>\nint main(){int n; scanf(\"%d\", &n); printf(\"%d\\n\", n);}\n", executable: false }],
    open: ["main.c"], run: "gcc main.c -o main && ./main",
    tests: { kind: "io", command: "", timeout_s: 10, visible: [{ name: "two", stdin: "2\n", expected: "4\n", compare: "text" }], n_hidden: 2 },
  }],
};

/** In-memory stand-in for the server routes the runtime uses. */
function fakeServer() {
  const snaps = new Map<string, { sha: string; data: Buffer; reason: string }>();
  const recipes = new Map<string, unknown>();
  const reply = (status: number, body?: unknown, raw?: Buffer) =>
    new Response(raw ? new Uint8Array(raw) : (body === undefined ? null : JSON.stringify(body)), { status });
  const fetch = async (path: string, init: any = {}) => {
    const u = new URL(path, "http://server");
    const p = u.pathname;
    if (p === "/api/me") return reply(200, { student_id: "PG25IT01" });
    if (p === "/api/sandbox/my/labs/slab_it") return reply(200, LAB);
    let m = /^\/api\/workspaces\/recipes\/([^/]+)$/.exec(p);
    if (m) {
      if (init.method === "PUT") { recipes.set(m[1]!, JSON.parse(String(init.body))); return reply(200, { ok: true }); }
      return recipes.has(m[1]!) ? reply(200, recipes.get(m[1]!)) : reply(404, {});
    }
    m = /^\/api\/workspaces\/([^/]+)\/([^/]+)(\/meta)?$/.exec(p);
    if (m) {
      const k = `${m[1]}/${m[2]}`;
      if (init.method === "PUT") {
        snaps.set(k, { sha: init.headers["X-Workspace-Sha256"], data: Buffer.from(init.body), reason: init.headers["X-Workspace-Reason"] });
        return reply(200, { ok: true });
      }
      const s = snaps.get(k);
      if (!s) return reply(404, {});
      return m[3] ? reply(200, { sha256: s.sha }) : reply(200, undefined, s.data);
    }
    return reply(404, {});
  };
  return { fetch, snaps, recipes };
}

function fakeCtx(server: ReturnType<typeof fakeServer>, userData: string) {
  const handlers = new Map<string, (...a: any[]) => any>();
  const emitted: Array<{ name: string; data: any }> = [];
  const ctx = {
    handle: (n: string, f: any) => handlers.set(n, f),
    emit: (name: string, data: unknown) => emitted.push({ name, data }),
    server: () => "http://server",
    fetch: server.fetch,
    userData,
  };
  const call = (n: string, ...a: any[]) => handlers.get(n)!(...a);
  return { ctx, call, emitted };
}

const fail = (info: { title: string }) => { throw new Error(info.title); };

before(async () => {
  if (!RUN) return;
  const s = createSandbox({ engine: ENGINE, dataDir: tmpdir() });
  await s.instance({ studentId: "PG25IT01", subjectId: "subj_it", image: IMAGE, network: "off", name: LAB.instance.name, volume: LAB.instance.volume }).destroy();
});

after(async () => {
  if (!RUN) return;
  const s = createSandbox({ engine: ENGINE, dataDir: tmpdir() });
  await s.instance({ studentId: "PG25IT01", subjectId: "subj_it", image: IMAGE, network: "off", name: LAB.instance.name, volume: LAB.instance.volume }).destroy();
});

test("setup check passes on this engine", { skip: !RUN }, async () => {
  const r = await setupCheck(ENGINE, { image: IMAGE });
  assert.ok(r.ok, JSON.stringify(r.checks.filter((c) => !c.ok)));
  assert.ok(r.checks.some((c) => c.id === "engine.run" && c.ok));
});

test("a student does a lab, then carries on on another machine", { skip: !RUN, timeout: 240_000 }, async () => {
  const server = fakeServer();
  const m1 = fakeCtx(server, await mkdtemp(join(tmpdir(), "sbx-m1-")));
  const ipc1 = registerSandboxIpc(m1.ctx, { engine: () => ENGINE, fail });

  const lab = await m1.call("sandbox.openLab", "slab_it");
  assert.equal(lab.instanceId, "sid-pg25it01-subj_it");
  assert.equal(lab.assignments[0].files, "new");
  assert.equal(lab.limitsEnforced, true);
  const W = lab.assignments[0].workdir;
  assert.match(await m1.call("sandbox.readFile", lab.instanceId, `${W}/main.c`), /printf/);

  // the starter is wrong: tests fail locally
  const t1 = await m1.call("sandbox.test", lab.instanceId, "asg_double");
  assert.equal(t1[0].passed, false);

  // fix it in the editor
  await m1.call("sandbox.writeFile", lab.instanceId, `${W}/main.c`, "#include <stdio.h>\nint main(){int n; scanf(\"%d\", &n); printf(\"%d\\n\", 2*n);}\n");
  const run = await m1.call("sandbox.run", lab.instanceId, "asg_double", { stdin: "21\n" });
  assert.equal(run.stdout, "42\n");
  assert.equal(run.error_type, null);
  assert.equal((await m1.call("sandbox.test", lab.instanceId, "asg_double"))[0].passed, true);

  // terminal: a command, a vim session, a package command for the recipe
  const { id } = await m1.call("terminal.open", lab.instanceId, { assignmentId: "asg_double", cols: 100, rows: 30 });
  const term = (name: string) => m1.emitted.filter((e) => e.name === name && e.data.id === id);
  const sbx = () => m1.emitted.filter((e) => e.name === "sandbox.event").map((e) => e.data);
  await wait(800);
  await m1.call("terminal.write", id, "ls && echo done-$((6*7))\n");
  await until(() => term("terminal.data").map((e) => e.data.data).join("").includes("done-42"));
  await until(() => sbx().some((e) => e.type === "term_cmd" && e.data.phase === "end" && e.data.command.startsWith("ls")));
  await m1.call("terminal.paste", id, "echo pasted\n");
  await until(() => sbx().some((e) => e.type === "term_paste"));
  await m1.call("terminal.write", id, "vim notes.txt\n");
  await until(() => term("terminal.surface").some((e) => e.data.surface === "terminal-editor" && e.data.path === "notes.txt"));
  await m1.call("terminal.write", id, "ihello from vim\x1b:wq\r");
  await until(() => term("terminal.surface").at(-1)?.data.surface === "terminal");
  // the sidecar watcher saw the vim save (schema v3 fs_change), with the new line as its diff
  await until(() => sbx().some((e) => e.type === "fs_change" && String(e.data.path).endsWith("/notes.txt")), 10_000);
  const save = sbx().find((e) => e.type === "fs_change" && String(e.data.path).endsWith("/notes.txt"))!;
  assert.equal(save.data.origin, "terminal-editor");
  assert.equal(save.data.added, "hello from vim");
  assert.ok(!sbx().some((e) => e.type === "fs_change" && String(e.data.path).endsWith(".swp")));
  // the editor's own saves are not reported again as fs_change (they are edits already)
  assert.ok(!sbx().some((e) => e.type === "fs_change" && String(e.data.path).endsWith("/main.c")));
  // a package command that succeeds without network (sudo is already installed)
  await m1.call("terminal.write", id, "sudo apt-get install -y --no-download sudo\n");
  await until(() => sbx().some((e) => e.type === "pkg_install"), 30_000);
  await until(() => server.recipes.has("subj_it"), 10_000);
  assert.ok(sbx().every((e) => e.sessionKey === "slab_it/asg_double"));
  assert.ok(sbx().some((e) => e.type === "run" && e.data.source === "button"));

  const sub = await m1.call("sandbox.submit", lab.instanceId, "asg_double");
  assert.match(sub.sha256, /^[0-9a-f]{64}$/);
  assert.equal(server.snaps.get("slab_it/asg_double")!.reason, "submit");
  const st = await m1.call("sandbox.stats", lab.instanceId);
  assert.equal(st.state, "running");
  assert.equal(st.memoryLimitBytes, 512 * 1024 * 1024);
  await ipc1.shutdown();

  // "another machine": the instance and its volume are gone, a fresh userData
  const s = createSandbox({ engine: ENGINE, dataDir: tmpdir() });
  await s.instance({ studentId: "PG25IT01", subjectId: "subj_it", image: IMAGE, network: "off", name: LAB.instance.name, volume: LAB.instance.volume }).destroy();
  const m2 = fakeCtx(server, await mkdtemp(join(tmpdir(), "sbx-m2-")));
  const ipc2 = registerSandboxIpc(m2.ctx, { engine: () => ENGINE, fail });
  const lab2 = await m2.call("sandbox.openLab", "slab_it");
  assert.equal(lab2.assignments[0].files, "restored");
  assert.ok(lab2.setup && lab2.setup.replayed >= 1, "setup recipe replayed");
  assert.match(await m2.call("sandbox.readFile", lab2.instanceId, `${W}/main.c`), /2\*n/);
  assert.match(await m2.call("sandbox.readFile", lab2.instanceId, `${W}/notes.txt`), /hello from vim/);
  assert.equal((await m2.call("sandbox.run", lab2.instanceId, "asg_double", { stdin: "5\n" })).stdout, "10\n");
  await ipc2.shutdown();
});

test("time limit and memory limit are enforced inside the instance", { skip: !RUN, timeout: 120_000 }, async () => {
  const s = createSandbox({ engine: ENGINE, dataDir: tmpdir() });
  const inst: Instance = s.instance({ studentId: "it", subjectId: "limits", image: IMAGE, network: "off", limits: { memoryMb: 128 } });
  await inst.destroy();
  await inst.start({ stopOthers: false });
  try {
    await inst.exec(["mkdir", "-p", "/home/student/w"]);
    const slow = await s.run(inst, "k", { workdir: "/home/student/w", command: "sleep 30", timeoutMs: 1000 });
    assert.equal(slow.error_type, "Timeout");
    assert.equal(slow.exit_code, null);
    const hog = await s.run(inst, "k", { workdir: "/home/student/w", command: "python3 -c 'b = bytearray(400*1024*1024); print(len(b))'", timeoutMs: 20_000 });
    assert.notEqual(hog.stdout.trim(), String(400 * 1024 * 1024), "allocation beyond the limit must fail");
  } finally {
    await inst.destroy();
  }
});

test("network modes: off blocks everything, registries allows only registries", { skip: !RUN || process.env.SANDBOX_IT_NET !== "1", timeout: 240_000 }, async () => {
  const s = createSandbox({ engine: ENGINE, dataDir: tmpdir() });
  const code = async (inst: Instance, url: string) =>
    (await inst.exec(["sh", "-c", `curl -s -m 15 -o /dev/null -w '%{http_code}' -k ${url} || true`], { timeoutMs: 30_000 })).stdout.toString();
  const off = s.instance({ studentId: "it", subjectId: "net_off", image: IMAGE, network: "off" });
  await off.destroy();
  await off.start({ stopOthers: false });
  assert.equal(await code(off, "http://archive.ubuntu.com/ubuntu/"), "000");
  await off.destroy();
  const reg = s.instance({ studentId: "it", subjectId: "net_reg", image: IMAGE, network: "registries" });
  await reg.destroy();
  await reg.start({ stopOthers: false });
  try {
    assert.equal(await code(reg, "http://archive.ubuntu.com/ubuntu/"), "200");
    assert.equal(await code(reg, "http://example.com/"), "403");
  } finally {
    await reg.destroy();
  }
});
