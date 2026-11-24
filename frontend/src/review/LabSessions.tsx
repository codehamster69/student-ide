import { useEffect, useMemo, useState } from "react";
import { Boxes, CalendarClock, ChevronRight, MessageCircleQuestion, NotebookPen, Trophy, Users } from "lucide-react";
import { Badge, Card, EmptyState, Page, PageHeader } from "../ui";
import { AuthError, get, type LabSessionRow, type SessionSummary } from "./api";
import { Skeleton } from "./bits";
import { dayKey, span } from "./format";
import { href } from "../routes";

interface Sitting {
  lab: LabSessionRow;
  day: string;
  start: number;
  end: number;
  students: number;
  sessions: number;
  assessed: number;
  talkTo: number;
}

/** #/review: one row per lab session, a lab on one day (a class meeting), for
 * the teacher's own and shared labs (admins: every lab), newest first. Opening
 * one lists that class's sessions student by student. */
export function LabSessions({ onAuthLost }: { onAuthLost: () => void }) {
  const [labs, setLabs] = useState<LabSessionRow[] | null>(null);
  const [rows, setRows] = useState<SessionSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([get<LabSessionRow[]>("/api/review/labs"), get<SessionSummary[]>("/api/review/sessions")])
      .then(([l, s]) => { setLabs(l); setRows(s); })
      .catch((e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)));
  }, [onAuthLost]);

  const sittings = useMemo(() => {
    if (!labs || !rows) return null;
    const byId = new Map(labs.map((l) => [l.id, l]));
    const groups = new Map<string, SessionSummary[]>();
    for (const r of rows) {
      const k = `${r.lab_id ?? "practice"}|${dayKey(r.started_at)}`;
      groups.set(k, [...(groups.get(k) ?? []), r]);
    }
    const out: Sitting[] = [];
    for (const [k, ss] of groups) {
      const [labId, day] = k.split("|");
      const lab = byId.get(labId);
      if (!lab) continue;
      out.push({
        lab, day, start: Math.min(...ss.map((s) => s.started_at)), end: Math.max(...ss.map((s) => s.started_at + s.duration_s)),
        students: new Set(ss.map((s) => s.student_id)).size, sessions: ss.length,
        assessed: ss.filter((s) => s.phase === "assessed").length,
        talkTo: new Set(ss.filter((s) => s.episodes.length).map((s) => s.student_id)).size,
      });
    }
    return out.sort((a, b) => b.start - a.start);
  }, [labs, rows]);

  return (
    <Page>
      <PageHeader
        title="Lab sessions"
        description="Each row is one class: a lab on the day it ran. Open it to review what every student did, compared with their own baseline weeks, never with the class."
        actions={<a href={href.reviewAll} className="inline-flex h-9 items-center rounded-lg border border-border bg-surface px-3 text-sm font-medium text-text shadow-sm hover:bg-surface-2">Every session in one list</a>}
      />

      {error && <Card className="mb-4 p-6 text-sm text-danger">{error}</Card>}
      {!sittings && !error && <Skeleton className="h-64 w-full rounded-xl" />}
      {sittings && sittings.length === 0 && (
        <EmptyState icon={NotebookPen} title="Nothing recorded in your labs yet">
          Sessions show up here once students work in a lab you made or that was shared with you.
        </EmptyState>
      )}

      {sittings && sittings.length > 0 && (
        <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
          {sittings.map(({ lab: l, day, start, end, students, sessions, assessed, talkTo }) => (
            <li key={`${l.id}-${day}`}>
              <a href={href.reviewLab(l.id, day)}
                className="group grid items-center gap-x-6 gap-y-2 px-5 py-3.5 transition-colors hover:bg-surface-2/60 md:grid-cols-[1fr_auto_13rem_1rem]">
                <span className="min-w-0">
                  <span className="flex items-center gap-2">
                    {l.kind === "competition" && <Trophy className="size-4 shrink-0 text-gold" aria-label="Competition" />}
                    {l.kind === "sandbox" && <Boxes className="size-4 shrink-0 text-accent" aria-label="Sandbox Lab" />}
                    <strong className="truncate text-[15px] font-semibold text-text">{l.title}</strong>
                    {l.kind === "practice" && <Badge className="h-5 px-2 text-[11px]">outside any lab</Badge>}
                  </span>
                  <span className="mt-0.5 flex items-center gap-1.5 text-[13px] text-muted">
                    <CalendarClock className="size-3.5 text-faint" />
                    {span(start, end, [start])}
                    {l.subject && <span className="text-faint">· {l.subject}</span>}
                  </span>
                </span>
                <span className="flex items-center gap-1.5 text-sm tabular-nums text-muted">
                  <Users className="size-3.5 text-faint" />
                  <span className="font-semibold text-text">{students}</span> {students === 1 ? "student" : "students"}
                  <span className="text-faint">· {sessions} sessions</span>
                </span>
                {talkTo ? (
                  <Badge tone="warn" className="justify-self-start">
                    <MessageCircleQuestion className="size-3.5" />
                    {talkTo} {talkTo === 1 ? "student" : "students"} to talk with
                  </Badge>
                ) : (
                  <span className="text-xs text-faint">{assessed ? "Nothing stood out" : "Baseline weeks only"}</span>
                )}
                <ChevronRight className="hidden size-4 text-faint group-hover:text-text md:block" />
              </a>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}
