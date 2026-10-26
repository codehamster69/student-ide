import { useEffect, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronRight, ListChecks, Plus, Users, X } from "lucide-react";
import { Badge, Button, Card, Field, Input, Spinner, TextArea, cn, item, pop, stagger } from "../ui";
import { AuthError, get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { dayTime } from "../review/format";
import { STATUS, type LabDetail, type LabRow, type LabStatus } from "./api";

const TONE: Record<LabStatus, "neutral" | "success" | "warn"> = { draft: "neutral", open: "success", closed: "warn" };

/** #/teach: every lab the teacher has made, and a form to start a new one. */
export function Labs({ onAuthLost }: { onAuthLost: () => void }) {
  const [labs, setLabs] = useState<LabRow[] | null>(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    get<LabRow[]>("/api/teach/labs").then(setLabs)
      .catch((e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)));
  }, [onAuthLost]);

  return (
    <motion.div variants={stagger(0.06)} initial="initial" animate="animate" className="mx-auto max-w-[1100px] px-5 pb-20 pt-8">
      <motion.div variants={item} className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Labs</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            A lab is one sitting: a set of questions with starter code, assigned to the students who should see it.
            Every session a student records is linked to the lab and question they worked on.
          </p>
        </div>
        <Button variant="primary" onClick={() => setCreating(true)} disabled={creating}>
          <Plus className="size-4" /> New lab
        </Button>
      </motion.div>

      <AnimatePresence>{creating && <NewLab onClose={() => setCreating(false)} onAuthLost={onAuthLost} />}</AnimatePresence>

      {error && <Card className="mb-4 p-6 text-sm text-danger">{error}</Card>}

      {!labs && (
        <div className="grid gap-3">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-20 w-full rounded-2xl" />)}</div>
      )}

      {labs && labs.length === 0 && !creating && (
        <Card variants={item} className="grid place-items-center gap-3 px-6 py-14 text-center">
          <span className="grid size-11 place-items-center rounded-xl bg-accent-soft text-accent"><ListChecks className="size-5" /></span>
          <p className="text-sm font-medium text-text">No labs yet</p>
          <p className="max-w-sm text-sm text-muted">Create one, add a few questions, assign your students and open it when the class starts.</p>
          <Button variant="primary" className="mt-2" onClick={() => setCreating(true)}><Plus className="size-4" /> New lab</Button>
        </Card>
      )}

      {labs && labs.length > 0 && (
        <motion.ul variants={stagger(0.05, 0.1)} className="grid gap-3">
          {labs.map((l) => (
            <motion.li key={l.id} variants={item}>
              <a href={`#/teach/l/${l.id}`}
                className="group grid items-center gap-x-6 gap-y-2 rounded-2xl border border-border bg-surface px-5 py-4 shadow-sm transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-md md:grid-cols-[1fr_auto_auto_auto_1.25rem]">
                <span className="min-w-0">
                  <span className="flex items-center gap-2">
                    <strong className="truncate text-[15px] font-semibold text-text">{l.title}</strong>
                    <Badge tone={TONE[l.status]} className="h-5 px-2 text-[11px]">{STATUS[l.status].label}</Badge>
                  </span>
                  <span className="mt-0.5 block truncate text-[13px] text-muted">{l.description || "No description"}</span>
                </span>
                <Count icon={ListChecks} value={l.n_questions} label={l.n_questions === 1 ? "question" : "questions"} />
                <Count icon={Users} value={l.everyone ? "All" : l.n_roster} label={l.everyone ? "students" : "assigned"} />
                <span className="text-xs text-faint md:text-right">
                  {l.n_sessions ? `${l.n_started} started · ${l.n_sessions} sessions` : `edited ${dayTime(l.updated_at)}`}
                </span>
                <ChevronRight className="hidden size-4 text-faint transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-text md:block" />
              </a>
            </motion.li>
          ))}
        </motion.ul>
      )}
    </motion.div>
  );
}

function Count({ icon: Icon, value, label }: { icon: typeof Users; value: number | string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-sm text-muted">
      <Icon className="size-3.5 text-faint" />
      <span className="font-semibold tabular-nums text-text">{value}</span> {label}
    </span>
  );
}

function NewLab({ onClose, onAuthLost }: { onClose: () => void; onAuthLost: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const lab = await send<LabDetail>("POST", "/api/teach/labs", { title, description });
      location.hash = `#/teach/l/${lab.id}`;
    } catch (err) {
      if (err instanceof AuthError) return onAuthLost();
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <motion.div variants={pop} initial="initial" animate="animate" exit="exit" className="mb-5">
      <Card className="p-6">
        <form onSubmit={submit} className="grid gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-text">New lab</h2>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cancel"><X className="size-4" /></Button>
          </div>
          <Field label="Title">
            <Input autoFocus required maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Lab 5: Strings and dictionaries" />
          </Field>
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
