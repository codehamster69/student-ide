import { useEffect, useState } from "react";
import { CheckCircle2, ChevronRight, Code2, NotebookPen, Play, Sparkles, Trophy } from "lucide-react";
import { api, type Lab, type Task } from "../api";
import { Badge, Button, LiveDot, Spinner, cn } from "../ui";
import { LearnCard } from "../learn/Learn";
import { SandboxLabs } from "./SandboxLabs";

/** Where "Start/Continue lab" lands: the first question not finished yet. */
const firstOpen = (lab: Lab) => Math.max(0, lab.questions.findIndex((q) => !q.submitted));

export function Tasks({ studentId, onPick, onOpenLab, onCompetition, onLearn, onSandbox }: {
  studentId: string;
  onPick: (task: Task) => Promise<void>;
  /** opens the whole lab as one sitting, on question `start` */
  onOpenLab: (lab: Lab, start: number) => Promise<void>;
  onCompetition: (labId: string) => void;
  /** the always-open learning lab */
  onLearn: () => void;
  /** a Sandbox lab (desktop app only; the website lists them with a note) */
  onSandbox: (labId: string) => void;
}) {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [labs, setLabs] = useState<Lab[]>([]);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api<Task[]>("/api/tasks"), api<Lab[]>(`/api/students/${encodeURIComponent(studentId)}/labs`)])
      .then(([t, l]) => { setLabs(l); setTasks(t); }, (e) => setError((e as Error).message));
  }, [studentId]);

  const pick = async (t: Task, lab?: Lab, start = 0) => {
    if (opening) return;
    setOpening(t.id);
    try {
      await (lab ? onOpenLab(lab, start) : onPick(t));
    } catch (e) {
      setError((e as Error).message);
      setOpening(null);
    }
  };

  const regular = labs.filter((l) => l.kind !== "competition");
  const comps = labs.filter((l) => l.kind === "competition" && l.state && l.state in COMP_STATE);

  return (
    <div className="w-full max-w-[1120px]">
      <Hero studentId={studentId} labs={regular} comps={comps} loaded={!!tasks} />
      <h2 className="mb-3 text-[15px] font-semibold text-text">{labs.length ? "Your labs" : "Choose a task"}</h2>
      {tasks && !regular.length && !comps.length && (
        <p className="mb-8 rounded-xl border border-dashed border-border px-5 py-6 text-sm text-muted">
          <Sparkles className="mr-1.5 inline size-4 text-accent-2" />
          No labs from your teacher yet. Perfect time for a warm-up: pick a practice task below or open the learning lab.
        </p>
      )}

      {error && <p className="mb-6 rounded-lg border border-danger/40 px-3 py-2 text-sm text-danger">{error}</p>}
      {!tasks && !error && <div className="mt-10 flex justify-center text-muted"><Spinner className="size-5" /></div>}

      {tasks && regular.map((lab, li) => {
        const at = firstOpen(lab), done = lab.questions.filter((q) => q.submitted).length;
        const pct = lab.questions.length ? Math.round((done / lab.questions.length) * 100) : 0;
        return (
          <section key={lab.id} className={li ? "mt-8" : ""}>
            <div className="overflow-hidden rounded-xl border border-border shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-border px-5 py-4">
                <div className="min-w-0 flex-1 basis-64">
                  <h2 className="flex flex-wrap items-center gap-2 text-base font-semibold text-text">
                    <NotebookPen className="size-4 text-accent" /> {lab.title}
                    {lab.draft && <Badge tone="warn">Draft: students can't see it yet</Badge>}
                  </h2>
                  {lab.description && <p className="mt-1 max-w-2xl text-[13px] text-muted">{lab.description}</p>}
                  <div className="mt-3 flex items-center gap-3">
                    <div className="h-1.5 w-40 overflow-hidden rounded-full bg-border" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
                      <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs tabular-nums text-faint">{done} of {lab.questions.length} finished</span>
                  </div>
                </div>
                <Button variant="primary" onClick={() => void pick(lab.questions[at], lab, at)} disabled={!!opening}>
                  {opening === lab.questions[at].id ? <Spinner className="size-3.5" /> : <Play className="size-3.5 fill-current" />}
                  {lab.questions.some((q) => q.sessions) ? "Continue lab" : "Start lab"}
                </Button>
              </div>
              <ul className="divide-y divide-border">
                {lab.questions.map((q, i) => (
                  <li key={q.id}>
                    <button
                      onClick={() => void pick(q, lab, i)}
                      disabled={!!opening}
                      title="Opens the whole lab at this question; you can move between questions in the editor"
                      className="group flex w-full items-center gap-4 px-5 py-3 text-left border border-transparent transition-[border-color,transform,box-shadow] hover:border-border-strong disabled:cursor-wait"
                    >
                      <span className={cn(
                        "grid size-7 shrink-0 place-items-center rounded-lg text-xs font-semibold tabular-nums",
                        q.submitted ? "border border-success/40 text-success" : "border border-cta/40 text-cta",
                      )}>
                        {opening === q.id ? <Spinner /> : q.submitted ? <CheckCircle2 className="size-4" /> : i + 1}
                      </span>
                      <span className="min-w-0 flex-1">
                        <strong className="block text-sm font-medium text-text">{q.title}</strong>
                        <span className="line-clamp-1 text-[13px] text-muted">{q.prompt}</span>
                      </span>
                      {q.submitted ? <Badge tone="success">Finished</Badge> : q.sessions ? <Badge>Started</Badge> : null}
                      <ChevronRight className="size-4 shrink-0 text-faint transition-colors group-hover:text-cta" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        );
      })}

      {tasks && comps.length > 0 && (
        <section className={regular.length ? "mt-8" : ""}>
          <h2 className="mb-3 text-[15px] font-semibold text-text">Competitions</h2>
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border shadow-sm">
            {comps.map((lab) => <CompetitionRow key={lab.id} lab={lab} onOpen={() => onCompetition(lab.id)} />)}
          </ul>
        </section>
      )}

      {tasks && <SandboxLabs studentId={studentId} onOpen={(lab) => onSandbox(lab.id)} />}

      {tasks && (
        <section className="mt-8">
          <h2 className="mb-3 text-[15px] font-semibold text-text">Learn and practice</h2>
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border shadow-sm">
            <li><LearnCard onOpen={onLearn} /></li>
            {tasks.map((t) => (
              <li key={t.id}>
                <button
                  onClick={() => void pick(t)}
                  disabled={!!opening}
                  className="group flex w-full items-center gap-4 px-5 py-3.5 text-left border border-transparent transition-[border-color,transform,box-shadow] hover:border-border-strong disabled:cursor-wait"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-cta/40 text-cta">
                    {opening === t.id ? <Spinner /> : <Code2 className="size-4" />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <strong className="block text-sm font-medium text-text">{t.title}</strong>
                    <span className="line-clamp-1 text-[13px] text-muted">{t.prompt}</span>
                  </span>
                  <span className="hidden gap-1.5 sm:flex">
                    <Badge>Python</Badge>
                    <Badge>{t.starter_code ? "Starter code" : "Blank file"}</Badge>
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-faint transition-colors group-hover:text-cta" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function greeting(h = new Date().getHours()) {
  if (h < 5) return "Up late";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

/** The top of the student home: a greeting and one line on what is waiting. */
function Hero({ studentId, labs, comps, loaded }: { studentId: string; labs: Lab[]; comps: Lab[]; loaded: boolean }) {
  const left = labs.reduce((n, l) => n + l.questions.filter((q) => !q.submitted).length, 0);
  const total = labs.reduce((n, l) => n + l.questions.length, 0);
  const live = comps.some((c) => c.state === "live");
  const headline = !loaded ? "Loading your labs…"
    : live ? "A competition is live. Go get it."
    : left ? `${left} question${left === 1 ? "" : "s"} waiting. Let's build.`
    : total ? "All caught up. Nice work."
    : "Fresh start. Nothing due.";
  return (
    <header className="mb-10">
      <p className="text-sm text-muted">
        {greeting()}, <span className="font-mono text-text">{studentId}</span>
      </p>
      <h1 className="mt-1 text-[32px] font-bold leading-tight text-text sm:text-[40px]">{headline}</h1>
      <p className="mt-2 text-sm text-muted">
        Recording starts when the editor opens.
        {total > 0 && <span className="ml-2 tabular-nums text-faint">{total - left} of {total} done across your labs</span>}
      </p>
    </header>
  );
}

const COMP_STATE = {
  waiting: { label: "Lobby open", tone: "accent" as const, cta: "Join the lobby" },
  live: { label: "Live now", tone: "success" as const, cta: "Enter" },
  ended: { label: "Finished", tone: "neutral" as const, cta: "See results" },
};

function CompetitionRow({ lab, onOpen }: { lab: Lab; onOpen: () => void }) {
  const st = COMP_STATE[lab.state ?? "waiting"];
  return (
    <li>
      <button onClick={onOpen} className="group flex w-full items-center gap-4 px-5 py-4 text-left border border-transparent transition-[border-color,transform,box-shadow] hover:border-border-strong">
        <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-gold/40 text-gold"><Trophy className="size-4" /></span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <strong className="text-sm font-medium text-text">{lab.title}</strong>
            <Badge tone={st.tone}>{lab.state === "live" && <LiveDot tone="success" />}{st.label}</Badge>
          </span>
          <span className="mt-0.5 line-clamp-1 block text-[13px] text-muted">
            {lab.description || "A class competition: solve the questions, pass the tests, climb the board."}
          </span>
          <span className="mt-0.5 block text-xs tabular-nums text-faint">
            {lab.n_questions} question{lab.n_questions === 1 ? "" : "s"}
            {lab.duration_s ? ` · ${Math.round(lab.duration_s / 60)} minutes` : ""}
            {lab.joined ? " · you're in" : ""}
          </span>
        </span>
        <span className="flex items-center gap-1 text-sm font-semibold text-cta">
          {st.cta}<ChevronRight className="size-4" />
        </span>
      </button>
    </li>
  );
}
