/** fs_change / port_open from the sidecar watcher's lines (no engine needed), and the line diff. */

import { test } from "node:test";
import assert from "node:assert/strict";
import { FsWatch, parseWatchLine, watchScript } from "../src/watcher.ts";
import { lineDiff } from "../src/textdiff.ts";
import { sha256 } from "../src/events.ts";

const H = "/home/student/labs/l1/a1";
const line = (k: string, text: string, rel: string) => `${k} ${Buffer.byteLength(text)} ${sha256(text)} /w/labs/l1/a1/${rel}`;

function rig(files: Record<string, string>, fg: { command: string; editorFile: string | null } | null = null) {
  const events: Array<{ key: string; type: string; data: any }> = [];
  const ports: any[] = [];
  const ctx = {
    fg,
    sessionKey: (p: string) => (p.startsWith(H + "/") ? "l1/a1" : null),
    foreground: () => ctx.fg,
    read: async (p: string) => Buffer.from(files[p.slice(H.length + 1)] ?? ""),
  };
  const w = new FsWatch(ctx, (key, ev) => events.push({ key, ...ev }), (_k, ev) => ports.push(ev.data));
  return { w, events, ports, ctx, files };
}

test("line parser reads every kind and maps /w to the home folder", () => {
  assert.deepEqual(parseWatchLine(`F 3 ${"a".repeat(64)} /w/labs/x/main.c`), { kind: "F", size: 3, sha: "a".repeat(64), path: "/home/student/labs/x/main.c" });
  assert.deepEqual(parseWatchLine("D /w/a b.txt"), { kind: "D", path: "/home/student/a b.txt" });
  assert.deepEqual(parseWatchLine("L 8000 python3"), { kind: "L", port: 8000, process: "python3" });
  assert.deepEqual(parseWatchLine("U 8000"), { kind: "U", port: 8000 });
  assert.equal(parseWatchLine("garbage"), null);
  assert.match(watchScript(), /-newer \$T\/old/);
});

test("baseline is silent, a vim save is a terminal-editor change with a diff", async () => {
  const r = rig({ "main.c": "int main(){}\n" });
  await r.w.line(line("B", "int main(){}\n", "main.c"));
  await r.w.line("R");
  assert.equal(r.events.length, 0);
  r.files["main.c"] = "#include <stdio.h>\nint main(){}\n";
  r.ctx.fg = { command: "vim main.c", editorFile: `${H}/main.c` };
  await r.w.line(line("F", r.files["main.c"]!, "main.c"));
  assert.equal(r.events.length, 1);
  const e = r.events[0]!;
  assert.equal(e.type, "fs_change");
  assert.equal(e.key, "l1/a1");
  assert.equal(e.data.origin, "terminal-editor");
  assert.equal(e.data.command, "vim main.c");
  assert.equal(e.data.added, "#include <stdio.h>");
  assert.equal(e.data.added_lines, 1);
  // the same content again is not a new change
  await r.w.line(line("F", r.files["main.c"]!, "main.c"));
  assert.equal(r.events.length, 1);
});

test("the editor's own saves are not reported; a write with no terminal command is 'outside'", async () => {
  const r = rig({ "a.py": "" });
  r.w.expect(`${H}/a.py`, "print(1)\n");
  await r.w.line(line("F", "print(1)\n", "a.py"));
  assert.equal(r.events.length, 0);
  r.files["a.py"] = "print(1)\nprint(2)\n";
  await r.w.line(line("F", r.files["a.py"]!, "a.py"));
  assert.equal(r.events[0]!.data.origin, "outside");
  assert.equal(r.events[0]!.data.added, "print(2)");
});

test("cat > file from the shell is a terminal change; deletes and files outside assignments", async () => {
  const r = rig({ "x.txt": "hello\n" });
  r.ctx.fg = { command: "cat > x.txt", editorFile: null };
  await r.w.line(line("F", "hello\n", "x.txt"));
  assert.equal(r.events[0]!.data.origin, "terminal");
  await r.w.line("D /w/labs/l1/a1/x.txt");
  assert.equal(r.events[1]!.data.deleted, true);
  await r.w.line(`F 1 ${"b".repeat(64)} /w/.bashrc`);
  assert.equal(r.events.length, 2);
});

test("ports are reported once when they open and once when they close", async () => {
  const r = rig({});
  await r.w.line("L 5000 flask");
  await r.w.line("L 5000 flask");
  await r.w.line("U 5000");
  assert.deepEqual(r.ports, [{ port: 5000, process: "flask", open: true }, { port: 5000, process: "", open: false }]);
});

test("line diff finds inserted and removed lines", () => {
  const d = lineDiff("a\nb\nc\n", "a\nB\nc\nd\n");
  assert.equal(d.added, "B\nd");
  assert.equal(d.addedLines, 2);
  assert.equal(d.removedLines, 1);
  assert.match(d.diff, /^ a\n-b\n\+B\n c\n\+d/);
  assert.equal(lineDiff("", "x").added, "x");
});
