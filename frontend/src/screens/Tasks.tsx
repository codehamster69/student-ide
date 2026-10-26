import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowUpRight, Code2 } from "lucide-react";
import { api, type Task } from "../api";
import { Badge, Spinner, item, spring, stagger } from "../ui";

export function Tasks({ studentId, onPick }: { studentId: string; onPick: (task: Task) => Promise<void> }) {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Task[]>("/api/tasks").then(setTasks, (e) => setError((e as Error).message));
  }, []);

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
        <motion.h1 variants={item} className="text-2xl font-semibold tracking-tight text-text">Choose a task</motion.h1>
        <motion.p variants={item} className="mt-1 text-sm text-muted">
          Signed in as <span className="font-mono text-text">{studentId}</span>. Recording starts when the editor opens.
        </motion.p>
      </motion.div>

      {error && <p className="mt-6 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {!tasks && !error && <div className="mt-10 flex justify-center text-muted"><Spinner className="size-5" /></div>}

      {tasks && (
        <motion.div variants={stagger(0.07, 0.15)} initial="initial" animate="animate" className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
      )}
    </div>
  );
}
