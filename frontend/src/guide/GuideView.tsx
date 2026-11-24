import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, BookOpen, GraduationCap, Presentation, Search } from "lucide-react";
import { Page, PageHeader, cn } from "../ui";
import { AUDIENCES, findPage, pages, resolveLink, searchPages, type Audience, type GuidePage } from "./content";
import { GuideMarkdown, type LinkTo } from "./GuideMarkdown";

/**
 * The help centre: an index of both guides with search, and a reader with the
 * page list on the left and "On this page" on the right. Used in the teacher
 * area (#/guide…), on the public #/help page and inside the student app, which
 * moves between pages with a callback instead of the address bar.
 */

export interface GuideNav {
  /** Address-bar navigation (teacher area, public page). */
  href?: (audience: Audience, slug?: string) => string;
  /** In-app navigation (student app). */
  go?: (audience: Audience, slug?: string) => void;
}

const ICON = { student: GraduationCap, teacher: Presentation } as const;

function linkProps(nav: GuideNav, audience: Audience, slug?: string) {
  return nav.href ? { href: nav.href(audience, slug) } : { onClick: () => nav.go?.(audience, slug) };
}

function GuideLink({ nav, audience, slug, className, children, current }: {
  nav: GuideNav; audience: Audience; slug?: string; className?: string; children: React.ReactNode; current?: boolean;
}) {
  const p = linkProps(nav, audience, slug);
  return p.href
    ? <a href={p.href} className={className} aria-current={current ? "page" : undefined}>{children}</a>
    : <button type="button" onClick={p.onClick} className={cn("text-left", className)} aria-current={current ? "page" : undefined}>{children}</button>;
}

/** The guide home: search plus every page of each audience shown. */
export function GuideIndex({ nav, audiences = ["student", "teacher"] }: { nav: GuideNav; audiences?: Audience[] }) {
  const [q, setQ] = useState("");
  const hits = useMemo(() => searchPages(q).filter((p) => audiences.includes(p.audience)), [q, audiences]);
  return (
    <Page>
      <PageHeader title="Guide" description="How Scribelab works, step by step. Search, or pick a topic below." />
      <SearchBox value={q} onChange={setQ} className="mb-8 max-w-xl" />
      {q.trim() ? (
        <Results hits={hits} nav={nav} q={q} />
      ) : (
        <div className={cn("grid gap-6", audiences.length > 1 && "lg:grid-cols-2")}>
          {AUDIENCES.filter((a) => audiences.includes(a.id)).map((a) => {
            const Icon = ICON[a.id];
            return (
              <section key={a.id} className="rounded-xl border border-border bg-surface shadow-sm">
                <header className="flex items-start gap-3 border-b border-border px-5 py-4">
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent"><Icon className="size-[18px]" /></span>
                  <div>
                    <h2 className="text-[15px] font-semibold text-text">{a.label}</h2>
                    <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{a.about}</p>
                  </div>
                </header>
                <ul className="divide-y divide-border">
                  {pages(a.id).map((p) => (
                    <li key={p.slug}>
                      <GuideLink nav={nav} audience={a.id} slug={p.slug} className="group flex w-full items-center gap-3 px-5 py-3 transition-colors hover:bg-surface-2">
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-medium text-text">{p.title}</span>
                          <span className="block truncate text-[13px] text-muted">{p.summary}</span>
                        </span>
                        <ArrowRight className="size-4 shrink-0 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-accent" />
                      </GuideLink>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </Page>
  );
}

function Results({ hits, nav, q }: { hits: GuidePage[]; nav: GuideNav; q: string }) {
  if (!hits.length) return <p className="text-sm text-muted">No guide page mentions “{q}”. Try a shorter word, or browse the topics.</p>;
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-surface shadow-sm">
      {hits.map((p) => (
        <li key={`${p.audience}/${p.slug}`}>
          <GuideLink nav={nav} audience={p.audience} slug={p.slug} className="flex w-full items-center gap-3 px-5 py-3 hover:bg-surface-2">
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium text-text">{p.title}</span>
              <span className="block truncate text-[13px] text-muted">{p.summary}</span>
            </span>
            <span className="shrink-0 text-xs text-faint">{AUDIENCES.find((a) => a.id === p.audience)!.label}</span>
          </GuideLink>
        </li>
      ))}
    </ul>
  );
}

function SearchBox({ value, onChange, className }: { value: string; onChange: (v: string) => void; className?: string }) {
  return (
    <label className={cn("relative block", className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="Search the guide" aria-label="Search the guide"
        className="h-10 w-full rounded-lg border border-border bg-surface pl-9 pr-3 text-sm text-text shadow-sm outline-none placeholder:text-faint hover:border-border-strong focus:border-accent focus:ring-3 focus:ring-accent/15" />
    </label>
  );
}

/** One guide page with the page list and "On this page". */
export function GuideReader({ audience, slug, hash, nav, audiences = ["student", "teacher"] }: {
  audience: Audience; slug?: string; hash?: string; nav: GuideNav; audiences?: Audience[];
}) {
  const page = findPage(audience, slug);
  const list = pages(audience);
  const at = page ? list.indexOf(page) : -1;
  const [q, setQ] = useState("");
  const hits = useMemo(() => (q.trim() ? searchPages(q, audience) : list), [q, audience, list]);

  useEffect(() => {
    const el = hash ? document.getElementById(hash) : null;
    if (el) el.scrollIntoView({ block: "start" });
    else window.scrollTo({ top: 0 });
  }, [audience, slug, hash]);

  const linkTo: LinkTo = (target) => {
    const r = resolveLink(audience, target);
    if (!r) return null;
    return nav.href ? { href: nav.href(r.audience, r.slug) } : { onClick: () => nav.go?.(r.audience, r.slug) };
  };

  if (!page) return <Page><p className="text-sm text-muted">That guide page does not exist. <GuideLink nav={nav} audience={audience} className="font-medium text-accent">Open the guide</GuideLink></p></Page>;

  return (
    <div className="mx-auto grid w-full max-w-[1280px] gap-8 px-4 pb-24 pt-6 sm:px-6 sm:pt-8 lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[220px_minmax(0,1fr)_200px]">
      <aside className="lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:self-start lg:overflow-y-auto">
        {audiences.length > 1 && (
          <div className="mb-3 grid grid-cols-2 gap-0.5 rounded-lg border border-border bg-surface-2 p-0.5" role="tablist" aria-label="Guide">
            {audiences.map((a) => (
              <GuideLink key={a} nav={nav} audience={a} slug={findPage(a)?.slug} current={a === audience}
                className={cn("rounded-md px-2 py-1 text-center text-[12.5px] font-medium transition-colors",
                  a === audience ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text")}>
                {a === "student" ? "Students" : "Teachers"}
              </GuideLink>
            ))}
          </div>
        )}
        <SearchBox value={q} onChange={setQ} className="mb-3" />
        <nav aria-label="Guide pages">
          <ul className="grid gap-px">
            {hits.map((p) => (
              <li key={p.slug}>
                <GuideLink nav={nav} audience={audience} slug={p.slug} current={p.slug === page.slug}
                  className={cn("block w-full rounded-md px-2.5 py-1.5 text-[13.5px] transition-colors",
                    p.slug === page.slug ? "bg-surface-3 font-medium text-text" : "text-muted hover:bg-surface-2 hover:text-text")}>
                  {p.title}
                </GuideLink>
              </li>
            ))}
            {!hits.length && <li className="px-2.5 py-1.5 text-[13px] text-faint">No page matches.</li>}
          </ul>
        </nav>
      </aside>

      <article className="min-w-0 max-w-[720px]">
        <p className="mb-2 flex items-center gap-1.5 text-[13px] text-faint"><BookOpen className="size-3.5" />{AUDIENCES.find((a) => a.id === audience)!.label}</p>
        <h1 className="text-[28px] font-semibold leading-tight tracking-[-0.02em] text-text">{page.title}</h1>
        {page.summary && <p className="mt-2 text-[17px] leading-relaxed text-muted">{page.summary}</p>}
        <GuideMarkdown markdown={page.body} linkTo={linkTo} className="mt-8" />
        <nav className="mt-12 grid gap-3 border-t border-border pt-6 sm:grid-cols-2" aria-label="Next and previous">
          {at > 0 ? (
            <GuideLink nav={nav} audience={audience} slug={list[at - 1].slug} className="group rounded-xl border border-border px-4 py-3 transition-colors hover:border-accent/40">
              <span className="flex items-center gap-1 text-xs text-faint"><ArrowLeft className="size-3" />Previous</span>
              <span className="mt-0.5 block text-sm font-medium text-text group-hover:text-accent">{list[at - 1].title}</span>
            </GuideLink>
          ) : <span />}
          {at < list.length - 1 && (
            <GuideLink nav={nav} audience={audience} slug={list[at + 1].slug} className="group rounded-xl border border-border px-4 py-3 text-right transition-colors hover:border-accent/40">
              <span className="flex items-center justify-end gap-1 text-xs text-faint">Next<ArrowRight className="size-3" /></span>
              <span className="mt-0.5 block text-sm font-medium text-text group-hover:text-accent">{list[at + 1].title}</span>
            </GuideLink>
          )}
        </nav>
      </article>

      {page.headings.length > 1 && (
        <aside className="hidden xl:block">
          <div className="sticky top-20">
            <p className="mb-2 text-xs font-medium text-faint">On this page</p>
            <ul className="grid gap-1 border-l border-border">
              {page.headings.map((h) => (
                <li key={h.id}>
                  <button type="button" onClick={() => document.getElementById(h.id)?.scrollIntoView({ behavior: "smooth", block: "start" })}
                    className="-ml-px border-l border-transparent py-0.5 pl-3 text-left text-[13px] text-muted hover:border-accent hover:text-text">
                    {h.text}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      )}
    </div>
  );
}
