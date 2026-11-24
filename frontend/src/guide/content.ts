/**
 * The in-app guides: Markdown files under ./pages/<audience>/<slug>.md, bundled at
 * build time. Each starts with front matter (title, summary, order, keywords).
 * Links between pages use a bare slug ("attendance") and resolve within the
 * same audience; "student/attendance" or "teacher/live-view" cross over.
 */

export type Audience = "student" | "teacher";
export const AUDIENCES: { id: Audience; label: string; about: string }[] = [
  { id: "student", label: "Student guide", about: "Signing in, solving lab questions, competitions, the learning lab, Sandbox Labs and attendance." },
  { id: "teacher", label: "Teacher guide", about: "Setting up, making labs, watching a class live, reading the review timeline, competitions, Sandbox Labs and Roll Call." },
];

export interface GuidePage {
  audience: Audience;
  slug: string;
  title: string;
  summary: string;
  order: number;
  keywords: string[];
  body: string;
  headings: { id: string; text: string }[];
}

const files = import.meta.glob("./pages/*/*.md", { query: "?raw", import: "default", eager: true }) as Record<string, string>;

export function headingId(text: string): string {
  return text.toLowerCase().replace(/[`*_]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function parsePage(path: string, raw: string): GuidePage | null {
  const m = path.match(/\.\/pages\/(student|teacher)\/([\w-]+)\.md$/);
  if (!m) return null;
  const text = raw.replace(/\r\n/g, "\n");
  const fm = text.match(/^---\n([\s\S]*?)\n---\n?/);
  const meta: Record<string, string> = {};
  for (const line of (fm?.[1] ?? "").split("\n")) {
    const kv = line.match(/^(\w+):\s*(.*)$/);
    if (kv) meta[kv[1]] = kv[2].trim();
  }
  const body = fm ? text.slice(fm[0].length) : text;
  const headings = [...body.matchAll(/^##\s+(.+)$/gm)].map((h) => ({ id: headingId(h[1]), text: h[1].replace(/[`*]/g, "") }));
  return {
    audience: m[1] as Audience,
    slug: m[2],
    title: meta.title || m[2],
    summary: meta.summary || "",
    order: Number(meta.order) || 99,
    keywords: (meta.keywords || "").replace(/^\[|\]$/g, "").split(",").map((k) => k.trim()).filter(Boolean),
    body,
    headings,
  };
}

const all = Object.entries(files).map(([p, raw]) => parsePage(p, raw)).filter((p): p is GuidePage => !!p);

export function pages(audience: Audience): GuidePage[] {
  return all.filter((p) => p.audience === audience).sort((a, b) => a.order - b.order || a.title.localeCompare(b.title));
}

export function findPage(audience: Audience, slug?: string): GuidePage | undefined {
  const list = pages(audience);
  return slug ? list.find((p) => p.slug === slug) : list[0];
}

/** A link target inside a page: "slug", "audience/slug", optionally with "#heading". */
export function resolveLink(from: Audience, target: string): { audience: Audience; slug: string; hash?: string } | null {
  const [path, hash] = target.split("#");
  const m = path.match(/^(?:(student|teacher)\/)?([\w-]+)$/);
  if (!m) return null;
  const audience = (m[1] as Audience | undefined) ?? from;
  return all.some((p) => p.audience === audience && p.slug === m[2]) ? { audience, slug: m[2], hash } : null;
}

/** Pages matching every word of the query, title and keyword hits first. */
export function searchPages(q: string, audience?: Audience): GuidePage[] {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const scored = all
    .filter((p) => !audience || p.audience === audience)
    .map((p) => {
      const head = `${p.title} ${p.summary} ${p.keywords.join(" ")}`.toLowerCase();
      const body = p.body.toLowerCase();
      if (!words.every((w) => head.includes(w) || body.includes(w))) return null;
      return { p, score: words.filter((w) => head.includes(w)).length };
    })
    .filter((x): x is { p: GuidePage; score: number } => !!x);
  return scored.sort((a, b) => b.score - a.score || a.p.order - b.p.order).map((x) => x.p);
}
