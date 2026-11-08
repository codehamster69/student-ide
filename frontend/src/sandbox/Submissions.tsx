// The lab wizard's Submissions step: every rostered student x assignment as a
// grid of grades (like an autograder gradebook), filters for who still needs
// attention, one cell opens the test results (hidden tests in full for staff),
// a link to the session's review, regrade, and a CSV download.
import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { CircleAlert, Download, ExternalLink, RefreshCw, X } from "lucide-react";
import { Badge, Button, Card, Spinner, cn, item, stagger } from "../ui";
import { get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { href } from "../routes";
import type { LabDetail, SubmissionCell, SubmissionsTable } from "./api";

type Filter = "all" | "missing" | "failing" | "passed";
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "Everyone" }, { id: "missing", label: "Not submitted" },
  { id: "failing", label: "Failing a test" }, { id: "passed", label: "All passed" },
];

const passedAll = (c: SubmissionCell | null) => !!c && c.status === "graded" && c.passed === c.total;
const failing = (c: SubmissionCell | null) => !!c && (c.status === "failed" || (c.status === "graded" && c.passed !== c.total));
const when = (t: number | null) => (t ? new Date(t * 1000).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "");

export function Submissions({ lab }: { lab: LabDetail }) {
  const [data, setData] = useState<SubmissionsTable | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [open, setOpen] = useState<{ student: string; cell: SubmissionCell } | null>(null);
  const [busy, setBusy] = useState(false);
  const readOnly = lab.access === "ta";

  const load = () => get<SubmissionsTable>(`/api/sandbox/labs/${lab.id}/submissions`).then(setData, (e) => setError((e as Error).message));
  useEffect(() => { load(); }, [lab.id]);
  // while something grades, look again every few seconds
  useEffect(() => {
    if (!data?.grader.queued) return;
    const t = window.setTimeout(load, 4000);
    return () => window.clearTimeout(t);
  }, [data]);

  const rows = useMemo(() => (data?.students ?? []).filter((s) => {
    const cells = Object.values(s.assignments);
    if (filter === "missing") return cells.some((c) => !c);
    if (filter === "failing") return cells.some(failing);
    if (filter === "passed") return cells.length > 0 && cells.every(passedAll);
    return true;
  }), [data, filter]);

  if (error) return <Card className="p-5 text-sm text-danger">{error}</Card>;
  if (!data) return <Skeleton className="h-60 rounded-2xl" />;
  const { counts } = data;
  const expected = counts.students * data.assignments.length;

  const csv = () => {
    const head = ["roll number", "section", ...data.assignments.flatMap((a) => [`${a.title} passed`, `${a.title} total`, `${a.title} submitted at`])];
    const lines = data.students.map((s) => [s.student_id, s.section, ...data.assignments.flatMap((a) => {
      const c = s.assignments[a.id];
      return c ? [c.passed ?? "", c.total ?? "", new Date(c.submitted_at * 1000).toISOString()] : ["", "", ""];
    })]);
    const text = [head, ...lines].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([text], { type: "text/csv" })), download: `${lab.title} grades.csv` });
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <motion.div variants={stagger(0.04)} initial="initial" animate="animate" className="grid gap-4">
      {!data.grader.enabled && (
        <Card className="flex items-start gap-2 p-4 text-sm text-warn"><CircleAlert className="mt-0.5 size-4 shrink-0" />
          Grading is not set up on this server, so submissions wait ungraded. See "Grading" in docs/sandbox-labs.md.</Card>
      )}
      <motion.div variants={item} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Submitted" value={`${counts.submitted}/${expected}`} />
        <Stat label="Graded" value={String(counts.graded)} hint={data.grader.queued ? `${data.grader.queued} grading now` : undefined} />
        <Stat label="All tests passed" value={String(counts.passed_all)} tone="success" />
        <Stat label="Due" value={data.lab.due_at ? when(data.lab.due_at) : "No due time"} small />
      </motion.div>

      <motion.div variants={item} className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button key={f.id} onClick={() => setFilter(f.id)} className={cn("h-8 rounded-full border px-3 text-xs font-medium",
              filter === f.id ? "border-accent bg-accent-soft text-accent" : "border-border text-muted hover:text-text")}>{f.label}</button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={csv}><Download className="size-4" /> CSV</Button>
          {!readOnly && data.grader.enabled && (
            <Button disabled={busy || counts.submitted === 0} onClick={async () => {
              setBusy(true);
              try { await send("POST", `/api/sandbox/labs/${lab.id}/regrade`); await load(); } finally { setBusy(false); }
            }}>{busy ? <Spinner /> : <RefreshCw className="size-4" />} Regrade all</Button>
          )}
        </div>
      </motion.div>

      <motion.div variants={item}>
        <Card className="overflow-x-auto p-0">
          {rows.length === 0 ? (
            <p className="p-6 text-sm text-muted">{data.students.length ? "Nobody matches this filter." : "No students on this lab's roster yet."}</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="px-4 py-2.5 font-medium">Student</th>
                  {data.assignments.map((a) => <th key={a.id} className="px-3 py-2.5 font-medium">{a.title}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={s.student_id} className="border-b border-border last:border-0">
                    <td className="px-4 py-2">
                      <span className="font-mono text-[13px] text-text">{s.student_id}</span>
                      {s.section && <span className="ml-2 text-xs text-faint">{s.section}</span>}
                      {!s.on_roster && <Badge className="ml-2">left roster</Badge>}
                    </td>
                    {data.assignments.map((a) => {
                      const c = s.assignments[a.id];
                      return (
                        <td key={a.id} className="px-3 py-2">
                          {c ? (
                            <button onClick={() => setOpen({ student: s.student_id, cell: c })} className="rounded-full focus-visible:outline-2 focus-visible:outline-accent">
                              <Grade cell={c} />
                            </button>
                          ) : <span className="text-xs text-faint">not submitted</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </motion.div>

      {open && <ResultPanel student={open.student} cell={open.cell} title={data.assignments.find((a) => a.id === open.cell.assignment_id)?.title ?? ""}
        readOnly={readOnly || !data.grader.enabled} onClose={() => setOpen(null)}
        onRegraded={async (c) => { setOpen({ student: open.student, cell: c }); await load(); }} />}
    </motion.div>
  );
}

function Stat({ label, value, hint, tone, small }: { label: string; value: string; hint?: string; tone?: "success"; small?: boolean }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className={cn("mt-1 font-semibold tracking-tight", small ? "text-sm" : "text-2xl", tone === "success" ? "text-success" : "text-text")}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-accent">{hint}</div>}
    </Card>
  );
}

export function Grade({ cell }: { cell: Pick<SubmissionCell, "status" | "passed" | "total" | "attempts"> }) {
  if (cell.status === "queued" || cell.status === "grading") return <Badge tone="accent"><Spinner /> {cell.status === "queued" ? "waiting" : "grading"}</Badge>;
  if (cell.status === "failed") return <Badge tone="danger">couldn't grade</Badge>;
  if (cell.status === "no_tests") return <Badge>submitted</Badge>;
  const all = cell.passed === cell.total;
  return (
    <Badge tone={all ? "success" : cell.passed ? "warn" : "danger"}>
      {cell.passed}/{cell.total}{cell.attempts && cell.attempts > 1 ? <span className="opacity-70">· {cell.attempts} tries</span> : null}
    </Badge>
  );
}

function ResultPanel({ student, cell, title, readOnly, onClose, onRegraded }: {
  student: string; cell: SubmissionCell; title: string; readOnly: boolean; onClose: () => void; onRegraded: (c: SubmissionCell) => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <motion.aside initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }}
      className="fixed inset-y-0 right-0 z-40 w-full max-w-lg overflow-y-auto border-l border-border bg-surface p-5 shadow-xl">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-sm text-text">{student}</div>
          <h2 className="text-lg font-semibold text-text">{title}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
            <Grade cell={cell} /> submitted {when(cell.submitted_at)}{cell.regraded && <Badge>regraded</Badge>}
          </div>
        </div>
        <Button variant="ghost" onClick={onClose} aria-label="Close"><X className="size-4" /></Button>
      </div>
      {cell.error && <Card className="mb-3 p-3 text-sm text-danger">{cell.error}</Card>}
      <div className="mb-4 flex flex-wrap gap-2">
        {cell.session_id && <a href={href.session(cell.session_id)} className="inline-flex h-8 items-center gap-1 rounded-lg border border-border px-3 text-xs text-muted hover:text-text"><ExternalLink className="size-3.5" /> How it was written</a>}
        {!readOnly && <Button disabled={busy} onClick={async () => {
          setBusy(true);
          try { onRegraded(await send<SubmissionCell>("POST", `/api/sandbox/submissions/${cell.id}/regrade`)); } finally { setBusy(false); }
        }}>{busy ? <Spinner /> : <RefreshCw className="size-4" />} Regrade</Button>}
      </div>
      <div className="grid gap-2">
        {cell.results.map((r, i) => (
          <Card key={i} className="p-3">
            <div className="flex items-center justify-between gap-2 text-sm">
              <span className="font-medium text-text">{r.name}{r.hidden && <Badge className="ml-2">hidden</Badge>}</span>
              <Badge tone={r.passed ? "success" : "danger"}>{r.passed ? "passed" : r.timed_out ? "timed out" : "failed"}</Badge>
            </div>
            {!r.passed && (r.expected !== undefined || r.stdout !== undefined) && (
              <div className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
                {r.stdin !== undefined && <Out label="Input" text={r.stdin} />}
                {r.expected !== undefined && <Out label="Expected" text={r.expected} />}
                {r.got !== undefined && <Out label="Got" text={r.got} />}
                {r.stdout !== undefined && <Out label="Output" text={r.stdout} />}
                {r.stderr && <Out label="Errors" text={r.stderr} />}
              </div>
            )}
          </Card>
        ))}
      </div>
    </motion.aside>
  );
}

function Out({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <div className="mb-1 text-faint">{label}</div>
      <pre className="max-h-40 overflow-auto rounded-md bg-surface-2 p-2 font-mono text-[12px] text-text">{text || "(empty)"}</pre>
    </div>
  );
}
