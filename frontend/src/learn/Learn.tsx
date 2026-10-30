import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowLeft, ArrowUpRight, BookOpen, CheckCircle2, Info, Play } from "lucide-react";
import { api, type LearnTrack, type Task } from "../api";
import { LANGUAGES } from "../teach/api";
import { Badge, Button, Spinner, cn, item, spring, stagger } from "../ui";

/** Where "Start/Continue" lands: the first lesson not done yet. */
const firstOpen = (t: LearnTrack) => Math.max(0, t.lessons.findIndex((l) => !l.submitted));

/**
 * The learning lab's front page: every track and its lessons, with the
 * student's progress. Always open: no roster, no lab times, no teacher.
 */
export function Learn({ studentId, onOpen, onBack }: {
  studentId: string;
  /** opens the track in the editor at lesson `start` */
  onOpen: (track: LearnTrack, start: number) => Promise<void>;
  onBack: () => void;
}) {
  const [tracks, setTracks] = useState<LearnTrack[] | null>(null);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<LearnTrack[]>(`/api/learn?student_id=${encodeURIComponent(studentId)}`).then(setTracks, (e) => setError((e as Error).message));
  }, [studentId]);

  const open = async (t: LearnTrack, i: number, l: Task) => {
    if (opening) return;
    setOpening(l.id);
    try {
      await onOpen(t, i);
    } catch (e) {
      setError((e as Error).message);
      setOpening(null);
    }
  };

  return (
    <div className="w-full max-w-4xl">
      <motion.div variants={stagger()} initial="initial" animate="animate">
        <motion.div variants={item}>
          <Button variant="ghost" size="sm" onClick={onBack} className="-ml-2 text-muted"><ArrowLeft className="size-3.5" />Your labs</Button>
        </motion.div>
        <motion.h1 variants={item} className="mt-2 flex items-center gap-2 text-2xl font-semibold tracking-tight text-text">
          <BookOpen className="size-6 text-accent" /> Learning lab
        </motion.h1>
        <motion.p variants={item} className="mt-1 max-w-2xl text-sm text-muted">
          Short lessons that explain one idea each, next to code you can change and run. Break things on purpose:
          that is how you learn what each line does. Each lesson ends with a small exercise you can Check.
        </motion.p>
        <motion.p variants={item} className="mt-3 flex max-w-2xl items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">
          <Info className="mt-0.5 size-3.5 shrink-0 text-accent" />
          <span>
            Open any time. Your typing here is recorded like in a lab, for the research study only. It is kept apart:
            never compared with your lab work, never shown to teachers and never marked.
          </span>
        </motion.p>
      </motion.div>

      {error && <p className="mt-6 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}
      {!tracks && !error && <div className="mt-10 flex justify-center text-muted"><Spinner className="size-5" /></div>}

      {tracks?.map((t, ti) => {
        const done = t.lessons.filter((l) => l.submitted).length;
        const at = firstOpen(t);
        return (
          <motion.section key={t.id} variants={stagger(0.04, 0.1 + ti * 0.08)} initial="initial" animate="animate" className="mt-8">
            <motion.div variants={item} className="mb-3 flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text">
                  <span className="size-2.5 rounded-sm" style={{ background: LANGUAGES[t.language].color }} />
                  {t.title}
                </h2>
                {t.summary && <p className="mt-0.5 max-w-2xl text-[13px] text-muted">{t.summary}</p>}
              </div>
              <span className="flex items-center gap-3">
                <span className="text-xs text-faint">{done} of {t.lessons.length} done</span>
                <Button variant="primary" size="sm" onClick={() => void open(t, at, t.lessons[at])} disabled={!!opening}>
                  {opening === t.lessons[at].id ? <Spinner className="size-3.5" /> : <Play className="size-3.5 fill-current" />}
                  {t.lessons.some((l) => l.sessions) ? "Continue" : "Start"}
                </Button>
              </span>
            </motion.div>
            <div className="grid gap-2 sm:grid-cols-2">
              {t.lessons.map((l, i) => (
                <motion.button
                  key={l.id}
                  variants={item}
                  whileHover={{ x: 3 }}
                  whileTap={{ scale: 0.99 }}
                  transition={spring}
                  onClick={() => void open(t, i, l)}
                  disabled={!!opening}
                  className="group flex items-center gap-3.5 rounded-xl border border-border bg-surface px-4 py-3 text-left shadow-sm transition-[border-color,box-shadow] duration-200 hover:border-accent/40 hover:shadow-md disabled:cursor-wait"
                >
                  <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg font-mono text-xs font-semibold",
                    l.submitted ? "bg-success-soft text-success" : "bg-accent-soft text-accent")}>
                    {opening === l.id ? <Spinner /> : l.submitted ? <CheckCircle2 className="size-4" /> : i + 1}
                  </span>
                  <span className="min-w-0 flex-1">
                    <strong className="block text-sm font-semibold text-text">{l.title}</strong>
                    <span className="line-clamp-1 text-[13px] text-muted">{l.summary}</span>
                  </span>
                  <ArrowUpRight className="size-4 shrink-0 text-faint transition-[transform,color] duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent" />
                </motion.button>
              ))}
            </div>
          </motion.section>
        );
      })}
    </div>
  );
}

/** The way in from the student's home page. */
export function LearnCard({ onOpen, delay = 0.2 }: { onOpen: () => void; delay?: number }) {
  return (
    <motion.button
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0, transition: { delay, ...spring } }}
      whileHover={{ y: -3 }} whileTap={{ scale: 0.99 }} transition={spring}
      onClick={onOpen}
      className="group relative mt-7 flex w-full items-center gap-5 overflow-clip rounded-2xl border border-accent/25 bg-surface p-5 text-left shadow-md transition-[border-color,box-shadow] duration-200 hover:border-accent/50 hover:shadow-lg"
    >
      <div className="pointer-events-none absolute -left-10 -top-16 size-48 rounded-full bg-accent/10 blur-3xl" />
      <span className="relative grid size-12 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent"><BookOpen className="size-6" /></span>
      <span className="relative min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <strong className="text-[15px] font-semibold text-text">Learning lab</strong>
          <Badge tone="accent">Always open</Badge>
        </span>
        <span className="mt-0.5 block text-[13px] text-muted">
          C, C++ and Python from beginner to advanced, one idea at a time: read a short lesson, change the example, run it, then try the exercise.
        </span>
      </span>
      <span className="relative flex items-center gap-1 text-sm font-medium text-accent">
        Open<ArrowUpRight className="size-4 transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
      </span>
    </motion.button>
  );
}
