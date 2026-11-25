import type { ReactNode } from "react";
import { ExternalLink } from "lucide-react";
import { cn } from "../ui";
import { headingId } from "./content";

/**
 * A guide page's Markdown, rendered to React elements (never as HTML). Covers what
 * the guides use: ## and ### headings (with ids for "On this page"), paragraphs,
 * lists, tables, fenced code, > notes, `code`, **bold**, *italic* and [links](slug).
 */

/** How an in-guide link is followed: a hash to put in the address bar, or a callback. */
export type LinkTo = (target: string) => { href?: string; onClick?: () => void } | null;

type Block =
  | { kind: "code"; text: string }
  | { kind: "heading"; level: number; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "table"; rows: string[][] }
  | { kind: "note"; text: string }
  | { kind: "para"; text: string };

const LIST = /^\s*([-*]|\d+\.)\s+/;

function parse(md: string): Block[] {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  const out: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) body.push(lines[i++]);
      i++;
      out.push({ kind: "code", text: body.join("\n") });
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) { out.push({ kind: "heading", level: h[1].length, text: h[2] }); i++; continue; }
    if (line.startsWith(">")) {
      const body: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) body.push(lines[i++].replace(/^>\s?/, ""));
      out.push({ kind: "note", text: body.join(" ") });
      continue;
    }
    if (LIST.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const items: string[] = [];
      while (i < lines.length && LIST.test(lines[i])) {
        let item = lines[i++].replace(LIST, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !LIST.test(lines[i])) item += " " + lines[i++].trim();
        items.push(item);
      }
      out.push({ kind: "list", ordered, items });
      continue;
    }
    if (line.trimStart().startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("|")) {
        const cells = lines[i++].trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        if (!cells.every((c) => /^:?-{2,}:?$/.test(c))) rows.push(cells);
      }
      out.push({ kind: "table", rows });
      continue;
    }
    if (!line.trim()) { i++; continue; }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(```|#{1,4}\s|>|\s*([-*]|\d+\.)\s|\s*\|)/.test(lines[i])) para.push(lines[i++]);
    out.push({ kind: "para", text: para.join(" ") });
  }
  return out;
}

export function GuideMarkdown({ markdown, linkTo, className }: { markdown: string; linkTo: LinkTo; className?: string }) {
  const inl = (s: string) => inline(s, linkTo);
  return (
    <div className={cn("grid gap-4 text-[15px] leading-[1.7] text-muted", className)}>
      {parse(markdown).map((b, k) => {
        switch (b.kind) {
          case "code":
            return <pre key={k} className="m-0 overflow-x-auto rounded-lg border border-border bg-surface-2 px-4 py-3 font-mono text-[13px] leading-relaxed text-text">{b.text}</pre>;
          case "heading":
            return b.level <= 2
              ? <h2 key={k} id={headingId(b.text)} className="mt-6 scroll-mt-20 text-lg font-semibold tracking-[-0.01em] text-text">{inl(b.text)}</h2>
              : <h3 key={k} id={headingId(b.text)} className="mt-2 scroll-mt-20 text-[15px] font-semibold text-text">{inl(b.text)}</h3>;
          case "note":
            return <div key={k} className="rounded-lg border-l-2 border-accent-2 py-1 pl-4 pr-2 text-[14px] text-text">{inl(b.text)}</div>;
          case "list": {
            const Tag = b.ordered ? "ol" : "ul";
            return (
              <Tag key={k} className={cn("m-0 grid gap-1.5 pl-6 marker:text-faint", b.ordered ? "list-decimal" : "list-disc")}>
                {b.items.map((it, j) => <li key={j} className="pl-1">{inl(it)}</li>)}
              </Tag>
            );
          }
          case "table":
            return (
              <div key={k} className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full border-collapse text-[14px]">
                  <thead className="border-b border-border-strong">
                    <tr>{b.rows[0]?.map((c, m) => <th key={m} className="px-3 py-2 text-left font-semibold text-text">{inl(c)}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {b.rows.slice(1).map((r, j) => (
                      <tr key={j}>{r.map((c, m) => <td key={m} className="px-3 py-2 align-top leading-relaxed">{inl(c)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case "para":
            return <p key={k} className="m-0">{inl(b.text)}</p>;
        }
      })}
    </div>
  );
}

function inline(s: string, linkTo: LinkTo): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /`([^`]+)`|\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const k = m.index;
    if (m[1] !== undefined) out.push(<code key={k} className="rounded border border-border px-1.5 py-px font-mono text-[13px] text-text">{m[1]}</code>);
    else if (m[2] !== undefined) out.push(<strong key={k} className="font-semibold text-text">{inline(m[2], linkTo)}</strong>);
    else if (m[3] !== undefined) out.push(<em key={k}>{m[3]}</em>);
    else {
      const [text, target] = [m[4], m[5]];
      const link = "font-medium text-accent underline decoration-accent/30 underline-offset-2 hover:decoration-accent";
      if (/^https?:\/\//.test(target)) {
        out.push(<a key={k} href={target} target="_blank" rel="noreferrer" className={link}>{text}<ExternalLink className="ml-0.5 inline size-3 align-[-1px]" /></a>);
      } else {
        const to = linkTo(target);
        if (!to) out.push(text);
        else if (to.href) out.push(<a key={k} href={to.href} className={link}>{text}</a>);
        else out.push(<button key={k} type="button" onClick={to.onClick} className={link}>{text}</button>);
      }
    }
    last = re.lastIndex;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}
