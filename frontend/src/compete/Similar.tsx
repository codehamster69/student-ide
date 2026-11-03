import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ClipboardPaste, Code2, ExternalLink, Info, Keyboard, MessagesSquare, RefreshCw, ScanSearch, X } from "lucide-react";
import { Badge, Button, Card, Spinner, cn, item, pop, stagger } from "../ui";
import { AuthError, get } from "../review/api";
import { Skeleton } from "../review/bits";
import { LanguageDot } from "../teach/bits";
import type { Language } from "../teach/api";
import { href } from "../routes";

// Similar submissions in a competition (backend: compete.py + similarity.py).
// A pointer for a conversation, never a verdict: the page never says "copied",
// never ranks students, and nothing here reaches the board or a score.

interface Side {
  submission_id: string;
  student_id: string;
  handle: string;
  language: Language;
  session_id: string;
  passed: number;
  total: number;
  auto: boolean;
}

interface Pair {
  a: Side;
  b: Side;
  similarity: number;
  share_a: number;
  share_b: number;
  matched_tokens: number;
  longest_run: number;
}

interface Report {
  lab_id: string;
  title: string;
  language: string;
  settings: { k: number; window: number; min_match: number; min_tokens: number; common_share: number; report_at: number };
  questions: { id: string; title: string; n_compared: number; n_students: number; pairs: Pair[] }[];
}

interface PairDetail extends Omit<Pair, "a" | "b"> {
  a: Side & { code: string; created_at: number; typed_chars: number; pasted_chars: number; n_pastes: number };
  b: PairDetail["a"];
  regions: { a: [number, number]; b: [number, number]; tokens: number }[];
}

/** Show from: 0.5 by default; 0.3 lists everything the server reports. */
const LEVELS = [0.5, 0.3] as const;
const HUES = ["var(--ch-identity)", "var(--ch-pairs)", "var(--ch-process)", "var(--gold)", "var(--syn-function)", "var(--syn-constant)"];

const pct = (x: number) => `${Math.round(x * 100)}%`;

/** #/teach/similar/<lab id>: pairs of similar submissions per question, and a side-by-side view. */
export function Similar({ id, onAuthLost }: { id: string; onAuthLost: () => void }) {
  const [rep, setRep] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [from, setFrom] = useState<number>(LEVELS[0]);
  const [open, setOpen] = useState<{ q: string; pair: Pair } | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    get<Report>(`/api/teach/competitions/${id}/similarity`).then(setRep, (e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)))
      .finally(() => setLoading(false));
  }, [id, onAuthLost]);
  useEffect(load, [load]);

  if (!rep) {
    return (
      <div className="mx-auto max-w-[1240px] px-5 pt-8">
        {error ? <Card className="p-6 text-sm text-danger">{error}</Card> : <Skeleton className="h-64 w-full rounded-2xl" />}
      </div>
    );
  }

  const shown = rep.questions.map((q) => ({ ...q, pairs: q.pairs.filter((p) => p.similarity >= from) }));
  const total = shown.reduce((n, q) => n + q.pairs.length, 0);

  return (
    <motion.div variants={stagger(0.05)} initial="initial" animate="animate" className="mx-auto max-w-[1240px] px-5 pb-20 pt-6">
      <motion.a variants={item} href={href.lab(id)} className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted hover:text-text">
        <ArrowLeft className="size-4" /> Back to the competition
      </motion.a>
      <motion.div variants={item} className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
            <ScanSearch className="size-3.5" /> Similar submissions worth a look
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text">{rep.title}</h1>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-border bg-surface p-0.5 shadow-sm" role="radiogroup" aria-label="Show pairs from">
            {LEVELS.map((l) => (
              <button key={l} role="radio" aria-checked={from === l} onClick={() => setFrom(l)}
                className={cn("h-7 rounded-md px-2.5 text-xs font-medium transition-colors", from === l ? "bg-surface-3 text-text" : "text-muted hover:text-text")}>
                {l === LEVELS[0] ? `Strong overlap (${pct(l)}+)` : `Everything from ${pct(l)}`}
              </button>
            ))}
          </div>
          <Button size="sm" onClick={load} disabled={loading}>{loading ? <Spinner className="size-3.5" /> : <RefreshCw className="size-3.5" />} Refresh</Button>
        </div>
      </motion.div>

      <motion.div variants={item}>
        <Card className="mb-6 flex gap-3 bg-surface-2/60 px-5 py-4 text-[13px] leading-relaxed text-muted shadow-none">
          <MessagesSquare className="mt-0.5 size-4 shrink-0 text-accent" />
          <div className="grid gap-1.5">
            <p className="text-text">
              A similar pair is a reason to talk with both students, never proof that anyone copied. Nothing on this page changes a score,
              and students never see it.
            </p>
            <p>
              Each student's last submission on a question is compared with everyone else's in the same language (C with C++), ignoring
              names, layout, comments, string texts and the starter code. Code most of the class wrote the same way is left out too.
              Short answers to small problems often look alike simply because there are few ways to write them, and students who
              learned together write alike. Look at what matches, and at how the code got into the editor (typed or pasted), before you
              read anything into it.
            </p>
          </div>
        </Card>
      </motion.div>

      <div className="grid gap-5">
        {shown.map((q, qi) => (
          <motion.section key={q.id} variants={item}>
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <h2 className="text-sm font-semibold text-text">
                <span className="mr-2 font-mono text-xs text-faint">Q{qi + 1}</span>{q.title}
              </h2>
              <span className="text-xs text-muted">{q.n_students} student{q.n_students === 1 ? "" : "s"} compared</span>
            </div>
            {q.pairs.length === 0 ? (
              <p className="rounded-xl border border-dashed border-border px-4 py-3 text-[13px] text-muted">
                {q.n_compared < 2 ? "Not enough submissions to compare yet." : "No pair stands out on this question."}
              </p>
            ) : (
              <ul className="grid gap-1.5">
                {q.pairs.map((p) => (
                  <li key={p.a.submission_id + p.b.submission_id}>
                    <button onClick={() => setOpen({ q: q.title, pair: p })}
                      className="flex w-full items-center gap-4 rounded-xl border border-border bg-surface px-4 py-2.5 text-left shadow-sm transition-[border-color,box-shadow] hover:border-accent/40 hover:shadow-md">
                      <Who s={p.a} />
                      <span className="text-faint">and</span>
                      <Who s={p.b} />
                      <span className="ml-auto flex items-center gap-3">
                        <span className="hidden text-xs text-muted sm:inline">longest common stretch {p.longest_run} tokens</span>
                        <Meter value={p.similarity} />
                        <Code2 className="size-4 text-faint" />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </motion.section>
        ))}
        {total === 0 && rep.questions.some((q) => q.n_compared > 1) && from === LEVELS[0] && (
          <p className="text-center text-xs text-faint">Nothing above {pct(from)}. "Everything from {pct(LEVELS[1])}" lists weaker overlaps too.</p>
        )}
      </div>

      <p className="mt-8 flex items-start justify-center gap-1.5 text-center text-xs text-faint">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        Token fingerprints (winnowing, {rep.settings.k}-token windows) pick the pairs; greedy string tiling with runs of at least {rep.settings.min_match} tokens
        measures them. Programs under {rep.settings.min_tokens} tokens of their own are not compared.
      </p>

      <AnimatePresence>
        {open && <PairView labId={id} question={open.q} pair={open.pair} onClose={() => setOpen(null)} onAuthLost={onAuthLost} />}
      </AnimatePresence>
    </motion.div>
  );
}

function Who({ s }: { s: Side }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <strong className="truncate text-sm font-semibold text-text">{s.handle}</strong>
      {s.handle !== s.student_id && <span className="hidden font-mono text-[11px] text-faint md:inline">{s.student_id}</span>}
      <LanguageDot language={s.language} />
    </span>
  );
}

function Meter({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-2" title="Share of both programs inside common stretches">
      <span className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-3">
        <span className="block h-full rounded-full bg-accent" style={{ width: pct(value) }} />
      </span>
      <span className="w-10 text-right text-sm font-semibold tabular-nums text-text">{pct(value)}</span>
    </span>
  );
}

function PairView({ labId, question, pair, onClose, onAuthLost }: {
  labId: string; question: string; pair: Pair; onClose: () => void; onAuthLost: () => void;
}) {
  const [d, setD] = useState<PairDetail | null>(null);
  const [error, setError] = useState("");
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    get<PairDetail>(`/api/teach/competitions/${labId}/similarity/${pair.a.submission_id}/${pair.b.submission_id}`)
      .then(setD, (e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)));
  }, [labId, pair, onAuthLost]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <motion.div variants={pop} initial="initial" animate="animate" exit="exit" onClick={(e) => e.stopPropagation()}
        role="dialog" aria-modal="true" aria-label="Two similar submissions side by side"
        className="flex max-h-[92vh] w-full max-w-[1320px] flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-xl">
        <div className="flex items-center gap-3 border-b border-border px-5 py-3">
          <ScanSearch className="size-4 text-accent" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-text">{question}</p>
            <p className="text-xs text-muted">
              {d ? `${pct(d.similarity)} in common · ${d.regions.length} matching stretch${d.regions.length === 1 ? "" : "es"}, the longest ${d.longest_run} tokens`
                : "Loading…"}
            </p>
          </div>
          <Button variant="ghost" size="icon" className="ml-auto" onClick={onClose} aria-label="Close"><X className="size-4" /></Button>
        </div>
        {error && <p className="m-5 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
        {!d && !error && <div className="grid place-items-center p-16"><Spinner className="size-5" /></div>}
        {d && (
          <div className="grid min-h-0 flex-1 grid-cols-1 overflow-auto md:grid-cols-2 md:divide-x md:divide-border">
            {(["a", "b"] as const).map((k) => (
              <CodeSide key={k} s={d[k]} share={k === "a" ? d.share_a : d.share_b}
                ranges={d.regions.map((r) => r[k])} hover={hover} onHover={setHover} />
            ))}
          </div>
        )}
        <p className="border-t border-border px-5 py-2.5 text-xs text-faint">
          Matching stretches share a colour on both sides; point at one to find its partner. Names, layout and comments are ignored when
          matching, so a stretch can look different and still match.
        </p>
      </motion.div>
    </motion.div>
  );
}

function CodeSide({ s, share, ranges, hover, onHover }: {
  s: PairDetail["a"]; share: number; ranges: [number, number][]; hover: number | null; onHover: (i: number | null) => void;
}) {
  const parts = useMemo(() => {
    const order = ranges.map((r, i) => ({ r, i })).sort((x, y) => x.r[0] - y.r[0]);
    const out: { text: string; region: number | null }[] = [];
    let at = 0;
    for (const { r, i } of order) {
      if (r[0] < at) continue;
      if (r[0] > at) out.push({ text: s.code.slice(at, r[0]), region: null });
      out.push({ text: s.code.slice(r[0], r[1]), region: i });
      at = r[1];
    }
    out.push({ text: s.code.slice(at), region: null });
    return out;
  }, [s.code, ranges]);
  const typedOrPasted = s.typed_chars + s.pasted_chars;

  return (
    <div className="flex min-w-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-surface-2/60 px-4 py-2.5">
        <strong className="text-sm font-semibold text-text">{s.handle}</strong>
        {s.handle !== s.student_id && <span className="font-mono text-[11px] text-faint">{s.student_id}</span>}
        <LanguageDot language={s.language} />
        <Badge className="h-5 px-2 text-[11px]">{s.passed}/{s.total} tests</Badge>
        {s.auto && <Badge className="h-5 px-2 text-[11px]">Handed in at the bell</Badge>}
        <span className="ml-auto text-xs text-muted">{pct(share)} of this program matches</span>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border px-4 py-2 text-xs text-muted">
        <span className="flex items-center gap-1.5"><Keyboard className="size-3.5" />{s.typed_chars.toLocaleString()} characters typed</span>
        <span className={cn("flex items-center gap-1.5", s.pasted_chars > 0 && "text-text")}>
          <ClipboardPaste className="size-3.5" />
          {s.n_pastes ? `${s.pasted_chars.toLocaleString()} pasted in ${s.n_pastes} paste${s.n_pastes === 1 ? "" : "s"}` : "nothing pasted"}
        </span>
        {typedOrPasted === 0 && <span>no editor activity recorded for this submission</span>}
        <a href={href.session(s.session_id)} className="ml-auto inline-flex items-center gap-1 text-accent hover:underline">
          Session timeline <ExternalLink className="size-3" />
        </a>
      </div>
      <pre className="m-0 min-h-0 flex-1 overflow-auto px-4 py-3 font-mono text-[12.5px] leading-relaxed text-text">
        {parts.map((p, i) => p.region === null ? <Fragment key={i}>{p.text}</Fragment> : (
          <mark key={i} onMouseEnter={() => onHover(p.region)} onMouseLeave={() => onHover(null)}
            className="rounded-sm text-text transition-[background-color,box-shadow]"
            style={{
              background: `color-mix(in srgb, ${HUES[p.region % HUES.length]} ${hover === p.region ? 34 : 16}%, transparent)`,
              boxShadow: hover === p.region ? `0 0 0 1px ${HUES[p.region % HUES.length]}` : undefined,
            }}>
            {p.text}
          </mark>
        ))}
      </pre>
    </div>
  );
}
