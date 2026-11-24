import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Eye, ListChecks, Plus, Search, Sparkles, Trophy, X } from "lucide-react";
import { Badge, Button, Card, EmptyState, Field, Input, Page, PageHeader, Spinner, TextArea, cn, pop } from "../ui";
import { AuthError, get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { dayTime } from "../review/format";
import { BOARD_MODES, type BoardMode, type TeacherComp } from "../compete/api";
import { STATUS, type LabLanguage, type LabDetail, type LabRow, type LabStatus } from "./api";
import { LanguageBadge, LanguageSelect } from "./bits";
import { href } from "../routes";

const TONE: Record<LabStatus, "neutral" | "success" | "warn"> = { draft: "neutral", open: "success", closed: "warn" };
const GRID = "md:grid-cols-[minmax(0,1fr)_8rem_4.5rem_5.5rem_8.5rem_9.5rem]";

/** #/teach: the labs this teacher made or was added to (admins: every lab), and a form to start a new one. */
export function Labs({ onAuthLost }: { onAuthLost: () => void }) {
  const [labs, setLabs] = useState<LabRow[] | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState<false | "lab" | "competition">(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | LabStatus>("all");

  useEffect(() => {
    get<LabRow[]>("/api/teach/labs").then(setLabs)
      .catch((e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)));
  }, [onAuthLost]);

  const counts = useMemo(() => {
    const c = { all: labs?.length ?? 0, draft: 0, open: 0, closed: 0 };
    labs?.forEach((l) => { c[l.status]++; });
    return c;
  }, [labs]);
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (labs ?? []).filter((l) => (status === "all" || l.status === status)
      && (!needle || `${l.title} ${l.subject} ${l.owner_email ?? ""}`.toLowerCase().includes(needle)));
  }, [labs, q, status]);

  return (
    <Page>
      <PageHeader title="Labs"
        description="A lab is one sitting: questions with starter code, assigned to the students who should see it."
        actions={<div className="flex max-w-[calc(100vw-2rem)] flex-wrap gap-2">
          {/* also in the header, which runs off narrow screens */}
          <a href={href.student} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-sm font-medium text-text shadow-sm hover:bg-surface-2 md:hidden">
            <Eye className="size-4" /> View as student
          </a>
          <Button onClick={() => setCreating("competition")} disabled={!!creating}>
            <Trophy className="size-4 text-gold" /> New competition
          </Button>
          <Button variant="primary" onClick={() => setCreating("lab")} disabled={!!creating}>
            <Plus className="size-4" /> New lab
          </Button>
        </div>} />

      <AnimatePresence>{creating && <NewLab key={creating} kind={creating} onClose={() => setCreating(false)} onAuthLost={onAuthLost} />}</AnimatePresence>

      {error && <Card className="mb-4 p-6 text-sm text-danger">{error}</Card>}

      {!labs && !error && (
        <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
          {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-16 w-full rounded-none border-b border-border last:border-b-0" />)}
        </div>
      )}

      {labs && labs.length === 0 && !creating && (
        <EmptyState icon={ListChecks} title="No labs yet"
          action={<>
            <a href={href.setup} className="mr-2 inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-sm font-medium text-text shadow-sm hover:bg-surface-2">
              <Sparkles className="size-4 text-accent" /> Getting started
            </a>
            <Button variant="primary" onClick={() => setCreating("lab")}><Plus className="size-4" /> New lab</Button>
          </>}>
          Create one, add a few questions, assign your students and open it when the class starts.
        </EmptyState>
      )}

      {labs && labs.length > 0 && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <div className="relative min-w-[14rem] flex-1 sm:max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title or subject" aria-label="Search labs" className="h-9 pl-9 text-[13px]" />
            </div>
            <div className="flex rounded-lg border border-border bg-surface p-0.5 shadow-sm" role="group" aria-label="Filter by status">
              {(["all", "open", "draft", "closed"] as const).map((s) => (
                <button key={s} type="button" aria-pressed={status === s} onClick={() => setStatus(s)}
                  className={cn("h-8 rounded-md px-3 text-[13px] font-medium transition-colors",
                    status === s ? "bg-surface-3 text-text" : "text-muted hover:text-text")}>
                  {s === "all" ? "All" : STATUS[s].label} <span className="tabular-nums text-faint">{counts[s]}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
            <div className={cn("hidden gap-x-4 border-b border-border bg-surface-2 px-4 py-2 text-xs font-medium text-faint md:grid", GRID)}>
              <span>Lab</span><span>Subject</span><span className="text-right">Questions</span><span className="text-right">Assigned</span><span>Activity</span><span>Last edit</span>
            </div>
            {shown.length === 0 ? (
              <p className="px-4 py-10 text-center text-sm text-muted">No labs match. <button className="font-medium text-accent hover:underline" onClick={() => { setQ(""); setStatus("all"); }}>Clear filters</button></p>
            ) : (
              <ul className="divide-y divide-border">
                {shown.map((l) => (
                  <li key={l.id}>
                    <a href={href.lab(l.id)} className={cn("group grid items-center gap-x-4 gap-y-1 px-4 py-3 transition-colors hover:bg-surface-2", GRID)}>
                      <span className="min-w-0">
                        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                          {l.kind === "competition" && <Trophy className="size-4 shrink-0 text-gold" aria-label="Competition" />}
                          <strong className="truncate text-sm font-semibold text-text">{l.title}</strong>
                          <Badge tone={TONE[l.status]} className="h-5 px-2 text-[11px]">{STATUS[l.status].label}</Badge>
                          <LanguageBadge language={l.language} />
                        </span>
                        {(l.description || l.access !== "owner") && (
                          <span className="mt-1 flex min-w-0 items-center gap-2">
                            <OwnerBadge lab={l} />
                            {l.description && <span className="truncate text-[13px] text-muted">{l.description}</span>}
                          </span>
                        )}
                      </span>
                      <span className="truncate text-[13px] text-muted">{l.subject || <span className="text-faint">No subject</span>}</span>
                      <span className="text-[13px] text-muted md:text-right"><b className="font-semibold tabular-nums text-text">{l.n_questions}</b> <span className="md:hidden">{l.n_questions === 1 ? "question" : "questions"}</span></span>
                      <span className="text-[13px] text-muted md:text-right"><b className="font-semibold tabular-nums text-text">{l.everyone ? "All" : l.n_roster}</b> <span className="md:hidden">{l.everyone ? "students" : "assigned"}</span></span>
                      {l.kind === "competition" ? (
                        // a link of its own inside the row's link: navigate by hand so the row does not open
                        <span role="link" tabIndex={0} className="inline-flex h-6 items-center gap-1 justify-self-start rounded-md bg-gold-soft px-2 text-xs font-medium text-gold transition-opacity hover:opacity-80"
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); location.hash = href.board(l.id); }}
                          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); location.hash = href.board(l.id); } }}>
                          <Trophy className="size-3.5" /> Leaderboard
                        </span>
                      ) : (
                        <span className="text-xs tabular-nums text-muted">{l.n_sessions ? `${l.n_started} started, ${l.n_sessions} sessions` : <span className="text-faint">No sessions</span>}</span>
                      )}
                      <span className="text-xs tabular-nums text-faint">{dayTime(l.updated_at)}</span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </Page>
  );
}

/** Whose lab this is, when it isn't simply yours. */
export function OwnerBadge({ lab }: { lab: Pick<LabRow, "access" | "owner_email"> }) {
  if (lab.access === "co_teacher") return <Badge className="h-5 shrink-0 whitespace-nowrap px-2 text-[11px]">Shared with you · {lab.owner_email?.split("@")[0]}</Badge>;
  if (lab.access !== "admin") return null;
  return lab.owner_email
    ? <Badge className="h-5 shrink-0 whitespace-nowrap px-2 font-mono text-[11px]">{lab.owner_email.split("@")[0]}</Badge>
    : <Badge tone="warn" className="h-5 shrink-0 whitespace-nowrap px-2 text-[11px]">No owner yet</Badge>;
}

function NewLab({ kind, onClose, onAuthLost }: { kind: "lab" | "competition"; onClose: () => void; onAuthLost: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [minutes, setMinutes] = useState("30");
  const [board, setBoard] = useState<BoardMode>("top");
  const comp = kind === "competition";
  const [subject, setSubject] = useState("");
  const [language, setLanguage] = useState<LabLanguage>("python");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const id = comp
        ? (await send<TeacherComp>("POST", "/api/teach/competitions",
            { title, description, subject, language, duration_min: Number(minutes) || null, board })).lab_id
        : (await send<LabDetail>("POST", "/api/teach/labs", { title, description, subject, language })).id;
      location.hash = href.lab(id);
    } catch (err) {
      if (err instanceof AuthError) return onAuthLost();
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <motion.div variants={pop} initial="initial" animate="animate" exit="exit" className="mb-5">
      <Card className="p-5">
        <form onSubmit={submit} className="grid gap-4">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text">
              {comp && <Trophy className="size-4 text-gold" />}{comp ? "New competition" : "New lab"}
            </h2>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cancel"><X className="size-4" /></Button>
          </div>
          <Field label="Title">
            <Input autoFocus required maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder={comp ? "Friday sprint: strings" : "Lab 5: Strings and dictionaries"} />
          </Field>
          {comp && (
            <div className="grid gap-4 md:grid-cols-[160px_1fr]">
              <Field label="Clock (minutes)" hint="Empty for no clock; you end it.">
                <Input type="number" min={1} max={600} value={minutes} onChange={(e) => setMinutes(e.target.value)} />
              </Field>
              <Field label="Students see" hint={BOARD_MODES[board].about}>
                <div className="flex gap-1.5">
                  {(Object.keys(BOARD_MODES) as BoardMode[]).map((m) => (
                    <button type="button" key={m} onClick={() => setBoard(m)}
                      className={cn("h-11 flex-1 rounded-lg border text-[13px] font-medium transition-colors",
                        board === m ? "border-accent bg-accent-soft text-accent" : "border-border bg-surface text-muted hover:text-text")}>
                      {BOARD_MODES[m].label}
                    </button>
                  ))}
                </div>
              </Field>
              <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted md:col-span-2">
                Competitions are graded on test cases: every question needs at least one test before you can start the clock.
                Students earn points for tests passed and a bonus for solving early. Nothing from the review timeline ever reaches the board.
              </p>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Subject" hint="Optional.">
              <Input maxLength={120} value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Data Structures" />
            </Field>
            <Field label="Programming language" hint={language === "any"
              ? "Each student picks C, C++, Java, JavaScript or Python per question. Tests are the same in every language."
              : comp ? "What students write and run. Pick Any language for an open contest." : "What students write and run in this lab."}>
              <LanguageSelect<LabLanguage> value={language} onChange={setLanguage} any={comp} />
            </Field>
          </div>
          <Field label="Instructions for students" hint="Optional. Shown above the questions.">
            <TextArea rows={3} maxLength={4000} value={description} onChange={(e) => setDescription(e.target.value)}
              placeholder="Work through the questions in order. Run your code as often as you like." />
          </Field>
          {error && <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
          <div className={cn("flex justify-end gap-2")}>
            <Button onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={busy || !title.trim()}>
              {busy && <Spinner />} Create and add questions
            </Button>
          </div>
        </form>
      </Card>
    </motion.div>
  );
}
