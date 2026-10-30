import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowUpRight, CheckCircle2, Code2, NotebookPen, Play, Trophy } from "lucide-react";
import { api, type Lab, type Task } from "../api";
import { Badge, Button, LiveDot, Spinner, cn, item, spring, stagger } from "../ui";
import { LearnCard } from "../learn/Learn";

/** Where "Start/Continue lab" lands: the first question not finished yet. */
const firstOpen = (lab: Lab) => Math.max(0, lab.questions.findIndex((q) => !q.submitted));

export function Tasks({ studentId, onPick, onOpenLab, onCompetition, onLearn }: {
  studentId: string;
  onPick: (task: Task) => Promise<void>;
  /** opens the whole lab as one sitting, on question `start` */
  onOpenLab: (lab: Lab, start: number) => Promise<void>;
  onCompetition: (labId: string) => void;
  /** the always-open learning lab */
  onLearn: () => void;
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

  return (
    <div className="w-full max-w-4xl">
      <motion.div variants={stagger()} initial="initial" animate="animate">
        <motion.h1 variants={item} className="text-2xl font-semibold tracking-tight text-text">
          {labs.length ? "Your labs" : "Choose a task"}
        </motion.h1>
        <motion.p variants={item} className="mt-1 text-sm text-muted">
          Signed in as <span className="font-mono text-text">{studentId}</span>. Recording starts when the editor opens.
        </motion.p>
      </motion.div>

      {error && <p className="mt-6 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {!tasks && !error && <div className="mt-10 flex justify-center text-muted"><Spinner className="size-5" /></div>}

      {tasks && labs.map((lab, li) => lab.kind === "competition" ? (
        <CompetitionCard key={lab.id} lab={lab} delay={0.1 + li * 0.08} onOpen={() => onCompetition(lab.id)} />
      ) : (
        <motion.section key={lab.id} variants={stagger(0.06, 0.1 + li * 0.08)} initial="initial" animate="animate" className="mt-7">
          <motion.div variants={item} className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text">
                <NotebookPen className="size-4 text-accent" /> {lab.title}
                {lab.draft && <Badge tone="warn">Draft: students can't see it yet</Badge>}
              </h2>
              {lab.description && <p className="mt-0.5 max-w-2xl text-[13px] text-muted">{lab.description}</p>}
            </div>
            <span className="flex items-center gap-3">
              <span className="text-xs text-faint">
                {lab.questions.filter((q) => q.submitted).length} of {lab.questions.length} finished
              </span>
              <Button variant="primary" size="sm" onClick={() => void pick(lab.questions[firstOpen(lab)], lab, firstOpen(lab))} disabled={!!opening}>
                {opening === lab.questions[firstOpen(lab)].id ? <Spinner className="size-3.5" /> : <Play className="size-3.5 fill-current" />}
                {lab.questions.some((q) => q.sessions) ? "Continue lab" : "Start lab"}
              </Button>
            </span>
          </motion.div>
          <div className="grid gap-2.5">
            {lab.questions.map((q, i) => (
              <motion.button
                key={q.id}
                variants={item}
                whileHover={{ x: 3 }}
                whileTap={{ scale: 0.99 }}
                transition={spring}
                onClick={() => void pick(q, lab, i)}
                disabled={!!opening}
                title="Opens the whole lab at this question; you can move between questions in the editor"
                className="group flex items-center gap-4 rounded-xl border border-border bg-surface px-4 py-3.5 text-left shadow-sm transition-[border-color,box-shadow] duration-200 hover:border-accent/40 hover:shadow-md disabled:cursor-wait"
              >
                <span className={cn(
                  "grid size-8 shrink-0 place-items-center rounded-lg font-mono text-xs font-semibold",
                  q.submitted ? "bg-success-soft text-success" : "bg-accent-soft text-accent",
                )}>
                  {opening === q.id ? <Spinner /> : q.submitted ? <CheckCircle2 className="size-4" /> : i + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <strong className="block text-sm font-semibold text-text">{q.title}</strong>
                  <span className="line-clamp-1 text-[13px] text-muted">{q.prompt}</span>
                </span>
                {q.submitted ? <Badge tone="success">Finished</Badge> : q.sessions ? <Badge>Started</Badge> : null}
                <ArrowUpRight className="size-4 shrink-0 text-faint transition-[transform,color] duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent" />
              </motion.button>
            ))}
          </div>
        </motion.section>
      ))}

      {tasks && <LearnCard onOpen={onLearn} delay={0.15 + labs.length * 0.08} />}

      {tasks && (
        <>
          {labs.length > 0 && (
            <motion.h2 initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { delay: 0.3 } }}
              className="mt-10 text-[13px] font-semibold uppercase tracking-[0.12em] text-faint">
              Practice
            </motion.h2>
          )}
          <motion.div variants={stagger(0.07, labs.length ? 0.35 : 0.15)} initial="initial" animate="animate"
            className={cn("grid gap-4 sm:grid-cols-2 lg:grid-cols-3", labs.length ? "mt-3" : "mt-7")}>
            {tasks.map((t) => (
              <motion.button
                key={t.id}
                variants={item}
                whileHover={{ y: -3 }}
                whileTap={{ scale: 0.985 }}
                transition={spring}
                onClick={() => void pick(t)}
                disabled={!!opening}
                className="group relative flex flex-col items-start gap-3 rounded-2xl border border-border bg-surface p-5 text-left shadow-sm transition-[border-color,box-shadow] duration-200 hover:border-accent/40 hover:shadow-md disabled:cursor-wait"
              >
                <div className="flex w-full items-center justify-between">
                  <span className="grid size-9 place-items-center rounded-xl bg-accent-soft text-accent">
                    {opening === t.id ? <Spinner /> : <Code2 className="size-4" />}
                  </span>
                  <ArrowUpRight className="size-4 text-faint transition-[transform,color] duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent" />
                </div>
                <strong className="text-[15px] font-semibold text-text">{t.title}</strong>
                <span className="line-clamp-3 text-[13px] leading-relaxed text-muted">{t.prompt}</span>
                <div className="mt-auto flex gap-2 pt-1">
                  <Badge>Python</Badge>
                  <Badge>{t.starter_code ? "Starter code" : "Blank file"}</Badge>
                </div>
              </motion.button>
            ))}
          </motion.div>
        </>
      )}
    </div>
  );
}

const COMP_STATE = {
  waiting: { label: "Lobby open", tone: "accent" as const, cta: "Join the lobby" },
  live: { label: "Live now", tone: "success" as const, cta: "Enter" },
  ended: { label: "Finished", tone: "neutral" as const, cta: "See results" },
};

function CompetitionCard({ lab, delay, onOpen }: { lab: Lab; delay: number; onOpen: () => void }) {
  const st = COMP_STATE[lab.state ?? "waiting"];
  return (
    <motion.button
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0, transition: { delay, ...spring } }}
      whileHover={{ y: -3 }} whileTap={{ scale: 0.99 }} transition={spring}
      onClick={onOpen}
      className="group relative mt-7 flex w-full items-center gap-5 overflow-clip rounded-2xl border border-gold/30 bg-surface p-5 text-left shadow-md transition-[border-color,box-shadow] duration-200 hover:border-gold/60 hover:shadow-lg"
    >
      <div className="pointer-events-none absolute -left-10 -top-16 size-48 rounded-full bg-gold/10 blur-3xl" />
      <span className="relative grid size-12 shrink-0 place-items-center rounded-2xl bg-gold-soft text-gold"><Trophy className="size-6" /></span>
      <span className="relative min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <strong className="text-[15px] font-semibold text-text">{lab.title}</strong>
          <Badge tone={st.tone}>{lab.state === "live" && <LiveDot tone="success" />}{st.label}</Badge>
        </span>
        <span className="mt-0.5 line-clamp-1 block text-[13px] text-muted">
          {lab.description || "A class competition: solve the questions, pass the tests, climb the board."}
        </span>
        <span className="mt-1 block text-xs text-faint">
          {lab.n_questions} question{lab.n_questions === 1 ? "" : "s"}
          {lab.duration_s ? ` · ${Math.round(lab.duration_s / 60)} minutes` : ""}
          {lab.joined ? " · you're in" : ""}
        </span>
      </span>
      <span className="relative flex items-center gap-1 text-sm font-medium text-gold">
        {st.cta}<ArrowUpRight className="size-4 transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
      </span>
    </motion.button>
  );
}
