import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, Check, ExternalLink, FlaskConical, Globe, Link2, Search, X } from "lucide-react";
import { Badge, Button, Card, Field, Input, Spinner, cn, spring } from "../ui";
import { AuthError, get } from "../review/api";
import { Skeleton } from "../review/bits";
import { LANGUAGES, type Language, type Provider, type SourceCategory, type SourcePreview, type SourceSummary } from "./api";

const DIFF_TONE: Record<string, "success" | "warn" | "danger"> = { beginner: "success", easy: "success", medium: "warn", hard: "danger" };
const STATUS_CHIP: Record<Provider["status"], [string, string]> = {
  live: ["Live", "bg-success-soft text-success"],
  bundled: ["Dataset", "bg-accent-soft text-accent"],
  link_only: ["Link only", "bg-surface-2 text-faint"],
};

/**
 * Pick a ready-made question from a platform. Live sources are fetched when
 * the teacher looks (and once more as the pick is added); dataset sources are
 * openly licensed copies shipped with the app. Either way the pick is copied
 * into the lab as an ordinary question.
 */
export function SourcePicker({ language, onImport, onLink, onClose, onAuthLost }: {
  language: Language;
  onImport: (provider: string, ref: string) => Promise<boolean>;
  onLink: (provider: string, url: string, title: string) => Promise<boolean>;
  onClose: () => void;
  onAuthLost: () => void;
}) {
  const [providers, setProviders] = useState<Provider[] | null>(null);
  const [pid, setPid] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    get<Provider[]>("/api/teach/sources").then((ps) => { setProviders(ps); setPid((cur) => cur || ps[0]?.id || ""); })
      .catch((e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)));
  }, [onAuthLost]);

  const p = providers?.find((x) => x.id === pid);

  return (
    <Card className="overflow-hidden border-accent/40 ring-4 ring-accent/10">
      <div className="flex items-center gap-3 border-b border-border px-5 py-4">
        <span className="grid size-8 place-items-center rounded-lg bg-accent text-accent-fg"><Globe className="size-4" /></span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text">Add a question from a platform</h3>
          <p className="text-xs text-muted">Only sources whose licence allows it, for this lab's language ({LANGUAGES[language].label}). Test cases come along where the source has them, and stay optional.</p>
        </div>
        <Button variant="ghost" size="icon" className="ml-auto" onClick={onClose} aria-label="Close"><X className="size-4" /></Button>
      </div>

      <div className="flex gap-1.5 overflow-x-auto border-b border-border px-5 py-3" role="tablist" aria-label="Platform">
        {(providers ?? []).map((x) => (
          <button key={x.id} role="tab" aria-selected={pid === x.id} onClick={() => setPid(x.id)}
            className={cn("relative flex h-8 shrink-0 items-center gap-1.5 rounded-lg px-3 text-[13px] font-medium transition-colors",
              pid === x.id ? "text-text" : "text-muted hover:text-text")}>
            {pid === x.id && <motion.span layoutId="source-tab" transition={spring} className="absolute inset-0 rounded-lg bg-surface-3" />}
            <span className="relative">{x.name}</span>
            <span className={cn("relative rounded-full px-1.5 text-[10px] font-semibold uppercase tracking-wide", STATUS_CHIP[x.status][1])}>
              {STATUS_CHIP[x.status][0]}
            </span>
          </button>
        ))}
        {!providers && <Skeleton className="h-8 w-80 rounded-lg" />}
      </div>

      {error && <p className="mx-5 mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{error}</p>}
      {p && (p.can_browse ? (
        <>
          <LiveBrowser key={p.id + language} provider={p} language={language} onImport={onImport} onAuthLost={onAuthLost} />
          {p.can_link && (
            <details className="border-t border-border">
              <summary className="cursor-pointer px-5 py-3 text-xs font-medium text-muted hover:text-text">
                Not in the list? Link any other {p.name} problem and write it yourself
              </summary>
              <LinkOnly key={p.id} provider={p} onLink={onLink} compact />
            </details>
          )}
        </>
      ) : <LinkOnly key={p.id} provider={p} onLink={onLink} />)}
    </Card>
  );
}

function LiveBrowser({ provider, language, onImport, onAuthLost }: {
  provider: Provider; language: Language; onImport: (provider: string, ref: string) => Promise<boolean>; onAuthLost: () => void;
}) {
  const [cats, setCats] = useState<SourceCategory[] | null>(null);
  const [cat, setCat] = useState("");
  const [query, setQuery] = useState("");
  const [list, setList] = useState<SourceSummary[] | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [preview, setPreview] = useState<SourcePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const base = `/api/teach/sources/${provider.id}`;

  const fail = (e: unknown) => (e instanceof AuthError ? onAuthLost() : setError((e as Error).message));

  useEffect(() => {
    get<SourceCategory[]>(`${base}/categories?language=${language}`)
      .then((cs) => { setCats(cs); setCat((cur) => cur || cs[0]?.id || "all"); }, fail);
  }, [base, language]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setList(null);
    if (!cat && !query) return; // wait for the categories, then show the first one
    const t = window.setTimeout(() => {
      const qs = new URLSearchParams({ language, ...(query ? { q: query } : cat !== "all" ? { category: cat } : {}) });
      get<SourceSummary[]>(`${base}/questions?${qs}`).then(setList, fail);
    }, query ? 250 : 0);
    return () => window.clearTimeout(t);
  }, [base, language, cat, query]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setPreview(null);
    if (picked) get<SourcePreview>(`${base}/questions/${picked}?language=${language}`).then(setPreview, fail);
  }, [base, language, picked]); // eslint-disable-line react-hooks/exhaustive-deps

  if (picked) {
    return (
      <div className="px-5 py-4">
        <button onClick={() => setPicked(null)} className="mb-3 inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-text">
          <ArrowLeft className="size-3.5" /> Back to the list
        </button>
        {error && <p className="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{error}</p>}
        {!preview ? <Skeleton className="h-48 w-full rounded-xl" /> : (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="grid gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="text-base font-semibold text-text">{preview.title}</h4>
              <Badge tone={preview.tests.length ? "accent" : "neutral"} className="h-5 px-2 text-[11px]">
                <FlaskConical className="size-3" />{preview.tests.length ? `${preview.tests.length} tests` : "no tests"}
              </Badge>
              {preview.source.url && (
                <a href={preview.source.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-accent hover:underline">
                  Open original <ExternalLink className="size-3" />
                </a>
              )}
            </div>
            <div className="max-h-56 overflow-auto whitespace-pre-line rounded-lg border border-border bg-surface-2/60 px-4 py-3 text-[13px] leading-relaxed text-muted">{preview.prompt}</div>
            {preview.starter_code && (
              <pre className="max-h-32 overflow-auto rounded-lg border border-border bg-surface-2 px-3 py-2 font-mono text-[11.5px] text-muted">{preview.starter_code}</pre>
            )}
            {preview.notes.map((n) => <p key={n} className="rounded-lg bg-warn-soft px-3 py-2 text-xs text-warn">{n}</p>)}
            <p className="text-[11px] text-faint">{preview.source.attribution}. You can edit everything after adding it.</p>
            <div className="flex justify-end">
              <Button variant="primary" size="sm" disabled={busy}
                onClick={async () => { setBusy(true); await onImport(provider.id, picked); setBusy(false); }}>
                {busy ? <Spinner className="size-3.5" /> : <Check className="size-3.5" />} Add to lab
              </Button>
            </div>
          </motion.div>
        )}
      </div>
    );
  }

  return (
    <div className="grid gap-3 px-5 py-4">
      <p className="text-xs text-muted">{provider.about}</p>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" />
        <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name" className="h-9 pl-9 text-[13px]" aria-label="Search questions" />
      </div>
      <div className={cn("grid gap-2", query && "opacity-40")}>
        {groupCategories(cats ?? []).map(([group, cs]) => (
          <div key={group} className="flex flex-wrap items-center gap-1.5" role="group" aria-label={group}>
            <span className="w-16 shrink-0 text-[10.5px] font-semibold uppercase tracking-wide text-faint">{group}</span>
            {cs.map((c) => (
              <button key={c.id} onClick={() => { setQuery(""); setCat(c.id); }} aria-pressed={cat === c.id && !query}
                className={cn("h-7 rounded-full border px-2.5 text-xs transition-colors",
                  cat === c.id && !query ? "border-accent bg-accent-soft text-accent" : "border-border bg-surface text-muted hover:text-text")}>
                {c.label} <span className="tabular-nums text-faint">{c.count}</span>
              </button>
            ))}
          </div>
        ))}
        {!cats && !error && <Skeleton className="h-7 w-72 rounded-full" />}
      </div>
      {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{error}</p>}
      <ul className="grid max-h-80 gap-1 overflow-auto" aria-label="Questions">
        {!list && !error && Array.from({ length: 5 }, (_, i) => <li key={i}><Skeleton className="h-10 w-full rounded-lg" /></li>)}
        {list?.length === 0 && <li className="py-6 text-center text-xs text-faint">Nothing matches.</li>}
        {list?.length === 400 && <li className="px-3 pb-1 text-[11px] text-faint">Showing the first 400; search or pick a narrower topic to see the rest.</li>}
        <AnimatePresence initial={false}>
          {list?.map((s, i) => (
            <motion.li key={s.ref} initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { delay: Math.min(i, 12) * 0.015 } }}>
              <button onClick={() => setPicked(s.ref)}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors hover:bg-surface-2">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium text-text">{s.title}</span>
                  {s.categories.length > 0 && <span className="block truncate text-[11px] text-faint">{s.categories.join(", ")}</span>}
                </span>
                {s.blurb && /^\d+$/.test(s.blurb) && <span className="font-mono text-[11px] tabular-nums text-faint" title="Codeforces rating">{s.blurb}</span>}
                {s.difficulty && <Badge tone={DIFF_TONE[s.difficulty] ?? "neutral"} className="h-5 px-2 text-[11px] capitalize">{s.difficulty}</Badge>}
              </button>
            </motion.li>
          ))}
        </AnimatePresence>
      </ul>
    </div>
  );
}

/** Topic chips first, then difficulty, whatever prefixes a provider uses. */
function groupCategories(cats: SourceCategory[]): [string, SourceCategory[]][] {
  const topics = cats.filter((c) => /^(topic|concept):/.test(c.id));
  const levels = cats.filter((c) => /^(level|difficulty):/.test(c.id));
  const other = cats.filter((c) => !topics.includes(c) && !levels.includes(c));
  return ([["Topic", topics], ["Level", levels], ["Other", other]] as [string, SourceCategory[]][]).filter(([, cs]) => cs.length);
}

function LinkOnly({ provider, onLink, compact }: {
  provider: Provider; onLink: (provider: string, url: string, title: string) => Promise<boolean>; compact?: boolean;
}) {
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form className="grid gap-3 px-5 py-4" onSubmit={async (e) => {
      e.preventDefault(); setBusy(true);
      if (await onLink(provider.id, url, title)) { setUrl(""); setTitle(""); }
      setBusy(false);
    }}>
      {!compact && <div className="rounded-xl border border-border bg-surface-2/60 px-4 py-3 text-[13px] text-muted">
        <p className="font-medium text-text">{provider.name} can't be fetched automatically</p>
        <p className="mt-1">{provider.about}</p>
        {provider.terms_url && (
          <a href={provider.terms_url} target="_blank" rel="noreferrer" className="mt-1.5 inline-flex items-center gap-1 text-xs text-accent hover:underline">
            {provider.name} terms <ExternalLink className="size-3" />
          </a>
        )}
      </div>}
      <div className="grid gap-3 sm:grid-cols-[1.4fr_1fr]">
        <Field label={`${provider.name} link`}>
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={`https://${provider.hosts[0]}/problems/...`} className="h-9 text-[13px]" required />
        </Field>
        <Field label="Title">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Two sum" maxLength={120} className="h-9 text-[13px]" required />
        </Field>
      </div>
      <p className="text-xs text-faint">The link is kept with the question for reference. Write the prompt and any tests yourself in the next step.</p>
      <div className="flex justify-end">
        <Button type="submit" size="sm" variant="primary" disabled={busy || !url.trim() || !title.trim()}>
          {busy ? <Spinner className="size-3.5" /> : <Link2 className="size-3.5" />} Add linked question
        </Button>
      </div>
    </form>
  );
}
