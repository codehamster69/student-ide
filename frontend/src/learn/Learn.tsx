import { useEffect, useState } from "react";
import { ArrowLeft, BookOpen, CheckCircle2, ChevronRight, Info, Play } from "lucide-react";
import { api, type LearnTrack, type Task } from "../api";
import { LANGUAGES } from "../teach/api";
import { Badge, Button, PageHeader, Spinner, cn } from "../ui";

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
    <div className="w-full max-w-[1120px]">
      <Button variant="ghost" size="sm" onClick={onBack} className="-ml-2 mb-2 text-muted"><ArrowLeft className="size-3.5" />Your labs</Button>
      <PageHeader
        title="Learning lab"
        description="Short lessons that explain one idea each, next to code you can change and run. Break things on purpose: that is how you learn what each line does. Each lesson ends with a small exercise you can Check."
      />
      <p className="-mt-2 mb-2 flex max-w-3xl items-start gap-2 rounded-lg border border-border px-3 py-2 text-xs text-muted">
        <Info className="mt-0.5 size-3.5 shrink-0 text-accent" />
        <span>
          Open any time. Your typing here is recorded like in a lab, for the research study only. It is kept apart:
          never compared with your lab work, never shown to teachers and never marked.
        </span>
      </p>

      {error && <p className="mt-6 rounded-lg border border-danger/40 px-3 py-2 text-sm text-danger">{error}</p>}
      {!tracks && !error && <div className="mt-10 flex justify-center text-muted"><Spinner className="size-5" /></div>}

      {tracks?.map((t) => {
        const done = t.lessons.filter((l) => l.submitted).length;
        const at = firstOpen(t);
        return (
          <section key={t.id} className="mt-8">
            <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text">
                  <span className="size-2.5 rounded-sm" style={{ background: LANGUAGES[t.language].color }} />
                  {t.title}
                </h2>
                {t.summary && <p className="mt-0.5 max-w-2xl text-[13px] text-muted">{t.summary}</p>}
              </div>
              <span className="flex items-center gap-3">
                <span className="text-xs tabular-nums text-faint">{done} of {t.lessons.length} done</span>
                <Button variant="primary" size="sm" onClick={() => void open(t, at, t.lessons[at])} disabled={!!opening}>
                  {opening === t.lessons[at].id ? <Spinner className="size-3.5" /> : <Play className="size-3.5 fill-current" />}
                  {t.lessons.some((l) => l.sessions) ? "Continue" : "Start"}
                </Button>
              </span>
            </div>
            <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border shadow-sm">
              {t.lessons.map((l, i) => (
                <li key={l.id}>
                  <button
                    onClick={() => void open(t, i, l)}
                    disabled={!!opening}
                    className="group flex w-full items-center gap-4 px-5 py-3 text-left border border-transparent transition-[border-color,transform,box-shadow] hover:border-border-strong disabled:cursor-wait"
                  >
                    <span className={cn("grid size-7 shrink-0 place-items-center rounded-lg text-xs font-semibold tabular-nums",
                      l.submitted ? "border border-success/40 text-success" : "border border-cta/40 text-cta")}>
                      {opening === l.id ? <Spinner /> : l.submitted ? <CheckCircle2 className="size-4" /> : i + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <strong className="block text-sm font-medium text-text">{l.title}</strong>
                      <span className="line-clamp-1 text-[13px] text-muted">{l.summary}</span>
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-faint transition-colors group-hover:text-cta" />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

/** The way in from the student's home page: one row of the "Learn and practice" list. */
export function LearnCard({ onOpen }: { onOpen: () => void }) {
  return (
    <button onClick={onOpen} className="group flex w-full items-center gap-4 px-5 py-3.5 text-left border border-transparent transition-[border-color,transform,box-shadow] hover:border-border-strong">
      <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-cta/40 text-cta"><BookOpen className="size-4" /></span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-2">
          <strong className="text-sm font-medium text-text">Learning lab</strong>
          <Badge tone="accent">Always open</Badge>
        </span>
        <span className="mt-0.5 line-clamp-2 block text-[13px] text-muted">
          C, C++ and Python from beginner to advanced, one idea at a time: read a short lesson, change the example, run it, then try the exercise.
        </span>
      </span>
      <ChevronRight className="size-4 shrink-0 text-faint transition-colors group-hover:text-cta" />
    </button>
  );
}
