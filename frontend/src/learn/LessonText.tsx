import type { ReactNode } from "react";
import { CornerDownLeft } from "lucide-react";
import { cn } from "../ui";

/**
 * A lesson's Markdown, rendered to React elements (never as HTML, so a lesson
 * file can't inject markup). It covers what lessons use: headings, paragraphs,
 * lists, tables, fenced code and inline `code`, **bold** and *italic*.
 *
 * Code blocks in the lesson's language get a "Try it" button that loads the
 * example into the editor.
 */
export function LessonText({ markdown, language, onTry, className }: {
  markdown: string;
  language: string;
  onTry?: (code: string) => void;
  className?: string;
}) {
  return <div className={cn("grid gap-3 text-sm leading-relaxed text-muted", className)}>{blocks(markdown, language, onTry)}</div>;
}

type Block =
  | { kind: "code"; lang: string; text: string }
  | { kind: "heading"; level: number; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "table"; rows: string[][] }
  | { kind: "para"; text: string };

export function parse(md: string): Block[] {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const fence = line.match(/^```\s*([\w+#-]*)/);
    if (fence) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) body.push(lines[i++]);
      i++;
      out.push({ kind: "code", lang: fence[1], text: body.join("\n") + "\n" });
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      out.push({ kind: "heading", level: h[1].length, text: h[2] });
      i++;
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        let item = lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i])) item += " " + lines[i++].trim(); // wrapped item
        items.push(item);
      }
      out.push({ kind: "list", ordered, items });
      continue;
    }
    if (line.trimStart().startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("|")) {
        const cells = lines[i++].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        if (!cells.every((c) => /^:?-{2,}:?$/.test(c))) rows.push(cells); // skip the |---| line
      }
      out.push({ kind: "table", rows });
      continue;
    }
    if (!line.trim()) {
      i++;
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(```|#{1,4}\s|\s*([-*]|\d+\.)\s|\s*\|)/.test(lines[i])) para.push(lines[i++]);
    out.push({ kind: "para", text: para.join(" ") });
  }
  return out;
}

function blocks(md: string, language: string, onTry?: (code: string) => void): ReactNode[] {
  return parse(md).map((b, k) => {
    switch (b.kind) {
      case "code": {
        const runnable = !!onTry && b.lang === language;
        return (
          <div key={k} className="group relative">
            <pre className="m-0 overflow-x-auto rounded-lg border border-border bg-surface-2 px-3 py-2.5 font-mono text-[12.5px] leading-relaxed text-text">{b.text}</pre>
            {runnable && (
              <button onClick={() => onTry!(b.text)}
                title="Put this example in the editor (Ctrl Z brings your code back)"
                className="absolute right-1.5 top-1.5 flex items-center gap-1 rounded-md border border-border bg-surface px-2 py-1 text-[11px] font-medium text-accent shadow-sm transition-colors hover:border-accent/40">
                <CornerDownLeft className="size-3" />Try it
              </button>
            )}
          </div>
        );
      }
      case "heading":
        return b.level <= 2
          ? <h3 key={k} className="mt-3 border-t border-border pt-4 text-[15px] font-semibold text-text">{inline(b.text)}</h3>
          : <h4 key={k} className="mt-1 text-sm font-semibold text-text">{inline(b.text)}</h4>;
      case "list": {
        const Tag = b.ordered ? "ol" : "ul";
        return (
          <Tag key={k} className={cn("m-0 grid gap-1 pl-5", b.ordered ? "list-decimal" : "list-disc")}>
            {b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}
          </Tag>
        );
      }
      case "table":
        return (
          <div key={k} className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <tbody>
                {b.rows.map((r, j) => (
                  <tr key={j} className="border-b border-border">
                    {r.map((c, m) => j === 0
                      ? <th key={m} className="px-2 py-1.5 text-left font-semibold text-text">{inline(c)}</th>
                      : <td key={m} className="px-2 py-1.5 align-top">{inline(c)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      case "para":
        return <p key={k} className="m-0">{inline(b.text)}</p>;
    }
  });
}

/** `code`, **bold** and *italic*; everything else is plain text. */
function inline(s: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /`([^`]+)`|\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    if (m[1] !== undefined) out.push(<code key={m.index} className="rounded bg-surface-2 px-1 py-px font-mono text-[12.5px] text-text">{m[1]}</code>);
    else if (m[2] !== undefined) out.push(<strong key={m.index} className="font-semibold text-text">{m[2]}</strong>);
    else out.push(<em key={m.index}>{m[3]}</em>);
    last = re.lastIndex;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}
