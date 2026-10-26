import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowUpRight, CheckCircle2, Code2, NotebookPen } from "lucide-react";
import { api, type Lab, type Task } from "../api";
import { Badge, Spinner, cn, item, spring, stagger } from "../ui";

export function Tasks({ studentId, onPick }: { studentId: string; onPick: (task: Task) => Promise<void> }) {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [labs, setLabs] = useState<Lab[]>([]);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api<Task[]>("/api/tasks"), api<Lab[]>(`/api/students/${encodeURIComponent(studentId)}/labs`)])
      .then(([t, l]) => { setLabs(l); setTasks(t); }, (e) => setError((e as Error).message));
  }, [studentId]);

  const pick = async (t: Task) => {
    if (opening) return;
    setOpening(t.id);
    try {
      await onPick(t);
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

      {tasks && labs.map((lab, li) => (
        <motion.section key={lab.id} variants={stagger(0.06, 0.1 + li * 0.08)} initial="initial" animate="animate" className="mt-7">
          <motion.div variants={item} className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text">
                <NotebookPen className="size-4 text-accent" /> {lab.title}
              </h2>
              {lab.description && <p className="mt-0.5 max-w-2xl text-[13px] text-muted">{lab.description}</p>}
            </div>
            <span className="text-xs text-faint">
              {lab.questions.filter((q) => q.submitted).length} of {lab.questions.length} finished
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
                onClick={() => void pick(q)}
                disabled={!!opening}
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
