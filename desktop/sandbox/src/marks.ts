/**
 * Streaming parser for the shell's OSC 6973 marks (see hooks.ts).
 *
 * Feeds raw terminal bytes, returns the bytes with our marks removed (for
 * xterm.js) and the marks found. Marks can be split across chunks; anything
 * that is not ours, including other OSC sequences, passes through untouched.
 */

export type Mark =
  | { kind: "start"; n: number; command: string; cwd: string }
  | { kind: "end"; exitCode: number | null };

const PREFIX = "\x1b]6973;";
const MAX_MARK = 64 * 1024;

export class MarkParser {
  private pending = "";

  /** Returns [text for the screen, marks]. Text is a JS string (UTF-8 decoded by the caller). */
  feed(chunk: string): [string, Mark[]] {
    const parts = this.segments(chunk);
    return [parts.filter((p): p is string => typeof p === "string").join(""), parts.filter((p): p is Mark => typeof p !== "string")];
  }

  /** Text and marks in stream order, so output can be given to the right command. */
  segments(chunk: string): Array<string | Mark> {
    let s = this.pending + chunk;
    this.pending = "";
    const segs: Array<string | Mark> = [];
    const push = (t: string) => {
      if (t) segs.push(t);
    };
    for (;;) {
      const i = s.indexOf(PREFIX);
      if (i < 0) {
        // keep a possible partial prefix at the end for the next chunk
        const keep = partialPrefix(s);
        push(s.slice(0, s.length - keep));
        this.pending = s.slice(s.length - keep);
        break;
      }
      push(s.slice(0, i));
      const end = s.indexOf("\x07", i);
      if (end < 0) {
        if (s.length - i > MAX_MARK) {
          push(s.slice(i)); // not a real mark; give up on it
        } else {
          this.pending = s.slice(i);
        }
        break;
      }
      const m = parseMark(s.slice(i + PREFIX.length, end));
      if (m) segs.push(m);
      s = s.slice(end + 1);
    }
    return segs;
  }
}

function partialPrefix(s: string): number {
  for (let k = Math.min(PREFIX.length - 1, s.length); k > 0; k--) {
    if (PREFIX.startsWith(s.slice(s.length - k))) return k;
  }
  return 0;
}

const b64 = (s: string | undefined): string => Buffer.from(s ?? "", "base64").toString("utf8");

export function parseMark(body: string): Mark | null {
  const parts = body.split(";");
  if (parts[0] === "start" && parts.length >= 4) {
    return { kind: "start", n: Number(parts[1]) || 0, command: b64(parts[2]), cwd: b64(parts[3]) };
  }
  if (parts[0] === "end") {
    const code = Number(parts[1]);
    return { kind: "end", exitCode: Number.isFinite(code) && parts[1] !== "" ? code : null };
  }
  return null;
}

const EDITORS = new Set(["vim", "vi", "nvim", "view", "nano", "pico", "emacs", "micro", "ed", "joe", "mcedit"]);

/** If a command line opens a terminal editor, its name and first file argument. */
export function terminalEditor(command: string): { editor: string; file: string | null } | null {
  const words = command.trim().split(/\s+/);
  let i = 0;
  while (i < words.length && (words[i] === "sudo" || words[i] === "command" || /^[A-Z_]+=/.test(words[i]!))) i++;
  const w = words[i];
  if (!w) return null;
  const name = w.split("/").pop()!;
  if (!EDITORS.has(name)) return null;
  const file = words.slice(i + 1).find((a) => !a.startsWith("-") && !a.startsWith("+")) ?? null;
  return { editor: name, file };
}
