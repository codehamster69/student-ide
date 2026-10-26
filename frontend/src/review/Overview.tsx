import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { ChevronRight, FlaskConical, MessageCircleQuestion, Search, Users } from "lucide-react";
import { Badge, Card, cn, item, stagger, spring } from "../ui";
import { AuthError, get, type SessionSummary, type StudentRow } from "./api";
import { ChannelTag, CountUp, Skeleton, Spark } from "./bits";
import { clock, dayTime, TASKS } from "./format";

type Filter = "all" | "moments" | "assessed";

export function Overview({ onAuthLost }: { onAuthLost: () => void }) {
  const [rows, setRows] = useState<SessionSummary[] | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [error, setError] = useState("");
  const [student, setStudent] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("assessed");
  const [q, setQ] = useState("");

  useEffect(() => {
    Promise.all([get<SessionSummary[]>("/api/review/sessions"), get<StudentRow[]>("/api/review/students")])
      .then(([s, st]) => { setRows(s); setStudents(st); })
      .catch((e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)));
  }, [onAuthLost]);

  const shown = useMemo(() => {
    if (!rows) return [];
    return rows
      .filter((r) => !student || r.student_id === student)
      .filter((r) => filter === "all" || r.phase === "assessed")
      .filter((r) => filter !== "moments" || r.episodes.length > 0)
      .filter((r) => !q || r.student_id.toLowerCase().includes(q.toLowerCase()))
      .sort((a, b) => b.started_at - a.started_at);
  }, [rows, student, filter, q]);

  const assessed = rows?.filter((r) => r.phase === "assessed") ?? [];
  const withMoments = assessed.filter((r) => r.episodes.length > 0);
  const synthetic = rows?.some((r) => r.synthetic);

  return (
    <motion.div variants={stagger(0.06)} initial="initial" animate="animate" className="mx-auto max-w-[1440px] px-5 pb-20 pt-8">
      <motion.div variants={item} className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Sessions</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Each session is compared with the same student's baseline weeks. Open one to see the evidence timeline and replay the code.
          </p>
        </div>
        {synthetic && (
          <Badge tone="warn"><FlaskConical className="size-3.5" /> Demo data: simulated students</Badge>
        )}
      </motion.div>

      <motion.div variants={item} className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Students" value={students.length} hint={`${students.filter((s) => s.baseline_ready).length} with a baseline`} loading={!rows} />
        <Stat label="Sessions reviewed" value={assessed.length} hint="after the baseline weeks" loading={!rows} />
        <Stat label="Sessions with a moment to discuss" value={withMoments.length} hint="worth a conversation" tone="warn" loading={!rows} />
        <Stat label="Baseline sessions" value={(rows?.length ?? 0) - assessed.length} hint="first four weeks, used as reference" loading={!rows} />
      </motion.div>

      <motion.div variants={item} className="mb-4 flex flex-wrap items-center gap-3">
        <LayoutGroup id="filter">
          <div className="flex rounded-lg border border-border bg-surface p-0.5 shadow-sm">
            {([["assessed", "Reviewed"], ["moments", "With moments"], ["all", "All incl. baseline"]] as [Filter, string][]).map(([f, label]) => (
              <button key={f} onClick={() => setFilter(f)}
                className={cn("relative h-8 rounded-md px-3 text-[13px] font-medium transition-colors", filter === f ? "text-text" : "text-muted hover:text-text")}>
                {filter === f && <motion.span layoutId="filter-pill" transition={spring} className="absolute inset-0 rounded-md bg-surface-3" />}
                <span className="relative">{label}</span>
              </button>
            ))}
          </div>
        </LayoutGroup>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-faint" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a student"
            className="h-9 w-48 rounded-lg border border-border bg-surface pl-8 pr-3 text-sm shadow-sm outline-none placeholder:text-faint focus:border-accent focus:ring-4 focus:ring-accent/15" />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Users className="mr-1 size-3.5 text-faint" />
          {[null, ...students.map((s) => s.student_id)].map((s) => (
            <button key={s ?? "all"} onClick={() => setStudent(s)}
              className={cn("h-7 rounded-full border px-2.5 font-mono text-xs transition-colors",
                student === s ? "border-accent bg-accent-soft text-accent" : "border-border bg-surface text-muted hover:text-text")}>
              {s ?? "everyone"}
            </button>
          ))}
        </div>
      </motion.div>

      {error && <Card className="p-6 text-sm text-danger">{error}</Card>}

      <Card variants={item} className="overflow-hidden">
        <div className="hidden grid-cols-[1.1fr_1.2fr_0.7fr_11rem_1.6fr_1.5rem] gap-4 border-b border-border bg-surface-2/60 px-5 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-faint lg:grid">
          <span>Student</span><span>Task · when</span><span>Length</span><span>Evidence over time</span><span>Moments to discuss</span><span />
        </div>
        {!rows && Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="flex items-center gap-4 border-b border-border px-5 py-4 last:border-0">
            <Skeleton className="h-4 w-24" /><Skeleton className="h-4 w-48" /><Skeleton className="ml-auto h-8 w-40" />
          </div>
        ))}
        <motion.ul layout>
          <AnimatePresence initial={false}>
            {shown.map((r, i) => (
              <motion.li key={r.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0, transition: { delay: Math.min(i, 12) * 0.025 } }}
                exit={{ opacity: 0, transition: { duration: 0.12 } }} className="border-b border-border last:border-0">
                <Row r={r} />
              </motion.li>
            ))}
          </AnimatePresence>
        </motion.ul>
        {rows && shown.length === 0 && (
          <p className="px-5 py-10 text-center text-sm text-muted">No sessions match these filters.</p>
        )}
      </Card>
      <p className="mt-4 text-xs text-faint">
        Lines show accumulated evidence for each channel relative to its threshold (dashed). Crossing it marks a moment to discuss.
      </p>
    </motion.div>
  );
}

function Stat({ label, value, hint, tone, loading }: { label: string; value: number; hint: string; tone?: "warn"; loading: boolean }) {
  return (
    <Card className="relative overflow-hidden p-4">
      <p className="text-[13px] font-medium text-muted">{label}</p>
      {loading ? <Skeleton className="mt-2 h-8 w-12" /> : (
        <p className={cn("mt-1 text-3xl font-semibold tracking-tight", tone === "warn" ? "text-warn" : "text-text")}><CountUp to={value} /></p>
      )}
      <p className="mt-1 text-xs text-faint">{hint}</p>
    </Card>
  );
}

function Row({ r }: { r: SessionSummary }) {
  return (
    <a href={`#/review/s/${r.id}`}
      className="group grid items-center gap-x-4 gap-y-2 px-5 py-3.5 transition-colors hover:bg-surface-2/70 lg:grid-cols-[1.1fr_1.2fr_0.7fr_11rem_1.6fr_1.5rem]">
      <span className="flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-full bg-surface-3 font-mono text-[11px] font-semibold text-muted">{r.student_id.slice(-2)}</span>
        <span className="font-mono text-sm font-medium text-text">{r.student_id}</span>
        {r.phase === "baseline" && <Badge className="h-5 px-2 text-[11px]">baseline</Badge>}
        {r.context === "competition" && <Badge tone="warn" className="h-5 px-2 text-[11px]">competition</Badge>}
      </span>
      <span className="text-sm">
        <span className="text-text">{r.task_title ?? TASKS[r.task_id] ?? r.task_id}</span>
        <span className="block text-xs text-faint">{dayTime(r.started_at)}</span>
      </span>
      <span className="font-mono text-sm tabular-nums text-muted">{clock(r.duration_s)}</span>
      <span>{r.baseline === "ready" ? <Spark spark={r.spark} /> : <span className="text-xs text-faint">waiting for baseline</span>}</span>
      <span className="flex flex-wrap items-center gap-1.5">
        {r.episodes.length === 0 ? (
          <span className="text-xs text-faint">{r.baseline === "ready" ? "Nothing stood out" : "—"}</span>
        ) : r.episodes.map((e, i) => (
          <span key={i} className="inline-flex items-center gap-1.5 rounded-full border border-warn/30 bg-warn-soft px-2 py-0.5">
            <MessageCircleQuestion className="size-3 text-warn" />
            <ChannelTag channel={e.channel} />
            <span className="font-mono text-[11px] text-muted">~{clock(e.switch_est)}</span>
          </span>
        ))}
      </span>
      <ChevronRight className="hidden size-4 text-faint transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-text lg:block" />
    </a>
  );
}
