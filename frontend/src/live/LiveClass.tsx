import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import {
  Activity, ArrowLeft, ArrowUpDown, CheckCircle2, CircleAlert, ClipboardPaste, Eye, FlaskConical, Info, MessagesSquare,
  Play, Radio, Trophy, Users,
} from "lucide-react";
import { Badge, Button, Card, LiveDot, cn, item, spring, stagger } from "../ui";
import { AuthError, get, token } from "../review/api";
import { Skeleton } from "../review/bits";
import { LanguageBadge } from "../teach/bits";
import { STATE, ago, leaveView, type LiveClass as LiveClassData, type LiveLab, type LiveState, type LiveStudent } from "./api";
import { href } from "../routes";

const POLL_MS = 3000;

/** #/live: the open labs a teacher can watch. */
export function LiveLabs({ onAuthLost }: { onAuthLost: () => void }) {
  const [labs, setLabs] = useState<LiveLab[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = () => get<LiveLab[]>("/api/live/labs").then(setLabs, (e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)));
    void load();
    const t = window.setInterval(load, 10_000);
    return () => window.clearInterval(t);
  }, [onAuthLost]);

  return (
    <motion.div variants={stagger(0.06)} initial="initial" animate="animate" className="mx-auto max-w-[1100px] px-5 pb-20 pt-8">
      <motion.div variants={item} className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-text">Live</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Follow an open lab while it runs: who is working on which question, their runs and test checks, and anything
          the review timeline has picked up so far. Students always see a notice while you are watching.
        </p>
      </motion.div>
      {error && <Card className="mb-4 p-6 text-sm text-danger">{error}</Card>}
      {!labs && !error && <div className="grid gap-3">{[0, 1].map((i) => <Skeleton key={i} className="h-20 w-full rounded-2xl" />)}</div>}
      {labs && labs.length === 0 && (
        <Card variants={item} className="grid place-items-center gap-3 px-6 py-14 text-center">
          <span className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent"><Radio className="size-5" /></span>
          <p className="text-sm font-medium text-text">No lab is open right now</p>
          <p className="max-w-sm text-sm text-muted">Open a lab from the Labs tab when the class starts, then follow it here.</p>
          <Button className="mt-2" onClick={() => { location.hash = href.labs; }}>Go to labs</Button>
        </Card>
      )}
      <div className="grid gap-3">
        {labs?.map((l) => (
          <motion.a key={l.id} variants={item} href={href.liveLab(l.id)}
            className="group flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border bg-surface px-5 py-4 shadow-sm transition-shadow hover:shadow-md">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-[15px] font-semibold text-text">
                {l.title} <LanguageBadge language={l.language} />
                {l.kind === "competition" && <Badge tone="warn">Competition</Badge>}
              </p>
              <p className="mt-1 text-sm text-muted">
                {l.n_questions} question{l.n_questions === 1 ? "" : "s"} · {l.everyone ? "every student" : `${l.n_roster} on the roster`}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-2 text-sm text-text">
                <LiveDot tone={l.n_online ? "success" : "neutral"} live={l.n_online > 0} />
                <span className="tabular-nums font-medium">{l.n_online}</span>
                <span className="text-muted">connected</span>
              </span>
              <Button size="sm" variant="primary" tabIndex={-1}><Eye className="size-3.5" /> Watch</Button>
            </div>
          </motion.a>
        ))}
      </div>
    </motion.div>
  );
}

const ORDER: LiveState[] = ["typing", "active", "idle", "away", "offline", "submitted", "left", "not_started"];

/** #/live/l/<lab id>: one card per student, refreshed every few seconds. */
export function LiveClass({ id, onAuthLost }: { id: string; onAuthLost: () => void }) {
  const [data, setData] = useState<LiveClassData | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<LiveState | "moments" | null>(null);
  const [sort, setSort] = useState<"roll" | "recent">("roll");
  // Moments that appeared after the page was opened are marked "new" until clicked.
  const seen = useRef<Map<string, number> | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());

  const load = useCallback(() => get<LiveClassData>(`/api/live/labs/${id}`).then((next) => {
    setData(next);
    if (seen.current === null) {
      seen.current = new Map(next.students.map((s) => [s.student_id, s.moments]));
    } else {
      const add = next.students.filter((s) => s.moments > (seen.current!.get(s.student_id) ?? 0)).map((s) => s.student_id);
      if (add.length) {
        for (const s of next.students) seen.current.set(s.student_id, s.moments);
        setFresh((f) => new Set([...f, ...add]));
      }
    }
  }, (e) => (e instanceof AuthError ? onAuthLost() : setError(e.message))), [id, onAuthLost]);

  useEffect(() => {
    void load();
    const t = window.setInterval(() => void load(), POLL_MS);
    const tok = token.get();
    return () => { window.clearInterval(t); leaveView({ lab_id: id }, tok); };
  }, [load, id]);

  const counts = useMemo(() => {
    const c = new Map<LiveState, number>();
    for (const s of data?.students ?? []) c.set(s.state, (c.get(s.state) ?? 0) + 1);
    return c;
  }, [data]);

  if (!data) {
    return (
      <div className="mx-auto max-w-[1440px] px-5 pt-8">
        {error ? <Card className="p-6 text-sm text-danger">{error}</Card> : <Skeleton className="h-64 w-full rounded-2xl" />}
      </div>
    );
  }

  const nMoments = data.students.filter((s) => s.moments > 0).length;
  let rows = data.students.filter((s) => filter === null || (filter === "moments" ? s.moments > 0 : s.state === filter));
  if (sort === "recent") rows = [...rows].sort((a, b) => (b.last_edit_at ?? 0) - (a.last_edit_at ?? 0));

  return (
    <motion.div variants={stagger(0.05)} initial="initial" animate="animate" className="mx-auto max-w-[1440px] px-5 pb-20 pt-6">
      <motion.a variants={item} href={href.live} className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted hover:text-text">
        <ArrowLeft className="size-4" /> All open labs
      </motion.a>

      <motion.div variants={item} className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-success">
            <LiveDot tone="success" /> Live class view
          </p>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-semibold tracking-tight text-text">
            {data.lab.title} <LanguageBadge language={data.lab.language} />
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-sm text-muted"><Users className="size-4" />{data.students.length}</span>
          <Button size="sm" variant="ghost" onClick={() => setSort((s) => (s === "roll" ? "recent" : "roll"))}>
            <ArrowUpDown className="size-3.5" /> {sort === "roll" ? "Roll number" : "Last edit"}
          </Button>
          {data.lab.kind === "competition" && (
            <Button size="sm" onClick={() => { location.hash = href.board(id); }}><Trophy className="size-3.5 text-gold" /> Leaderboard</Button>
          )}
          <Button size="sm" onClick={() => { location.hash = href.lab(id); }}>Lab settings</Button>
        </div>
      </motion.div>

      <motion.div variants={item} className="mb-4 flex items-start gap-2 rounded-xl bg-accent-soft px-4 py-2.5 text-[13px] text-text">
        <Info className="mt-0.5 size-4 shrink-0 text-accent" />
        <p>
          Students in this lab see a small <strong className="font-semibold">Class view on</strong> notice while this page is open.
          {data.editor_view
            ? <> Opening someone's editor shows them a banner with your name for as long as you look. Every view is logged.</>
            : <> Viewing individual editors is turned off on this server.</>}
        </p>
      </motion.div>

      <motion.div variants={item} className="mb-4 flex flex-wrap gap-1.5" role="toolbar" aria-label="Filter students">
        <Chip active={filter === null} onClick={() => setFilter(null)}>All <span className="tabular-nums text-faint">{data.students.length}</span></Chip>
        {ORDER.filter((s) => counts.get(s)).map((s) => (
          <Chip key={s} active={filter === s} onClick={() => setFilter(filter === s ? null : s)}>
            <LiveDot tone={STATE[s].tone} live={STATE[s].live} /> {STATE[s].label} <span className="tabular-nums text-faint">{counts.get(s)}</span>
          </Chip>
        ))}
        {nMoments > 0 && (
          <Chip active={filter === "moments"} onClick={() => setFilter(filter === "moments" ? null : "moments")}>
            <MessagesSquare className="size-3.5 text-accent" /> Worth a conversation <span className="tabular-nums text-faint">{nMoments}</span>
          </Chip>
        )}
      </motion.div>

      {data.questions.length > 1 && (
        <motion.div variants={item} className="mb-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {[...data.questions].sort((a, b) => a.position - b.position).map((q) => {
            const on = data.students.filter((s) => s.question_id === q.id && !["submitted", "left"].includes(s.state)).length;
            const done = data.students.filter((s) => s.submitted.includes(q.id)).length;
            return (
              <div key={q.id} className="rounded-xl border border-border bg-surface px-3 py-2 text-xs">
                <p className="truncate font-medium text-text">Q{q.position + 1} · {q.title}</p>
                <p className="mt-0.5 text-muted"><span className="tabular-nums">{on}</span> working · <span className="tabular-nums">{done}</span> finished</p>
              </div>
            );
          })}
        </motion.div>
      )}

      <LayoutGroup>
        <motion.div layout className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          <AnimatePresence initial={false}>
            {rows.map((s) => (
              <motion.div key={s.student_id} layout transition={spring} initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.12 } }}>
                <StudentCard s={s} now={data.now} editorView={data.editor_view} fresh={fresh.has(s.student_id)}
                  onSeen={() => setFresh((f) => { const n = new Set(f); n.delete(s.student_id); return n; })} />
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      </LayoutGroup>
      {rows.length === 0 && <p className="py-10 text-center text-sm text-muted">Nobody here right now.</p>}
    </motion.div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} aria-pressed={active}
      className={cn("inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors",
        active ? "border-accent bg-accent-soft text-text" : "border-border bg-surface text-muted hover:text-text")}>
      {children}
    </button>
  );
}

function StudentCard({ s, now, editorView, fresh, onSeen }: {
  s: LiveStudent; now: number; editorView: boolean; fresh: boolean; onSeen: () => void;
}) {
  const st = STATE[s.state];
  const started = s.session_id !== null;
  return (
    <Card className={cn("flex h-full flex-col gap-3 p-4 transition-shadow", fresh && "ring-2 ring-accent/60",
      !started && "opacity-70")}>
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-mono text-sm font-semibold text-text">{s.student_id}</span>
        <Badge tone={st.tone === "accent" ? "accent" : st.tone}><LiveDot tone={st.tone} live={st.live} />{st.label}</Badge>
      </div>

      {started ? (
        <>
          <div className="min-w-0 text-[13px]">
            <p className="truncate text-text">
              {s.position !== null && <span className="text-faint">Q{s.position + 1} · </span>}{s.question_title}
            </p>
            <p className="text-xs text-muted">Last edit {ago(now, s.last_edit_at)}{s.submitted.length > 0 && ` · ${s.submitted.length} finished`}</p>
          </div>
          <ActivityBars bins={s.activity} />
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
            <span className="inline-flex items-center gap-1" title={s.last_run ? `Last run ${ago(now, s.last_run.at)}` : "No runs yet"}>
              <Play className="size-3" /> <span className="tabular-nums text-text">{s.runs}</span> run{s.runs === 1 ? "" : "s"}
              {s.last_run && (s.last_run.ok
                ? <CheckCircle2 className="size-3 text-success" aria-label="last run clean" />
                : <span className="inline-flex items-center gap-0.5 text-danger"><CircleAlert className="size-3" />{s.last_run.error_type}</span>)}
            </span>
            {s.check && (
              <span className="inline-flex items-center gap-1" title={`Best so far ${s.check.best}/${s.check.total}`}>
                <FlaskConical className="size-3" /> <span className="tabular-nums text-text">{s.check.passed}/{s.check.total}</span> tests
              </span>
            )}
            {s.pastes > 0 && (
              <span className="inline-flex items-center gap-1"><ClipboardPaste className="size-3" /><span className="tabular-nums text-text">{s.pastes}</span> paste{s.pastes === 1 ? "" : "s"}</span>
            )}
          </div>
          {s.moments > 0 && (
            <a href={href.session(s.moment_session_id ?? s.session_id)} onClick={onSeen}
              className="flex items-center gap-1.5 rounded-lg bg-accent-soft px-2.5 py-1.5 text-xs font-medium text-accent hover:underline">
              <MessagesSquare className="size-3.5" />
              {s.moments} moment{s.moments === 1 ? "" : "s"} worth a conversation in this lab
              {fresh && <span className="ml-auto rounded-full bg-accent px-1.5 text-[10px] font-semibold uppercase text-accent-fg">new</span>}
            </a>
          )}
          <div className="mt-auto flex items-center gap-2 pt-1">
            {editorView && (
              <Button size="sm" onClick={() => { location.hash = href.liveSession(s.session_id); }} disabled={s.state === "left" || s.state === "submitted"}>
                <Eye className="size-3.5" /> View editor
              </Button>
            )}
            <a href={href.session(s.session_id)} className="inline-flex h-8 items-center gap-1 rounded-md px-2 text-xs text-muted hover:text-text">
              <Activity className="size-3.5" /> Timeline
            </a>
            {s.watched && <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-faint" title="A teacher has this editor open"><Eye className="size-3" /> open</span>}
          </div>
        </>
      ) : (
        <p className="text-xs text-muted">Has not opened a question in this lab yet.</p>
      )}
    </Card>
  );
}

/** Edits per 30 s over the last 10 minutes; the newest bar is on the right. */
export function ActivityBars({ bins, className }: { bins: number[]; className?: string }) {
  const top = Math.max(8, ...bins);
  return (
    <div className={cn("flex h-7 items-end gap-[3px]", className)} role="img"
      aria-label={`${bins.reduce((a, b) => a + b, 0)} edits in the last 10 minutes`}>
      {bins.map((n, i) => (
        <motion.span key={i} className={cn("flex-1 rounded-sm", n ? "bg-accent/70" : "bg-surface-3")}
          initial={false} animate={{ height: `${n ? Math.max(14, (n / top) * 100) : 10}%` }} transition={{ duration: 0.4 }} />
      ))}
    </div>
  );
}
