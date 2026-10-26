import { useCallback, useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import {
  ArrowDown, ArrowLeft, ArrowUp, Check, CheckCircle2, CircleDashed, Code2, Pencil, Plus, Trash2, UserPlus, Users,
} from "lucide-react";
import { Badge, Button, Card, Checkbox, Dialog, Field, Input, Spinner, TextArea, cn, item, pop, spring, stagger } from "../ui";
import { AuthError, get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { parseIds, STATUS, type LabDetail, type LabStatus, type Question, type QuestionFields } from "./api";

const BLANK: QuestionFields = { title: "", prompt: "", starter_code: "", sample_input: "" };

/** #/teach/l/<id>: edit one lab's questions, roster and status, and watch progress. */
export function LabEditor({ id, onAuthLost }: { id: string; onAuthLost: () => void }) {
  const [lab, setLab] = useState<LabDetail | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | null>(null); // question id, or "new"
  const [confirmDelete, setConfirmDelete] = useState(false);

  const fail = useCallback((e: unknown) => {
    if (e instanceof AuthError) onAuthLost();
    else setError((e as Error).message);
  }, [onAuthLost]);

  useEffect(() => { get<LabDetail>(`/api/teach/labs/${id}`).then(setLab, fail); }, [id, fail]);

  /** Every write returns the whole lab, so the screen never drifts from the server. */
  const write = useCallback(async (method: string, path: string, body?: unknown) => {
    setError("");
    try {
      const next = await send<LabDetail>(method, path, body);
      setLab(next);
      return true;
    } catch (e) {
      fail(e);
      return false;
    }
  }, [fail]);

  if (!lab) {
    return (
      <div className="mx-auto max-w-[1240px] px-5 pt-8">
        {error ? <Card className="p-6 text-sm text-danger">{error}</Card> : <Skeleton className="h-40 w-full rounded-2xl" />}
      </div>
    );
  }

  const move = (i: number, d: -1 | 1) => {
    const ids = lab.questions.map((q) => q.id);
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    void write("PUT", `/api/teach/labs/${lab.id}/order`, { question_ids: ids });
  };

  return (
    <motion.div variants={stagger(0.06)} initial="initial" animate="animate" className="mx-auto max-w-[1240px] px-5 pb-20 pt-6">
      <motion.a variants={item} href="#/teach" className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted transition-colors hover:text-text">
        <ArrowLeft className="size-4" /> All labs
      </motion.a>

      <motion.div variants={item} className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <LabHeading lab={lab} onSave={(f) => write("PATCH", `/api/teach/labs/${lab.id}`, f)} />
        <div className="flex items-center gap-2">
          <StatusSwitch value={lab.status} disabled={!lab.questions.length}
            onChange={(status) => void write("PATCH", `/api/teach/labs/${lab.id}`, { status })} />
          <Button variant="ghost" size="icon" aria-label="Delete lab" onClick={() => setConfirmDelete(true)}
            title={lab.n_sessions ? "Students have recorded work here; close the lab instead" : "Delete lab"} disabled={lab.n_sessions > 0}>
            <Trash2 className="size-4" />
          </Button>
        </div>
      </motion.div>

      <AnimatePresence>
        {error && (
          <motion.p key={error} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className="mb-4 overflow-hidden rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{error}</motion.p>
        )}
      </AnimatePresence>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_380px]">
        <motion.section variants={item}>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-[13px] font-semibold uppercase tracking-[0.12em] text-faint">
              Questions <span className="ml-1 tabular-nums text-muted">{lab.questions.length}</span>
            </h2>
            <Button size="sm" onClick={() => setEditing("new")} disabled={editing === "new"}>
              <Plus className="size-3.5" /> Add question
            </Button>
          </div>

          <LayoutGroup>
            <motion.ol layout className="grid gap-3">
              <AnimatePresence initial={false}>
                {lab.questions.map((q, i) => (
                  <motion.li key={q.id} layout transition={spring} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.15 } }}>
                    {editing === q.id ? (
                      <QuestionForm index={i} initial={q} onCancel={() => setEditing(null)}
                        onSave={async (f) => { if (await write("PATCH", `/api/teach/questions/${q.id}`, f)) setEditing(null); }}
                        onDelete={q.n_sessions ? undefined : async () => { if (await write("DELETE", `/api/teach/questions/${q.id}`)) setEditing(null); }} />
                    ) : (
                      <QuestionCard q={q} index={i} first={i === 0} last={i === lab.questions.length - 1}
                        onEdit={() => setEditing(q.id)} onMove={(d) => move(i, d)} />
                    )}
                  </motion.li>
                ))}
                {editing === "new" && (
                  <motion.li key="new" layout variants={pop} initial="initial" animate="animate" exit="exit">
                    <QuestionForm index={lab.questions.length} initial={BLANK} onCancel={() => setEditing(null)}
                      onSave={async (f) => { if (await write("POST", `/api/teach/labs/${lab.id}/questions`, f)) setEditing(null); }} />
                  </motion.li>
                )}
              </AnimatePresence>
            </motion.ol>
          </LayoutGroup>

          {lab.questions.length === 0 && editing !== "new" && (
            <Card className="grid place-items-center gap-2 px-6 py-12 text-center">
              <span className="grid size-10 place-items-center rounded-xl bg-accent-soft text-accent"><Code2 className="size-5" /></span>
              <p className="text-sm font-medium text-text">Add the first question</p>
              <p className="max-w-sm text-sm text-muted">Each question has a prompt, optional starter code that opens in the editor, and a sample input.</p>
              <Button variant="primary" size="sm" className="mt-2" onClick={() => setEditing("new")}><Plus className="size-3.5" /> Add question</Button>
            </Card>
          )}
        </motion.section>

        <motion.aside variants={item} className="grid gap-5 lg:sticky lg:top-20">
          <Assign lab={lab} onSave={(student_ids, everyone) => write("PUT", `/api/teach/labs/${lab.id}/roster`, { student_ids, everyone })} onAuthLost={onAuthLost} />
          <Progress lab={lab} />
        </motion.aside>
      </div>

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)} icon={<Trash2 className="size-5" />}
        title="Delete this lab?" description="Its questions and roster go too. No student has recorded anything here yet, so nothing else is lost."
        actions={<>
          <Button onClick={() => setConfirmDelete(false)} data-autofocus>Keep</Button>
          <Button variant="danger" onClick={async () => { if (await write("DELETE", `/api/teach/labs/${lab.id}`)) location.hash = "#/teach"; }}>Delete</Button>
        </>} />
    </motion.div>
  );
}

function LabHeading({ lab, onSave }: { lab: LabDetail; onSave: (f: { title?: string; description?: string }) => Promise<boolean> }) {
  const [title, setTitle] = useState(lab.title);
  const [description, setDescription] = useState(lab.description);
  const [saved, setSaved] = useState(false);
  useEffect(() => { setTitle(lab.title); setDescription(lab.description); }, [lab.title, lab.description]);

  const commit = async () => {
    const f: { title?: string; description?: string } = {};
    if (title.trim() && title.trim() !== lab.title) f.title = title.trim();
    if (description !== lab.description) f.description = description;
    if (!Object.keys(f).length) return setTitle(lab.title);
    if (await onSave(f)) { setSaved(true); window.setTimeout(() => setSaved(false), 1400); }
  };

  return (
    <div className="min-w-0 flex-1">
      <div className="flex items-center gap-3">
        <input value={title} onChange={(e) => setTitle(e.target.value)} onBlur={() => void commit()} maxLength={120}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()} aria-label="Lab title"
          className="-mx-2 min-w-0 flex-1 rounded-lg bg-transparent px-2 py-0.5 text-2xl font-semibold tracking-tight text-text outline-none transition-colors hover:bg-surface-2 focus:bg-surface focus:ring-4 focus:ring-accent/15" />
        <AnimatePresence>
          {saved && (
            <motion.span initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
              className="inline-flex items-center gap-1 text-xs font-medium text-success"><Check className="size-3.5" /> Saved</motion.span>
          )}
        </AnimatePresence>
      </div>
      <textarea value={description} onChange={(e) => setDescription(e.target.value)} onBlur={() => void commit()} rows={1} maxLength={4000}
        placeholder="Add instructions for students" aria-label="Instructions for students"
        className="-mx-2 mt-1 block w-full max-w-3xl resize-none rounded-lg bg-transparent px-2 py-1 text-sm text-muted outline-none [field-sizing:content] placeholder:text-faint hover:bg-surface-2 focus:bg-surface focus:ring-4 focus:ring-accent/15" />
    </div>
  );
}

function StatusSwitch({ value, onChange, disabled }: { value: LabStatus; onChange: (s: LabStatus) => void; disabled: boolean }) {
  return (
    <LayoutGroup id="lab-status">
      <div className="flex rounded-lg border border-border bg-surface p-0.5 shadow-sm" role="radiogroup" aria-label="Lab status">
        {(Object.keys(STATUS) as LabStatus[]).map((s) => {
          const off = disabled && s === "open";
          return (
            <button key={s} role="radio" aria-checked={value === s} disabled={off} title={off ? "Add a question first" : STATUS[s].about}
              onClick={() => value !== s && onChange(s)}
              className={cn("relative h-8 rounded-md px-3 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45",
                value === s ? (s === "open" ? "text-success" : "text-text") : "text-muted hover:text-text")}>
              {value === s && (
                <motion.span layoutId="status-pill" transition={spring}
                  className={cn("absolute inset-0 rounded-md", s === "open" ? "bg-success-soft" : "bg-surface-3")} />
              )}
              <span className="relative flex items-center gap-1.5">
                {s === "open" && <span className={cn("size-1.5 rounded-full", value === "open" ? "bg-success" : "bg-faint")} />}
                {STATUS[s].label}
              </span>
            </button>
          );
        })}
      </div>
    </LayoutGroup>
  );
}

function QuestionCard({ q, index, first, last, onEdit, onMove }: {
  q: Question; index: number; first: boolean; last: boolean; onEdit: () => void; onMove: (d: -1 | 1) => void;
}) {
  return (
    <Card className="group flex gap-4 p-4 shadow-sm transition-shadow hover:shadow-md">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-soft font-mono text-xs font-semibold text-accent">{index + 1}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <strong className="text-[15px] font-semibold text-text">{q.title}</strong>
          {q.starter_code && <Badge className="h-5 px-2 text-[11px]">Starter code</Badge>}
          {q.n_sessions > 0 && <Badge tone="accent" className="h-5 px-2 text-[11px]">{q.n_sessions} session{q.n_sessions === 1 ? "" : "s"}</Badge>}
        </div>
        <p className="mt-1 line-clamp-2 whitespace-pre-line text-[13px] leading-relaxed text-muted">{q.prompt || "No prompt yet"}</p>
        {q.starter_code && (
          <pre className="mt-2.5 max-h-20 overflow-hidden rounded-lg border border-border bg-surface-2 px-3 py-2 font-mono text-[11.5px] leading-relaxed text-muted [mask-image:linear-gradient(to_bottom,black_60%,transparent)]">{q.starter_code}</pre>
        )}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-1 opacity-70 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
        <Button size="sm" onClick={onEdit}><Pencil className="size-3.5" /> Edit</Button>
        <div className="flex">
          <Button variant="ghost" size="icon" disabled={first} onClick={() => onMove(-1)} aria-label="Move up"><ArrowUp className="size-3.5" /></Button>
          <Button variant="ghost" size="icon" disabled={last} onClick={() => onMove(1)} aria-label="Move down"><ArrowDown className="size-3.5" /></Button>
        </div>
      </div>
    </Card>
  );
}

/** Tab in the starter-code box indents (four spaces) instead of leaving the field. */
function indentOnTab(e: KeyboardEvent<HTMLTextAreaElement>, set: (v: string) => void) {
  if (e.key !== "Tab" || e.shiftKey) return;
  e.preventDefault();
  const el = e.currentTarget;
  const { selectionStart: a, selectionEnd: b, value } = el;
  set(value.slice(0, a) + "    " + value.slice(b));
  requestAnimationFrame(() => el.setSelectionRange(a + 4, a + 4));
}

function QuestionForm({ index, initial, onSave, onCancel, onDelete }: {
  index: number; initial: QuestionFields; onSave: (f: QuestionFields) => Promise<void>; onCancel: () => void; onDelete?: () => Promise<void>;
}) {
  const [f, setF] = useState<QuestionFields>({
    title: initial.title, prompt: initial.prompt, starter_code: initial.starter_code, sample_input: initial.sample_input,
  });
  const [busy, setBusy] = useState(false);
  const set = (k: keyof QuestionFields) => (v: string) => setF((p) => ({ ...p, [k]: v }));
  const isNew = !initial.title;

  const save = async () => { setBusy(true); await onSave(f); setBusy(false); };

  return (
    <Card className="border-accent/40 p-5 ring-4 ring-accent/10">
      <form onSubmit={(e) => { e.preventDefault(); void save(); }} className="grid gap-4">
        <div className="flex items-center gap-3">
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent text-xs font-semibold text-accent-fg">{index + 1}</span>
          <h3 className="text-sm font-semibold text-text">{isNew ? "New question" : "Edit question"}</h3>
        </div>
        <Field label="Title">
          <Input autoFocus required maxLength={120} value={f.title} onChange={(e) => set("title")(e.target.value)} placeholder="Anagram check" />
        </Field>
        <Field label="Prompt" hint="What the student reads beside the editor.">
          <TextArea rows={4} value={f.prompt} onChange={(e) => set("prompt")(e.target.value)}
            placeholder="Read two words, one per line. Print YES if they are anagrams of each other, otherwise NO." />
        </Field>
        <div className="grid gap-4 md:grid-cols-[1.5fr_1fr]">
          <Field label="Starter code" hint="Opens in the editor. Leave empty for a blank file.">
            <TextArea rows={6} spellCheck={false} value={f.starter_code} onChange={(e) => set("starter_code")(e.target.value)}
              onKeyDown={(e) => indentOnTab(e, set("starter_code"))} placeholder={"a = input()\nb = input()\n"}
              className="bg-surface-2 font-mono text-[12.5px] leading-relaxed" />
          </Field>
          <Field label="Sample input" hint="Prefilled in the input box.">
            <TextArea rows={6} spellCheck={false} value={f.sample_input} onChange={(e) => set("sample_input")(e.target.value)}
              placeholder={"listen\nsilent"} className="bg-surface-2 font-mono text-[12.5px] leading-relaxed" />
          </Field>
        </div>
        {!isNew && (
          <p className="text-xs text-faint">Sessions already recorded keep the version of the question the student saw.</p>
        )}
        <div className="flex items-center gap-2">
          {onDelete && !isNew && (
            <Button variant="ghost" size="sm" className="text-danger hover:text-danger" onClick={() => void onDelete()}>
              <Trash2 className="size-3.5" /> Remove
            </Button>
          )}
          <div className="ml-auto flex gap-2">
            <Button size="sm" onClick={onCancel}>Cancel</Button>
            <Button size="sm" type="submit" variant="primary" disabled={busy || !f.title.trim()}>
              {busy ? <Spinner className="size-3.5" /> : <Check className="size-3.5" />} {isNew ? "Add question" : "Save"}
            </Button>
          </div>
        </div>
      </form>
    </Card>
  );
}

function Assign({ lab, onSave, onAuthLost }: {
  lab: LabDetail; onSave: (ids: string[], everyone: boolean) => Promise<boolean>; onAuthLost: () => void;
}) {
  const [known, setKnown] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  useEffect(() => {
    get<{ student_id: string }[]>("/api/teach/students").then((s) => setKnown(s.map((x) => x.student_id)))
      .catch((e) => e instanceof AuthError && onAuthLost());
  }, [onAuthLost]);

  const roster = new Set(lab.roster);
  const add = async (ids: string[]) => { if (await onSave([...lab.roster, ...ids], lab.everyone)) setDraft(""); };
  const remove = (id: string) => void onSave(lab.roster.filter((s) => s !== id), lab.everyone);
  const suggestions = known.filter((s) => !roster.has(s));

  return (
    <Card className="p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text"><Users className="size-4 text-accent" /> Assigned to</h2>
      <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-border bg-surface-2/60 p-3">
        <Checkbox checked={lab.everyone} onChange={(e) => void onSave(lab.roster, e.target.checked)} className="mt-0.5" />
        <span>
          <span className="block text-[13px] font-medium text-text">Everyone who signs in</span>
          <span className="block text-xs text-muted">Handy for an open practice lab. Turn off to use the list below.</span>
        </span>
      </label>

      <motion.div animate={{ opacity: lab.everyone ? 0.45 : 1 }} className={cn("mt-4", lab.everyone && "pointer-events-none")} aria-disabled={lab.everyone}>
        <form onSubmit={(e) => { e.preventDefault(); const ids = parseIds(draft); if (ids.length) void add(ids); }} className="flex gap-2">
          <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Roll numbers"
            className="h-9 font-mono text-[13px]" aria-label="Add roll numbers" />
          <Button type="submit" size="sm" className="h-9" disabled={!parseIds(draft).length}><UserPlus className="size-3.5" /> Add</Button>
        </form>
        <p className="mt-1.5 text-xs text-faint">Paste a whole class list; commas, spaces and new lines all work.</p>

        <div className="mt-3 flex min-h-8 flex-wrap gap-1.5">
          <AnimatePresence initial={false}>
            {lab.roster.map((s) => (
              <motion.button key={s} layout initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.85 }}
                transition={spring} onClick={() => remove(s)} title="Remove"
                className="group inline-flex h-7 items-center gap-1 rounded-full border border-accent/30 bg-accent-soft pl-2.5 pr-1.5 font-mono text-xs text-accent">
                {s}<span className="grid size-4 place-items-center rounded-full text-accent/70 group-hover:bg-accent group-hover:text-accent-fg">×</span>
              </motion.button>
            ))}
          </AnimatePresence>
          {lab.roster.length === 0 && <span className="self-center text-xs text-faint">Nobody assigned yet.</span>}
        </div>

        {suggestions.length > 0 && (
          <div className="mt-4 border-t border-border pt-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-medium text-muted">Students who have signed in</p>
              <button className="text-xs font-medium text-accent hover:underline" onClick={() => void add(suggestions)}>Add all</button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {suggestions.slice(0, 40).map((s) => (
                <button key={s} onClick={() => void add([s])}
                  className="h-7 rounded-full border border-border bg-surface px-2.5 font-mono text-xs text-muted transition-colors hover:border-accent/40 hover:text-text">
                  + {s}
                </button>
              ))}
            </div>
          </div>
        )}
      </motion.div>
    </Card>
  );
}

function Progress({ lab }: { lab: LabDetail }) {
  const students = useMemo(() => {
    const ids = new Set(lab.everyone ? [] : lab.roster);
    lab.progress.forEach((p) => ids.add(p.student_id));
    return [...ids].sort();
  }, [lab]);
  const cell = useMemo(() => {
    const m = new Map<string, { n: number; submitted: boolean }>();
    lab.progress.forEach((p) => m.set(`${p.student_id}|${p.question_id}`, p));
    return m;
  }, [lab.progress]);

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between px-5 pb-3 pt-5">
        <h2 className="text-sm font-semibold text-text">Progress</h2>
        <a href="#/review" className="text-xs font-medium text-accent hover:underline">Open review timeline</a>
      </div>
      {students.length === 0 || lab.questions.length === 0 ? (
        <p className="px-5 pb-5 text-xs text-muted">Once students start, you'll see who has started and finished each question.</p>
      ) : (
        <div className="max-h-[360px] overflow-auto border-t border-border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-surface-2/95 backdrop-blur">
              <tr>
                <th className="px-5 py-2 text-left font-semibold text-faint">Student</th>
                {lab.questions.map((q, i) => (
                  <th key={q.id} title={q.title} className="px-1.5 py-2 text-center font-mono font-semibold text-faint">Q{i + 1}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {students.map((s, si) => (
                <motion.tr key={s} initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { delay: Math.min(si, 15) * 0.02 } }}
                  className="border-t border-border/70">
                  <td className="px-5 py-1.5 font-mono text-text">{s}</td>
                  {lab.questions.map((q) => {
                    const c = cell.get(`${s}|${q.id}`);
                    return (
                      <td key={q.id} className="px-1.5 py-1.5 text-center"
                        title={c ? `${c.n} session${c.n === 1 ? "" : "s"}${c.submitted ? ", finished" : ""}` : "not started"}>
                        {c?.submitted ? <CheckCircle2 className="mx-auto size-4 text-success" />
                          : c ? <CircleDashed className="mx-auto size-4 text-accent" />
                          : <span className="text-faint">·</span>}
                      </td>
                    );
                  })}
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="flex gap-4 border-t border-border px-5 py-2.5 text-[11px] text-faint">
        <span className="flex items-center gap-1"><CheckCircle2 className="size-3 text-success" /> finished</span>
        <span className="flex items-center gap-1"><CircleDashed className="size-3 text-accent" /> started</span>
      </div>
    </Card>
  );
}
