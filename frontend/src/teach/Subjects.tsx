import { useEffect, useMemo, useState } from "react";
import { motion } from "motion/react";
import { ArrowLeft, BookOpen, ChevronRight, ClipboardCheck, ExternalLink, Plus } from "lucide-react";
import { Badge, Button, Card, Field, Input, item, stagger } from "../ui";
import { AuthError, get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { href, subjectSlug } from "../routes";
import { STATUS, type LabRow, type LabStatus } from "./api";
import type { Connection, LabAttendanceSummary, RollCallSubject } from "./attendanceApi";

const TONE: Record<LabStatus, "neutral" | "success" | "warn"> = { draft: "neutral", open: "success", closed: "warn" };

interface SubjectGroup { slug: string; name: string; code: string; labs: LabRow[]; inRollCall: boolean }

/** Labs grouped by subject, plus Roll Call's subjects that have no lab yet. */
function useSubjects(onAuthLost: () => void) {
  const [labs, setLabs] = useState<LabRow[] | null>(null);
  const [att, setAtt] = useState<LabAttendanceSummary>({});
  const [conn, setConn] = useState<Connection | null>(null);
  const [rc, setRc] = useState<RollCallSubject[]>([]);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const fail = (e: unknown) => (e instanceof AuthError ? onAuthLost() : setError((e as Error).message));
    get<LabRow[]>("/api/teach/labs").then(setLabs, fail);
    get<LabAttendanceSummary>("/api/teach/attendance/labs").then(setAtt, fail);
    get<Connection>("/api/teach/attendance").then((c) => {
      setConn(c);
      if (c.connected) get<RollCallSubject[]>("/api/teach/attendance/subjects").then(setRc, () => setRc([]));
    }, fail);
  }, [onAuthLost, version]);
  const groups = useMemo(() => {
    const by = new Map<string, SubjectGroup>();
    const at = (name: string) => {
      const slug = subjectSlug(name);
      if (!by.has(slug)) by.set(slug, { slug, name: name.trim() || "No subject", code: "", labs: [], inRollCall: false });
      return by.get(slug)!;
    };
    rc.forEach((s) => Object.assign(at(s.name), { code: s.code, inRollCall: true }));
    (labs ?? []).forEach((l) => at(l.subject).labs.push(l));
    return [...by.values()].sort((a, b) => (a.slug === "no-subject" ? 1 : b.slug === "no-subject" ? -1 : a.name.localeCompare(b.name)));
  }, [labs, rc]);
  return { labs, att, conn, groups, error, reload: () => setVersion((v) => v + 1) };
}

/** #/teach/subjects: every subject the teacher has labs in, with their class groups and attendance. */
export function Subjects({ onAuthLost }: { onAuthLost: () => void }) {
  const { labs, att, conn, groups, error, reload } = useSubjects(onAuthLost);
  const [adding, setAdding] = useState(false);

  return (
    <motion.div variants={stagger(0.05)} initial="initial" animate="animate" className="mx-auto max-w-[1100px] px-5 pb-20 pt-8">
      <motion.div variants={item} className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Subjects</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Your labs grouped by the subject set on each lab{conn?.connected ? ", together with the subjects in your Roll Call" : ""}.
            Attendance from a lab is filed under its subject in Roll Call.
          </p>
        </div>
        {conn?.connected && <Button onClick={() => setAdding(!adding)}><Plus className="size-4" /> New subject</Button>}
      </motion.div>
      {adding && <NewSubject onDone={() => { setAdding(false); reload(); }} onAuthLost={onAuthLost} />}
      {error && <Card className="mb-4 p-6 text-sm text-danger">{error}</Card>}
      {!labs ? <Skeleton className="h-40 w-full rounded-2xl" /> : groups.length === 0 ? (
        <Card className="grid place-items-center gap-2 px-6 py-14 text-center">
          <span className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent"><BookOpen className="size-5" /></span>
          <p className="text-sm font-medium text-text">No subjects yet</p>
          <p className="max-w-sm text-sm text-muted">Set a subject on a lab (Session settings) and it shows up here.</p>
        </Card>
      ) : (
        <motion.ul variants={stagger(0.04, 0.05)} className="grid gap-3 md:grid-cols-2">
          {groups.map((g) => {
            const classes = [...new Set(g.labs.flatMap((l) => att[l.id]?.classes ?? []))];
            const open = g.labs.filter((l) => l.status === "open").length;
            return (
              <motion.li key={g.slug} variants={item}>
                <a href={`#/teach/subjects/${encodeURIComponent(g.slug)}`} className="block h-full">
                  <Card className="flex h-full flex-col gap-3 p-5 transition-shadow hover:shadow-md">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        {g.code && <div className="font-mono text-[11px] font-semibold text-accent">{g.code}</div>}
                        <div className="text-[15px] font-semibold text-text">{g.name}</div>
                      </div>
                      <ChevronRight className="size-4 text-faint" />
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {classes.length ? classes.map((c) => <Badge key={c} className="h-5 px-2 text-[11px]">{c}</Badge>)
                        : <span className="text-xs text-faint">No class group attached</span>}
                    </div>
                    <div className="mt-auto flex gap-3 text-xs text-muted">
                      <span>{g.labs.length} lab{g.labs.length === 1 ? "" : "s"}</span>
                      {open > 0 && <span className="text-success">{open} open</span>}
                      <span>{g.labs.reduce((a, l) => a + l.n_sessions, 0)} sessions</span>
                      {g.inRollCall && <span className="ml-auto inline-flex items-center gap-1"><ClipboardCheck className="size-3" /> in Roll Call</span>}
                    </div>
                  </Card>
                </a>
              </motion.li>
            );
          })}
        </motion.ul>
      )}
    </motion.div>
  );
}

function NewSubject({ onDone, onAuthLost }: { onDone: () => void; onAuthLost: () => void }) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  return (
    <Card className="mb-5 p-5">
      <form className="grid gap-3 sm:grid-cols-[8rem_1fr_auto] sm:items-end" onSubmit={async (e) => {
        e.preventDefault();
        try { await send("POST", "/api/teach/attendance/subjects", { code, name }); onDone(); }
        catch (err) { if (err instanceof AuthError) onAuthLost(); else setError((err as Error).message); }
      }}>
        <Field label="Code"><Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS301" className="h-9 font-mono uppercase" /></Field>
        <Field label="Name"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Data Structures" className="h-9" autoFocus /></Field>
        <Button type="submit" variant="primary" className="h-9" disabled={!name.trim()}>Add to Roll Call</Button>
      </form>
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
    </Card>
  );
}

/** #/teach/subjects/<slug>: one subject's labs, the class groups they mark, and how much attendance has gone out. */
export function Subject({ slug, onAuthLost }: { slug: string; onAuthLost: () => void }) {
  const { labs, att, conn, groups, error } = useSubjects(onAuthLost);
  const g = groups.find((x) => x.slug === slug);
  return (
    <motion.div variants={stagger(0.05)} initial="initial" animate="animate" className="mx-auto max-w-[1100px] px-5 pb-20 pt-6">
      <motion.a variants={item} href={href.subjects} className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted hover:text-text">
        <ArrowLeft className="size-4" /> Subjects
      </motion.a>
      {error && <Card className="mb-4 p-6 text-sm text-danger">{error}</Card>}
      {!labs ? <Skeleton className="h-40 w-full rounded-2xl" /> : !g ? (
        <Card className="p-6 text-sm text-muted">No labs with this subject.</Card>
      ) : (
        <>
          <motion.div variants={item} className="mb-5 flex flex-wrap items-end justify-between gap-4">
            <div>
              {g.code && <div className="font-mono text-xs font-semibold text-accent">{g.code}</div>}
              <h1 className="text-2xl font-semibold tracking-tight text-text">{g.name}</h1>
            </div>
            {conn?.connected && g.slug !== "no-subject" && (
              <a href={`${conn.url}/subjects/${g.slug}`} target="_blank" rel="noreferrer"
                className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-sm font-medium text-text shadow-sm hover:bg-surface-2">
                <ExternalLink className="size-4" /> Attendance register in Roll Call
              </a>
            )}
          </motion.div>
          {g.labs.length === 0 ? (
            <Card className="p-6 text-sm text-muted">This subject is in Roll Call but no lab uses it yet. Set it as a lab's subject to file the lab's attendance here.</Card>
          ) : (
            <Card className="overflow-hidden">
              <table className="w-full text-[13px]">
                <thead className="bg-surface-2/80 text-left text-xs text-faint">
                  <tr><th className="px-5 py-2.5 font-semibold">Lab</th><th className="px-3 py-2.5 font-semibold">Status</th>
                    <th className="px-3 py-2.5 font-semibold">Class groups</th><th className="px-3 py-2.5 text-right font-semibold">Sessions</th>
                    <th className="px-5 py-2.5 text-right font-semibold">Attendance</th></tr>
                </thead>
                <tbody>
                  {g.labs.map((l) => {
                    const a = att[l.id];
                    return (
                      <tr key={l.id} className="border-t border-border">
                        <td className="px-5 py-3"><a href={href.lab(l.id)} className="font-medium text-text hover:text-accent">{l.title}</a></td>
                        <td className="px-3 py-3"><Badge tone={TONE[l.status]} className="h-5 px-2 text-[11px]">{STATUS[l.status].label}</Badge></td>
                        <td className="px-3 py-3 text-muted">{a?.classes.join(", ") || <span className="text-faint">none</span>}</td>
                        <td className="px-3 py-3 text-right tabular-nums text-muted">{l.n_sessions}</td>
                        <td className="px-5 py-3 text-right">
                          {a?.classes.length ? (
                            <a href={href.labAttendance(l.id)} className={a.errors ? "text-danger hover:underline" : "text-accent hover:underline"}>
                              {a.errors ? "send failed" : a.days_sent ? `${a.days_sent} day${a.days_sent === 1 ? "" : "s"} sent` : "not sent yet"}
                            </a>
                          ) : <span className="text-faint">—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
          )}
        </>
      )}
    </motion.div>
  );
}
