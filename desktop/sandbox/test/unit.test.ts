/** Unit tests that need no container engine: parsers, recipes, compares, flags, setup-check wording. */

import { test } from "node:test";
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import { MarkParser, terminalEditor } from "../src/marks.ts";
import { parseCommandLine, record, emptyRecipe, replayScript } from "../src/recipe.ts";
import { outputsMatch } from "../src/run.ts";
import { Engine } from "../src/engine.ts";
import { Instance, homePath, parseSize } from "../src/instance.ts";
import { explain, setupCheck } from "../src/doctor.ts";
import { hostAllowed, tinyproxyFilter } from "../src/registries.ts";
import { isBuildOrRun, termPaste } from "../src/events.ts";
import { ProxyLogParser } from "../src/netlog.ts";
import { BASHRC, terminalCommand } from "../src/hooks.ts";

const b64 = (s: string) => Buffer.from(s).toString("base64");

test("marks are stripped, parsed in order, and may be split across chunks", () => {
  const p = new MarkParser();
  const start = `\x1b]6973;start;7;${b64("gcc main.c")};${b64("/home/student/labs/l/a")}\x07`;
  const whole = `$ gcc main.c\r\n${start}output\r\n\x1b]6973;end;1\x07$ `;
  const out: Array<string | object> = [];
  for (let i = 0; i < whole.length; i += 5) out.push(...p.segments(whole.slice(i, i + 5)));
  const text = out.filter((x) => typeof x === "string").join("");
  assert.equal(text, "$ gcc main.c\r\noutput\r\n$ ");
  const marks = out.filter((x) => typeof x !== "string");
  assert.deepEqual(marks, [{ kind: "start", n: 7, command: "gcc main.c", cwd: "/home/student/labs/l/a" }, { kind: "end", exitCode: 1 }]);
  // the command's output sits between its start and end marks
  const iStart = out.findIndex((x) => typeof x !== "string");
  const iEnd = out.findLastIndex((x) => typeof x !== "string");
  assert.equal(out.slice(iStart + 1, iEnd).join(""), "output\r\n");
});

test("other escape sequences pass through untouched", () => {
  const p = new MarkParser();
  const s = "\x1b]0;title\x07\x1b[32mgreen\x1b[0m";
  assert.deepEqual(p.feed(s), [s, []]);
});

test("terminal editors are recognised with their file", () => {
  assert.deepEqual(terminalEditor("vim main.c"), { editor: "vim", file: "main.c" });
  assert.deepEqual(terminalEditor("sudo nano -w /etc/hosts"), { editor: "nano", file: "/etc/hosts" });
  assert.deepEqual(terminalEditor("/usr/bin/vi +12 a.py"), { editor: "vi", file: "a.py" });
  assert.equal(terminalEditor("cat vim.txt"), null);
  assert.equal(terminalEditor("   "), null);
});

test("package commands feed the setup recipe", () => {
  assert.deepEqual(parseCommandLine("sudo apt update && sudo apt install -y valgrind gdb"), [{ manager: "apt", action: "install", packages: ["valgrind", "gdb"] }]);
  assert.deepEqual(parseCommandLine("pip install --user numpy==2.1 pandas"), [{ manager: "pip", action: "install", packages: ["numpy==2.1", "pandas"] }]);
  assert.deepEqual(parseCommandLine("python3 -m pip install -r requirements.txt flask"), [{ manager: "pip", action: "install", packages: ["flask"] }]);
  assert.deepEqual(parseCommandLine("npm install -g typescript"), [{ manager: "npm", action: "install", packages: ["typescript"] }]);
  assert.deepEqual(parseCommandLine("npm install express"), []); // local: lives in the synced lab folder
  assert.deepEqual(parseCommandLine("ls -la; make"), []);
  const r = emptyRecipe();
  record(r, "sudo apt install postgresql", "/home/student", 1);
  record(r, "echo hi", "/home/student", 2);
  assert.equal(r.steps.length, 1);
  const script = replayScript(r);
  assert.match(script, /apt install -y postgresql/);
  assert.match(script, /\[setup\] done/);
});

test("output comparison follows grading.py", () => {
  assert.ok(outputsMatch("4  \n\n", "4"));
  assert.ok(!outputsMatch("4\n", "4", "exact"));
  assert.ok(outputsMatch("1.0000001 2", "1 2", "tokens"));
  assert.ok(!outputsMatch("1 2 3", "1 2", "tokens"));
  assert.ok(outputsMatch('{"a": [1, 2.0]}', '{"a":[1,2]}', "json"));
  assert.ok(!outputsMatch("not json", "1", "json"));
});

test("paths stay inside the student's home", () => {
  assert.equal(homePath("labs/x/main.c"), "/home/student/labs/x/main.c");
  assert.equal(homePath("/home/student/labs/../labs/a"), "/home/student/labs/a");
  assert.throws(() => homePath("/etc/passwd"));
  assert.throws(() => homePath("../../etc/passwd"));
  assert.throws(() => homePath("/home/studentx"));
});

test("sizes from engine stats parse", () => {
  assert.equal(parseSize("2GiB"), 2 * 1024 ** 3);
  assert.equal(parseSize("1.5MB"), 1_500_000);
  assert.equal(parseSize("512KiB"), 512 * 1024);
  assert.equal(parseSize("junk"), undefined);
});

test("instance flags: isolated, limited, one capability per flag, network per mode", () => {
  const e = new Engine({ kind: "docker", cli: ["docker"] });
  const mk = (network: "off" | "registries" | "open") =>
    new Instance(e, { studentId: "PG25CS07", subjectId: "subj_8c1d", image: "ghcr.io/x/env:3", digest: "sha256:abc", network, limits: { memoryMb: 1024 } });
  const off = mk("off");
  assert.equal(off.name, "sid-pg25cs07-subj_8c1d");
  assert.equal(off.volume, "sidv-pg25cs07-subj_8c1d");
  assert.equal(off.hostname, "subj-8c1d");
  const a = off.createArgs();
  const s = a.join(" ");
  assert.ok(!s.includes("--privileged") && !s.includes("--network host"));
  assert.match(s, /--cap-drop ALL/);
  assert.ok(a.filter((x) => x === "--cap-add").length >= 10);
  assert.ok(!a.some((x) => x.includes(",") && a[a.indexOf(x) - 1] === "--cap-add"));
  assert.match(s, /--memory 1024m --memory-swap 1024m/);
  assert.match(s, /--cpus 2 /);
  assert.match(s, /--network none/);
  assert.match(s, /ghcr\.io\/x\/env@sha256:abc sleep infinity$/);
  assert.match(mk("registries").createArgs().join(" "), /--network sidnet-sid-pg25cs07-subj_8c1d .*https_proxy=http:\/\/sidproxy:8888/);
  assert.ok(!mk("open").createArgs().includes("--network"));
  assert.ok(!off.createArgs(false).includes("--memory"));
  // lab definition names with {student}
  const named = new Instance(e, { studentId: "UG23CS01", subjectId: "s", image: "i", network: "off", name: "sid-{student}-subj_9", volume: "sidv-{student}-subj_9" });
  assert.equal(named.name, "sid-ug23cs01-subj_9");
});

test("registries allowlist", () => {
  assert.ok(hostAllowed("files.pythonhosted.org"));
  assert.ok(hostAllowed("PYPI.org."));
  assert.ok(!hostAllowed("pypi.org.evil.com"));
  assert.ok(!hostAllowed("chat.openai.com"));
  assert.match(tinyproxyFilter(["a.b"]), /\^\(\.\+\\\.\)\?a\\\.b\$/);
});

test("proxy log lines become one net_conn per host and decision", () => {
  const p = new ProxyLogParser();
  const lines = [
    'CONNECT   Nov 08 [1]: Request (file descriptor 4): CONNECT pypi.org:443 HTTP/1.1',
    'CONNECT   Nov 08 [1]: Established connection to host "pypi.org" using file descriptor 5.',
    'CONNECT   Nov 08 [1]: Request (file descriptor 4): CONNECT pypi.org:443 HTTP/1.1',
    'CONNECT   Nov 08 [1]: Established connection to host "pypi.org" using file descriptor 5.',
    'CONNECT   Nov 08 [1]: Request (file descriptor 4): GET http://example.com/x HTTP/1.1',
    'NOTICE    Nov 08 [1]: Proxying refused on filtered domain "example.com"',
  ];
  const evs = lines.map((l) => p.line(l)).filter(Boolean);
  assert.deepEqual(evs.map((e) => e!.data), [{ host: "pypi.org", port: 443, allowed: true }, { host: "example.com", port: 80, allowed: false }]);
});

test("build and run commands count as runs; installs do not", () => {
  for (const c of ["gcc main.c", "./a.out", "make", "python3 x.py", "sudo time ./main", "npm test"]) assert.ok(isBuildOrRun(c), c);
  for (const c of ["ls", "vim main.c", "npm install", "cd ..", "apt install x"]) assert.ok(!isBuildOrRun(c), c);
});

test("terminal pastes carry length, lines and a hash, and are clipped", () => {
  const ev = termPaste("t1", "a\nb\n" + "x".repeat(30_000));
  assert.equal(ev.type, "term_paste");
  assert.equal(ev.data.lines, 3);
  assert.equal(ev.data.truncated, true);
  assert.equal((ev.data.text as string).length, 20_000);
  assert.match(String(ev.data.sha256), /^[0-9a-f]{64}$/);
});

test("hooks: rc file keeps marks, terminal starts a PTY with the size", () => {
  assert.match(BASHRC, /PS0=/);
  assert.match(BASHRC, /PROMPT_COMMAND=/);
  assert.match(BASHRC, /6973;start/);
  const cmd = terminalCommand("abc", 120, 40);
  assert.equal(cmd[cmd.length - 1], "/dev/null");
  assert.ok(cmd.join(" ").includes("stty rows 40 cols 120"));
});

test("setup check explains common engine failures", () => {
  assert.match(explain("Error: 0x80370102 The virtual machine could not be started", "wsl-podman")!.message, /BIOS/);
  assert.match(explain("Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?", "docker")!.message, /not running/);
  assert.match(explain("write /var/lib: no space left on device", "podman")!.fix, /10 GB/);
  assert.equal(explain("something else", "docker"), null);
});

/** A fake `spawn` that answers engine commands from a table. */
function fakeSpawn(answer: (args: string[]) => { code: number; stdout?: string; stderr?: string } | "ENOENT"): any {
  return (_cmd: string, args: string[]) => {
    const child: any = new EventEmitter();
    child.stdout = new PassThrough();
    child.stderr = new PassThrough();
    child.stdin = new PassThrough();
    child.kill = () => {};
    setImmediate(() => {
      const a = answer(args);
      if (a === "ENOENT") {
        child.emit("error", Object.assign(new Error("spawn docker ENOENT"), { code: "ENOENT" }));
        return;
      }
      child.stdout.end(a.stdout ?? "");
      child.stderr.end(a.stderr ?? "");
      setImmediate(() => child.emit("close", a.code));
    });
    return child;
  };
}

const bigHost = { platform: "linux" as const, arch: "x64", totalMemBytes: 16 * 1024 ** 3, freeMemBytes: 8 * 1024 ** 3, freeDiskBytes: 100 * 1024 ** 3 };

test("setup check: missing engine program", async () => {
  const r = await setupCheck({ kind: "docker", cli: ["docker"] }, { host: bigHost, spawnFn: fakeSpawn(() => "ENOENT") });
  assert.equal(r.ok, false);
  assert.equal(r.checks.at(-1)!.id, "engine.cli");
});

test("setup check: Docker installed but not running", async () => {
  const r = await setupCheck({ kind: "docker", cli: ["docker"] }, {
    host: bigHost,
    spawnFn: fakeSpawn(() => ({ code: 1, stdout: '{"Client":{"Version":"29.0"}}', stderr: "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?" })),
  });
  assert.equal(r.ok, false);
  const c = r.checks.find((x) => x.id === "engine.running")!;
  assert.match(c.message, /not running/);
  assert.match(c.fix!, /Start Docker Desktop/);
});

test("setup check: small machine and rootless cgroup v1 are reported", async () => {
  const r = await setupCheck({ kind: "podman", cli: ["podman"] }, {
    quick: true,
    host: { ...bigHost, totalMemBytes: 3 * 1024 ** 3, freeDiskBytes: 8 * 1024 ** 3 },
    spawnFn: fakeSpawn((a) => a[0] === "version"
      ? { code: 0, stdout: '{"Client":{"Version":"5.2.0","OsArch":"linux/amd64"}}' }
      : { code: 0, stdout: '{"host":{"cgroupVersion":"v1","security":{"rootless":true}}}' }),
  });
  assert.equal(r.ok, false); // 3 GB is too small
  assert.equal(r.checks.find((x) => x.id === "host.memory")!.severity, "error");
  assert.equal(r.checks.find((x) => x.id === "host.disk")!.severity, "warning");
  assert.equal(r.checks.find((x) => x.id === "engine.limits")!.ok, false);
});
