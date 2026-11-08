// #/sandbox/labs/<id>: the lab wizard (plan §5.3). Basics, Assignments, Check
// (reference solution against the tests in a preview instance), Publish, and
// sharing to the library.
import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { ArrowDown, ArrowLeft, ArrowUp, Check, CircleAlert, Copy, Download, FilePlus2, FlaskConical, History, Info, Play, Plus, Rocket, Share2, Trash2, Undo2, X } from "lucide-react";
import { Badge, Button, Card, Checkbox, Field, Input, Spinner, TextArea, cn, item, spring, stagger } from "../ui";
import { get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { LessonText } from "../learn/LessonText";
import { go, href } from "../routes";
import { useLoad } from "./Subjects";
import { FileEditor, NetworkBadge } from "./bits";
import { SourcePicker } from "../teach/SourcePicker";
import type { Language } from "../teach/api";
import { GRADING, NETWORK, emptyTests, type Assignment, type CopyCandidate, type GradingMode, type LabChange, type LabDetail, type LatePolicy,
  type Network, type Preview, type SandboxFile, type TestCase, type Tests, type VerifyResult } from "./api";

const STEPS = ["Basics", "Assignments", "Check", "Publish", "History"] as const;
type Step = (typeof STEPS)[number];

export function SandboxLabEditor({ id, onAuthLost }: { id: string; onAuthLost: () => void }) {
  const [lab, error, , setLab] = useLoad<LabDetail>(`/api/sandbox/labs/${id}`, onAuthLost);
  const [step, setStep] = useState<Step>("Basics");
  const [msg, setMsg] = useState("");
  const [note, setNote] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const save = async (method: string, path: string, body?: unknown) => {
    setSaving(true);
    setMsg("");
    setNote([]);
    try {
      const got = await send<LabDetail>(method, path, body);
      setLab(got);
      setNote([...(got.effects ?? []), ...(got.notes ?? [])]);
      return true;
    }
    catch (e) { setMsg((e as Error).message); return false; }
    finally { setSaving(false); }
  };

  if (error) return <div className="mx-auto max-w-[1200px] px-5 pt-8"><Card className="p-6 text-sm text-danger">{error}</Card></div>;
  if (!lab) return <div className="mx-auto max-w-[1200px] px-5 pt-8"><Skeleton className="h-60 rounded-2xl" /></div>;
  const readOnly = lab.access === "ta";

  return (
    <motion.div variants={stagger(0.05)} initial="initial" animate="animate" className="mx-auto max-w-[1200px] px-5 pb-24 pt-6">
      <motion.a variants={item} href={href.sbxSubject(lab.subject_id)} className="mb-4 inline-flex items-center gap-1 text-[13px] text-muted hover:text-text">
        <ArrowLeft className="size-3.5" /> {lab.definition.subject.title}
      </motion.a>
      <motion.div variants={item} className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">{lab.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge tone={lab.status === "published" ? "success" : lab.status === "closed" ? "warn" : "neutral"}>{lab.status}</Badge>
            <NetworkBadge network={lab.network} />
            {lab.assessed && <Badge>assessed</Badge>}
            {lab.shared && <Badge tone="accent"><Share2 className="size-3" /> in library</Badge>}
            <span className="font-mono text-[11px] text-faint">v{lab.version}</span>
          </div>
        </div>
        <TryButton labId={lab.id} />
      </motion.div>
      {msg && <Card className="mb-4 flex items-start gap-2 p-4 text-sm text-danger"><CircleAlert className="mt-0.5 size-4 shrink-0" />{msg}</Card>}
      <AnimatePresence>
        {note.length > 0 && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}>
            <Card className="mb-4 flex items-start gap-2 border-accent/40 bg-accent-soft p-4 text-sm text-text" role="status">
              <Info className="mt-0.5 size-4 shrink-0 text-accent" />
              <ul className="grid flex-1 gap-0.5">{note.map((n) => <li key={n}>{n}</li>)}</ul>
              <button onClick={() => setNote([])} aria-label="Dismiss"><X className="size-4 text-muted" /></button>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid gap-6 md:grid-cols-[180px_1fr]">
        <LayoutGroup id="wizard">
          <nav className="flex gap-1 overflow-x-auto md:sticky md:top-20 md:grid md:content-start">
            {STEPS.filter((s) => s !== "History" || lab.status !== "draft" || lab.n_changes > 0).map((s, i) => (
              <button key={s} onClick={() => setStep(s)} className={cn("relative flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium",
                step === s ? "text-text" : "text-muted hover:text-text")}>
                {step === s && <motion.span layoutId="wizard-step" transition={spring} className="absolute inset-0 rounded-lg bg-surface-3" />}
                <span className={cn("relative grid size-5 place-items-center rounded-full border text-[11px]", step === s ? "border-accent bg-accent text-accent-fg" : "border-border")}>{i + 1}</span>
                <span className="relative">{s}</span>
                {s === "History" && lab.n_changes > 0 && <span className="relative ml-auto font-mono text-[11px] text-faint">{lab.n_changes}</span>}
              </button>
            ))}
          </nav>
        </LayoutGroup>
        <AnimatePresence mode="wait">
          <motion.div key={step} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.18 }}>
            {step === "Basics" && <Basics lab={lab} readOnly={readOnly} saving={saving} save={save} />}
            {step === "Assignments" && <Assignments lab={lab} readOnly={readOnly} save={save} onAuthLost={onAuthLost} />}
            {step === "Check" && <CheckStep lab={lab} />}
            {step === "Publish" && <Publish lab={lab} readOnly={readOnly} saving={saving} save={save} />}
            {step === "History" && <HistoryStep lab={lab} readOnly={readOnly} save={save} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

type Save = (method: string, path: string, body?: unknown) => Promise<boolean>;

function TryButton({ labId }: { labId: string }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  return (
    <div className="grid justify-items-end gap-1">
      <Button variant="primary" disabled={busy} onClick={async () => {
        setBusy(true); setMsg("");
        try { const p = await send<Preview>("POST", "/api/sandbox/previews", { lab_id: labId }); go(href.sbxPreview(p.id)); }
        catch (e) { setMsg((e as Error).message); setBusy(false); }
      }}>{busy ? <Spinner /> : <Play className="size-4" />} Try as a student</Button>
      {msg && <span className="max-w-xs text-right text-xs text-danger">{msg}</span>}
    </div>
  );
}

function Basics({ lab, readOnly, saving, save }: { lab: LabDetail; readOnly: boolean; saving: boolean; save: Save }) {
  const [title, setTitle] = useState(lab.title);
  const [description, setDescription] = useState(lab.description);
  return (
    <Card className="grid gap-4 p-5">
      <Field label="Title"><Input value={title} disabled={readOnly} onChange={(e) => setTitle(e.target.value)} /></Field>
      <div className="grid gap-3 lg:grid-cols-2">
        <Field label="Description for students" hint="Markdown"><TextArea rows={8} value={description} disabled={readOnly} onChange={(e) => setDescription(e.target.value)} /></Field>
        <div className="grid content-start gap-1.5"><span className="text-[13px] font-medium text-text">Preview</span>
          <div className="min-h-32 rounded-lg border border-border bg-surface-2 p-3"><LessonText markdown={description || "*Nothing yet.*"} language="" /></div></div>
      </div>
      <p className="text-xs text-muted">Environment: {lab.definition.environment?.title ?? "none"} (from the subject){lab.env_version ? `, pinned at v${lab.env_version}` : ""}.</p>
      {!readOnly && <Button variant="primary" className="justify-self-end" disabled={saving} onClick={() => save("PATCH", `/api/sandbox/labs/${lab.id}`, { title, description })}>Save</Button>}
    </Card>
  );
}

const BASE_LANGUAGE: Record<string, Language> = { "c-cpp": "c", python: "python", java: "java", "web-node": "javascript" };

function Assignments({ lab, readOnly, save, onAuthLost }: { lab: LabDetail; readOnly: boolean; save: Save; onAuthLost: () => void }) {
  const list = lab.definition.assignments;
  const [open, setOpen] = useState<string | null>(list[0]?.id ?? null);
  const [title, setTitle] = useState("");
  const [adding, setAdding] = useState<null | "import" | "copy">(null);
  const [language, setLanguage] = useState<Language>(BASE_LANGUAGE[lab.definition.environment?.recipe.base ?? ""] ?? "python");
  const added = (ok: boolean) => { if (ok) setAdding(null); return ok; };
  const move = (i: number, d: number) => {
    const ids = list.map((a) => a.id);
    [ids[i], ids[i + d]] = [ids[i + d], ids[i]];
    void save("PUT", `/api/sandbox/labs/${lab.id}/order`, { assignment_ids: ids });
  };
  return (
    <div className="grid gap-3">
      <LayoutGroup>
        {list.map((a, i) => (
          <motion.div key={a.id} layout transition={spring}>
            <Card className="overflow-hidden">
              <div className="flex items-center gap-2 p-3">
                <button className="flex flex-1 items-center gap-2 text-left" onClick={() => setOpen(open === a.id ? null : a.id)}>
                  <span className="grid size-6 place-items-center rounded-md bg-surface-2 font-mono text-xs text-muted">{i + 1}</span>
                  <span className="text-sm font-medium text-text">{a.title}</span>
                  <span className="text-xs text-muted">{a.files.length} files · {a.tests.kind === "command" ? "test command" : `${a.tests.cases.length} tests`}{a.solution_files.length ? " · solution" : ""}</span>
                </button>
                {!readOnly && <>
                  <Button size="icon" variant="ghost" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Move up"><ArrowUp className="size-3.5" /></Button>
                  <Button size="icon" variant="ghost" disabled={i === list.length - 1} onClick={() => move(i, 1)} aria-label="Move down"><ArrowDown className="size-3.5" /></Button>
                </>}
              </div>
              <AnimatePresence initial={false}>
                {open === a.id && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden border-t border-border">
                    <AssignmentForm key={a.id + lab.version} a={a} readOnly={readOnly} published={lab.status !== "draft"}
                      onSave={(body) => save("PATCH", `/api/sandbox/assignments/${a.id}`, body)}
                      onDelete={() => save("DELETE", `/api/sandbox/assignments/${a.id}`)} />
                  </motion.div>
                )}
              </AnimatePresence>
            </Card>
          </motion.div>
        ))}
      </LayoutGroup>
      {!readOnly && (
        <div className="grid gap-2">
          <form className="flex gap-2" onSubmit={async (e) => {
            e.preventDefault();
            if (await save("POST", `/api/sandbox/labs/${lab.id}/assignments`, { title, tests: emptyTests() })) setTitle("");
          }}>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New assignment, e.g. Insert at head" className="h-9" />
            <Button type="submit" disabled={!title.trim()}><Plus className="size-4" /> Write one</Button>
          </form>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span>or</span>
            <Button size="sm" variant={adding === "import" ? "primary" : "secondary"} onClick={() => setAdding(adding === "import" ? null : "import")}>
              <Download className="size-3.5" /> Import a question
            </Button>
            <Button size="sm" variant={adding === "copy" ? "primary" : "secondary"} onClick={() => setAdding(adding === "copy" ? null : "copy")}>
              <Copy className="size-3.5" /> Copy from another lab
            </Button>
          </div>
          <AnimatePresence>
            {adding === "import" && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <Card className="grid gap-3 p-4">
                  <label className="flex flex-wrap items-center gap-2 text-[13px] text-text">Students answer in
                    <select value={language} onChange={(e) => setLanguage(e.target.value as Language)} className="h-8 rounded-md border border-border bg-surface px-2">
                      <option value="c">C</option><option value="cpp">C++</option><option value="python">Python</option>
                      <option value="java">Java</option><option value="javascript">JavaScript</option>
                    </select>
                    <span className="text-xs text-muted">The statement, a starter file, a Run command and the tests come along; you can change any of it after.</span>
                  </label>
                  <SourcePicker language={language} onClose={() => setAdding(null)} onAuthLost={onAuthLost}
                    onImport={async (provider, ref) => added(await save("POST", `/api/sandbox/labs/${lab.id}/import`, { provider, ref, language }))} />
                </Card>
              </motion.div>
            )}
            {adding === "copy" && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <CopyPicker labId={lab.id} onPick={async (assignment_id) => added(await save("POST", `/api/sandbox/labs/${lab.id}/assignments/copy`, { assignment_id }))} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

function CopyPicker({ labId, onPick }: { labId: string; onPick: (assignmentId: string) => Promise<boolean> }) {
  const [labs, setLabs] = useState<CopyCandidate[] | null>(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");
  useEffect(() => { get<CopyCandidate[]>("/api/sandbox/assignments").then(setLabs, () => setLabs([])); }, []);
  const shown = (labs ?? []).filter((l) => l.lab_id !== labId).map((l) => ({
    ...l, assignments: l.assignments.filter((a) => !q || `${a.title} ${l.lab_title} ${l.subject_title}`.toLowerCase().includes(q.toLowerCase())),
  })).filter((l) => l.assignments.length);
  return (
    <Card className="grid gap-3 p-4">
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your labs" className="h-9" />
      {labs === null ? <Skeleton className="h-20" /> : shown.length === 0 ? (
        <p className="text-sm text-muted">No other labs with assignments yet. The library has labs your colleagues shared.</p>
      ) : (
        <div className="grid max-h-80 gap-3 overflow-y-auto">
          {shown.map((l) => (
            <div key={l.lab_id}>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-faint">{l.subject_title} · {l.lab_title}</p>
              <div className="mt-1 grid gap-1">
                {l.assignments.map((a) => (
                  <button key={a.id} disabled={!!busy} onClick={async () => { setBusy(a.id); await onPick(a.id); setBusy(""); }}
                    className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-left text-sm text-text hover:border-accent hover:bg-accent-soft">
                    <span className="flex-1">{a.title}</span>
                    {busy === a.id ? <Spinner /> : <Plus className="size-3.5 text-accent" />}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="text-xs text-muted">The copy is independent: changing it later doesn't touch the original.</p>
    </Card>
  );
}

function AssignmentForm({ a, readOnly, published, onSave, onDelete }: {
  a: Assignment; readOnly: boolean; published: boolean; onSave: (b: unknown) => Promise<boolean>; onDelete: () => void;
}) {
  const [f, setF] = useState(() => ({ title: a.title, statement: a.statement, files: a.files, open: a.open, run: a.run, tests: a.tests, solution_files: a.solution_files }));
  const [tab, setTab] = useState<"statement" | "files" | "tests" | "solution">("statement");
  const dirty = useMemo(() => JSON.stringify(f) !== JSON.stringify({ title: a.title, statement: a.statement, files: a.files, open: a.open, run: a.run, tests: a.tests, solution_files: a.solution_files }), [f, a]);
  return (
    <div className="grid gap-4 p-4">
      <div className="grid gap-3 sm:grid-cols-[1fr_1fr]">
        <Field label="Title"><Input value={f.title} disabled={readOnly} onChange={(e) => setF({ ...f, title: e.target.value })} className="h-9" /></Field>
        <Field label="Run command" hint="What the Run button does, in the assignment folder"><Input value={f.run} disabled={readOnly} onChange={(e) => setF({ ...f, run: e.target.value })} placeholder="make -s && ./main" className="h-9 font-mono text-xs" /></Field>
      </div>
      <div className="flex gap-1 border-b border-border">
        {(["statement", "files", "tests", "solution"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={cn("relative px-3 pb-2 text-[13px] font-medium capitalize", tab === t ? "text-text" : "text-muted")}>
            {t === "files" ? "Starter files" : t === "solution" ? "Reference solution" : t}
            {tab === t && <motion.span layoutId={`tab-${a.id}`} className="absolute inset-x-0 -bottom-px h-0.5 bg-accent" />}
          </button>
        ))}
      </div>
      {tab === "statement" && (
        <div className="grid gap-3 lg:grid-cols-2">
          <TextArea rows={12} value={f.statement} disabled={readOnly} onChange={(e) => setF({ ...f, statement: e.target.value })} placeholder="What students should do (Markdown)" />
          <div className="max-h-80 overflow-y-auto rounded-lg border border-border bg-surface-2 p-3"><LessonText markdown={f.statement || "*Nothing yet.*"} language="" /></div>
        </div>
      )}
      {tab === "files" && <FilesEditor files={f.files} open={f.open} readOnly={readOnly} onChange={(files, open) => setF({ ...f, files, open })} />}
      {tab === "solution" && (
        <div className="grid gap-2">
          <p className="text-xs text-muted">Private: never sent to students. Laid over the starter files when the Check step runs the tests; all must pass.</p>
          <FilesEditor files={f.solution_files} readOnly={readOnly} onChange={(solution_files) => setF({ ...f, solution_files })} />
        </div>
      )}
      {tab === "tests" && <TestsEditor tests={f.tests} readOnly={readOnly} onChange={(tests) => setF({ ...f, tests })} />}
      {!readOnly && (
        <div className="flex items-center justify-between gap-2">
          {!published ? <Button variant="ghost" size="sm" onClick={() => confirm(`Remove ${a.title}?`) && onDelete()}><Trash2 className="size-3.5" /> Remove</Button>
            : <span className="text-xs text-muted">Students have this lab: fixes apply at once, test changes regrade their work, and every change can be undone from History.</span>}
          <Button variant="primary" size="sm" disabled={!dirty} onClick={() => onSave(f)}><Check className="size-3.5" /> Save assignment</Button>
        </div>
      )}
    </div>
  );
}

function FilesEditor({ files, open, readOnly, onChange }: {
  files: SandboxFile[]; open?: string[]; readOnly: boolean; onChange: (files: SandboxFile[], open: string[]) => void;
}) {
  const [cur, setCur] = useState(files[0]?.path ?? "");
  const upload = useRef<HTMLInputElement>(null);
  const file = files.find((x) => x.path === cur);
  const opened = open ?? [];
  const add = (path: string, content = "") => {
    if (!path || files.some((x) => x.path === path)) return;
    onChange([...files, { path, content }], opened.length ? opened : [path]);
    setCur(path);
  };
  return (
    <div className="grid min-h-72 overflow-hidden rounded-lg border border-border sm:grid-cols-[180px_1fr]">
      <div className="grid content-start gap-0.5 border-b border-border bg-surface-2 p-2 sm:border-b-0 sm:border-r">
        {files.map((x) => (
          <div key={x.path} className={cn("group flex items-center gap-1 rounded-md px-2 py-1 font-mono text-xs", cur === x.path ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text")}>
            <button className="flex-1 truncate text-left" onClick={() => setCur(x.path)}>{x.path}</button>
            {open && !readOnly && <input type="checkbox" title="Open first in the editor" checked={opened.includes(x.path)} className="size-3"
              onChange={() => onChange(files, opened.includes(x.path) ? opened.filter((p) => p !== x.path) : [...opened, x.path])} />}
            {!readOnly && <button className="opacity-0 group-hover:opacity-100" aria-label={`Remove ${x.path}`} onClick={() => { onChange(files.filter((y) => y.path !== x.path), opened.filter((p) => p !== x.path)); setCur(files[0]?.path ?? ""); }}><X className="size-3" /></button>}
          </div>
        ))}
        {!readOnly && <>
          <button className="mt-1 flex items-center gap-1 rounded-md px-2 py-1 text-xs text-accent hover:bg-surface" onClick={() => add((prompt("File path, e.g. main.c or src/app.py") ?? "").trim())}><FilePlus2 className="size-3.5" /> New file</button>
          <button className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-accent hover:bg-surface" onClick={() => upload.current?.click()}><Plus className="size-3.5" /> Upload files</button>
          <input ref={upload} type="file" multiple hidden onChange={async (e) => {
            const got = await Promise.all([...(e.target.files ?? [])].map(async (fl) => ({ path: fl.name, content: await fl.text() })));
            const merged = [...files.filter((x) => !got.some((g) => g.path === x.path)), ...got];
            onChange(merged, opened.length ? opened : got.slice(0, 1).map((g) => g.path));
            if (got[0]) setCur(got[0].path);
            e.target.value = "";
          }} />
        </>}
      </div>
      <div className="h-80 min-w-0">
        {file ? <FileEditor key={file.path} path={file.path} value={file.content} readOnly={readOnly}
          onChange={(content) => onChange(files.map((x) => (x.path === file.path ? { ...x, content } : x)), opened)} />
          : <p className="p-6 text-sm text-muted">No files yet.</p>}
      </div>
    </div>
  );
}

function TestsEditor({ tests, readOnly, onChange }: { tests: Tests; readOnly: boolean; onChange: (t: Tests) => void }) {
  const set = (i: number, c: Partial<TestCase>) => onChange({ ...tests, cases: tests.cases.map((x, j) => (j === i ? { ...x, ...c } : x)) });
  const blank = (): TestCase => ({ name: "", stdin: "", expected: "", hidden: false, compare: "text" });
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-3 text-[13px]">
        {(["io", "command"] as const).map((k) => (
          <label key={k} className="flex items-center gap-1.5">
            <input type="radio" disabled={readOnly} checked={tests.kind === k} onChange={() => onChange({ ...tests, kind: k })} />
            {k === "io" ? "Input/output pairs (fed to the Run command)" : "A test command (exit code 0 passes)"}
          </label>
        ))}
        <label className="ml-auto flex items-center gap-1.5 text-muted">Time limit
          <Input type="number" min={1} max={300} value={tests.timeout_s} disabled={readOnly} onChange={(e) => onChange({ ...tests, timeout_s: Number(e.target.value) || 10 })} className="h-8 w-16" /> s
        </label>
      </div>
      {tests.kind === "command" ? (
        <Input value={tests.command} disabled={readOnly} onChange={(e) => onChange({ ...tests, command: e.target.value })} placeholder="make test   or   pytest -q" className="h-9 font-mono text-xs" />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="bg-surface-2 text-left text-muted"><tr><th className="p-2">Name</th><th className="p-2">Input</th><th className="p-2">Expected output</th><th className="p-2">Compare</th><th className="p-2">Hidden</th><th /></tr></thead>
            <tbody>
              {tests.cases.map((c, i) => (
                <tr key={i} className="border-t border-border align-top">
                  <td className="p-1"><Input value={c.name} disabled={readOnly} onChange={(e) => set(i, { name: e.target.value })} className="h-8 text-xs" /></td>
                  <td className="p-1"><TextArea rows={2} value={c.stdin} disabled={readOnly} onChange={(e) => set(i, { stdin: e.target.value })} className="font-mono text-xs" /></td>
                  <td className="p-1"><TextArea rows={2} value={c.expected} disabled={readOnly} onChange={(e) => set(i, { expected: e.target.value })}
                    onKeyDown={(e) => { if (e.key === "Tab" && !e.shiftKey && i === tests.cases.length - 1 && !readOnly) onChange({ ...tests, cases: [...tests.cases, blank()] }); }}
                    className="font-mono text-xs" /></td>
                  <td className="p-1"><select value={c.compare} disabled={readOnly} onChange={(e) => set(i, { compare: e.target.value as TestCase["compare"] })} className="h-8 rounded-md border border-border bg-surface px-1">
                    <option value="text">text</option><option value="tokens">tokens</option><option value="json">json</option></select></td>
                  <td className="p-2 text-center"><Checkbox checked={c.hidden} disabled={readOnly} onChange={() => set(i, { hidden: !c.hidden })} /></td>
                  <td className="p-1">{!readOnly && <Button size="icon" variant="ghost" onClick={() => onChange({ ...tests, cases: tests.cases.filter((_, j) => j !== i) })} aria-label="Remove test"><X className="size-3.5" /></Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!readOnly && <button className="w-full border-t border-border p-2 text-xs text-accent hover:bg-surface-2" onClick={() => onChange({ ...tests, cases: [...tests.cases, blank()] })}><Plus className="mr-1 inline size-3" />Add test</button>}
        </div>
      )}
      <p className="text-xs text-muted">Hidden tests never leave the server; students see only how many there are. "text" ignores trailing spaces and newlines, "tokens" compares words and numbers.</p>
    </div>
  );
}

function CheckStep({ lab }: { lab: LabDetail }) {
  const [state, setState] = useState<"idle" | "starting" | "running" | "done">("idle");
  const [res, setRes] = useState<VerifyResult | null>(null);
  const [msg, setMsg] = useState("");
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);

  const run = async () => {
    setMsg(""); setRes(null); setState("starting");
    try {
      let p = await send<Preview>("POST", "/api/sandbox/previews", { lab_id: lab.id });
      while (p.status === "starting" && alive.current) { await new Promise((r) => setTimeout(r, 1500)); p = await get<Preview>(`/api/sandbox/previews/${p.id}`); }
      if (p.status !== "running") throw new Error(p.error || "the preview did not start");
      setState("running");
      setRes(await send<VerifyResult>("POST", `/api/sandbox/previews/${p.id}/verify`));
      await send("POST", `/api/sandbox/previews/${p.id}/stop`);
      setState("done");
    } catch (e) { setMsg((e as Error).message); setState("idle"); }
  };

  return (
    <div className="grid gap-4">
      <Card className="p-5">
        <h2 className="text-sm font-semibold text-text">Problems that stop publishing</h2>
        {lab.problems.length === 0 ? <p className="mt-2 flex items-center gap-1.5 text-sm text-success"><Check className="size-4" /> None.</p>
          : <ul className="mt-2 grid gap-1 text-sm text-danger">{lab.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
      </Card>
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-text">Run the tests in the lab's environment</h2>
            <p className="mt-1 text-xs text-muted">Starts a short cloud preview: your reference solution must pass every test, the starter files should fail.</p>
          </div>
          <Button variant="primary" onClick={run} disabled={state === "starting" || state === "running"}>
            {state === "starting" || state === "running" ? <Spinner /> : <FlaskConical className="size-4" />}
            {state === "starting" ? "Starting the instance…" : state === "running" ? "Running tests…" : "Check lab"}
          </Button>
        </div>
        {msg && <p className="mt-3 text-sm text-danger">{msg}</p>}
        {res && (
          <motion.ul variants={stagger(0.08)} initial="initial" animate="animate" className="mt-4 grid gap-2">
            {res.assignments.map((a) => (
              <motion.li key={a.assignment_id} variants={item} className="rounded-xl border border-border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex-1 text-sm font-medium text-text">{a.title}</span>
                  {a.solution && <Badge tone={a.solution.passed === a.solution.total ? "success" : "danger"}>solution {a.solution.passed}/{a.solution.total}</Badge>}
                  {a.starter && <Badge tone={a.starter.passed < a.starter.total ? "success" : "warn"}>starter {a.starter.passed}/{a.starter.total}</Badge>}
                </div>
                {a.problems.length > 0 && <ul className="mt-2 grid gap-0.5 text-xs text-warn">{a.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
              </motion.li>
            ))}
          </motion.ul>
        )}
      </Card>
    </div>
  );
}

function Publish({ lab, readOnly, saving, save }: { lab: LabDetail; readOnly: boolean; saving: boolean; save: Save }) {
  const [network, setNetwork] = useState<Network>(lab.network);
  const [assessed, setAssessed] = useState(lab.assessed);
  const [sections, setSections] = useState(lab.sections.join(", "));
  const [due, setDue] = useState(lab.due_at ? toLocal(lab.due_at) : "");
  const [opens, setOpens] = useState(lab.opens_at ? toLocal(lab.opens_at) : "");
  const [summary, setSummary] = useState("");
  const [topics, setTopics] = useState("");
  const [shareMsg, setShareMsg] = useState("");
  const [grading, setGrading] = useState<GradingMode>(lab.grading_mode);
  const [late, setLate] = useState<LatePolicy>(lab.late);
  const body = { network, assessed, sections: sections.split(/[\s,]+/).filter(Boolean), due_at: due ? fromLocal(due) : null,
                 opens_at: opens ? fromLocal(opens) : null, grading_mode: grading, late };

  return (
    <div className="grid gap-4">
      <Card className="grid gap-4 p-5">
        <label className="flex items-center gap-2 text-sm text-text"><Checkbox checked={assessed} disabled={readOnly} onChange={() => { setAssessed(!assessed); if (!assessed && network === "open") setNetwork("registries"); }} /> Assessed lab</label>
        <div className="grid gap-2">
          <span className="text-[13px] font-medium text-text">Network</span>
          {(Object.keys(NETWORK) as Network[]).map((n) => (
            <label key={n} className={cn("flex cursor-pointer items-start gap-2 rounded-lg border p-3", network === n ? "border-accent bg-accent-soft" : "border-border",
              n === "open" && assessed && "cursor-not-allowed opacity-50")}>
              <input type="radio" disabled={readOnly || (n === "open" && assessed)} checked={network === n} onChange={() => setNetwork(n)} className="mt-1" />
              <span><span className="block text-sm font-medium text-text">{NETWORK[n].label}</span><span className="text-xs text-muted">{NETWORK[n].hint}</span></span>
            </label>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Sections" hint="Empty = every student of the subject"><Input value={sections} disabled={readOnly} onChange={(e) => setSections(e.target.value)} placeholder="A, B" className="h-9" /></Field>
          <Field label="Opens"><Input type="datetime-local" value={opens} disabled={readOnly} onChange={(e) => setOpens(e.target.value)} className="h-9" /></Field>
          <Field label="Due"><Input type="datetime-local" value={due} disabled={readOnly} onChange={(e) => setDue(e.target.value)} className="h-9" /></Field>
        </div>
        <div className="grid gap-2">
          <span className="text-[13px] font-medium text-text">Grading</span>
          <div className="grid gap-2 sm:grid-cols-3">
            {(Object.keys(GRADING) as GradingMode[]).map((g) => (
              <label key={g} className={cn("flex cursor-pointer items-start gap-2 rounded-lg border p-3", grading === g ? "border-accent bg-accent-soft" : "border-border")}>
                <input type="radio" disabled={readOnly} checked={grading === g} onChange={() => setGrading(g)} className="mt-1" />
                <span><span className="block text-sm font-medium text-text">{GRADING[g].label}</span><span className="text-xs text-muted">{GRADING[g].hint}</span></span>
              </label>
            ))}
          </div>
        </div>
        <LateEditor late={late} onChange={setLate} readOnly={readOnly} hasDue={!!due} />
        <Summary lab={lab} network={network} sections={body.sections} opens={body.opens_at} due={body.due_at} grading={grading} late={late} />
        {!readOnly && (
          <div className="flex flex-wrap justify-end gap-2">
            <Button disabled={saving} onClick={() => save("PATCH", `/api/sandbox/labs/${lab.id}`, body)}>Save settings</Button>
            {lab.status === "published" ? (
              <Button disabled={saving} onClick={() => save("PATCH", `/api/sandbox/labs/${lab.id}`, { status: "closed" })}>Close lab</Button>
            ) : (
              <Button variant="primary" disabled={saving || lab.problems.length > 0} onClick={() => save("PATCH", `/api/sandbox/labs/${lab.id}`, { ...body, status: "published" })}>
                <Rocket className="size-4" /> Publish to students
              </Button>
            )}
          </div>
        )}
        <p className="text-xs text-muted">Students see published labs in the desktop app; the lab keeps environment v{lab.env_version ?? lab.definition.environment?.version ?? "?"} from the moment it is published.</p>
      </Card>

      <Card className="grid gap-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text"><Share2 className="size-4 text-accent" /> Share to the library</h2>
        <p className="text-xs text-muted">Colleagues can copy it into their own subjects (statements, starter files and tests; solutions only to teachers). Their copies stay independent; sharing again tells them an update is available.</p>
        {!readOnly && <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Summary"><Input value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Pointers and malloc, 3 parts" className="h-9" /></Field>
            <Field label="Topics"><Input value={topics} onChange={(e) => setTopics(e.target.value)} placeholder="pointers, linked lists" className="h-9" /></Field>
          </div>
          {shareMsg && <p className="text-xs text-muted">{shareMsg}</p>}
          <div className="flex justify-end gap-2">
            {lab.shared && <Button onClick={async () => { await send("DELETE", `/api/sandbox/labs/${lab.id}/share`); setShareMsg("Withdrawn from the library."); }}>Withdraw</Button>}
            <Button variant="primary" onClick={async () => {
              try { const e = await send<{ version: number }>("POST", `/api/sandbox/labs/${lab.id}/share`, { summary, topics: topics.split(",").map((t) => t.trim()).filter(Boolean) }); setShareMsg(`Shared (library version ${e.version}).`); }
              catch (e) { setShareMsg((e as Error).message); }
            }}>{lab.shared ? "Share the latest version" : "Share"}</Button>
          </div>
        </>}
      </Card>
    </div>
  );
}

function LateEditor({ late, onChange, readOnly, hasDue }: { late: LatePolicy; onChange: (l: LatePolicy) => void; readOnly: boolean; hasDue: boolean }) {
  const opts: [LatePolicy["mode"], string, string][] = [
    ["closed", "Not accepted", "Submit stops at the due time."],
    ["accept", "Accepted, marked late", "No penalty; you see who was late."],
    ["penalty", "Accepted with a penalty", "A share of the score is taken off per day."],
  ];
  return (
    <div className={cn("grid gap-2", !hasDue && "opacity-60")}>
      <span className="text-[13px] font-medium text-text">Late work {!hasDue && <span className="font-normal text-muted">(set a due time first)</span>}</span>
      <div className="grid gap-2 sm:grid-cols-3">
        {opts.map(([m, label, hint]) => (
          <label key={m} className={cn("flex cursor-pointer items-start gap-2 rounded-lg border p-3", late.mode === m ? "border-accent bg-accent-soft" : "border-border")}>
            <input type="radio" disabled={readOnly} checked={late.mode === m} onChange={() => onChange({ ...late, mode: m })} className="mt-1" />
            <span><span className="block text-sm font-medium text-text">{label}</span><span className="text-xs text-muted">{hint}</span></span>
          </label>
        ))}
      </div>
      <AnimatePresence initial={false}>
        {late.mode === "penalty" && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className="flex flex-wrap items-center gap-2 overflow-hidden text-[13px] text-text">
            Take off
            <Input type="number" min={1} max={100} value={late.per_day_pct} disabled={readOnly} className="h-8" style={{ width: "4.5rem" }}
              onChange={(e) => onChange({ ...late, per_day_pct: Math.min(100, Math.max(1, Number(e.target.value) || 10)) })} />
            % per day, and stop accepting after
            <Input type="number" min={0} max={60} value={late.max_days} disabled={readOnly} className="h-8" style={{ width: "4.5rem" }}
              onChange={(e) => onChange({ ...late, max_days: Math.min(60, Math.max(0, Number(e.target.value) || 0)) })} />
            days <span className="text-xs text-muted">(0 = never)</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const lateWords = (l: LatePolicy) => l.mode === "closed" ? "Submissions close at the due time."
  : l.mode === "accept" ? "Late work is accepted and marked late."
  : `Late work loses ${l.per_day_pct}% per day${l.max_days ? `, not accepted after ${l.max_days} day${l.max_days === 1 ? "" : "s"}` : ""}.`;

/** What students will see, in one card, before the final button (plan §5.3 step 4). */
function Summary({ lab, network, sections, opens, due, grading, late }: {
  lab: LabDetail; network: Network; sections: string[]; opens: number | null; due: number | null; grading: GradingMode; late: LatePolicy;
}) {
  const n = lab.definition.assignments.length;
  const hidden = lab.definition.assignments.reduce((s, a) => s + (a.tests.cases?.filter((c) => c.hidden).length ?? 0), 0);
  const when = (t: number) => new Date(t * 1000).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const rows: [string, string][] = [
    ["Who", sections.length ? `Sections ${sections.join(", ")}` : "Every student of the subject"],
    ["When", `${opens ? `Opens ${when(opens)}` : "Opens as soon as you publish"}${due ? `, due ${when(due)}` : ", no due time"}`],
    ["Work", `${n} assignment${n === 1 ? "" : "s"}${hidden ? `, ${hidden} hidden test${hidden === 1 ? "" : "s"}` : ""}, in the desktop app`],
    ["Network", NETWORK[network].label],
    ["Grading", GRADING[grading].label],
    ...(due ? [["Late", lateWords(late)] as [string, string]] : []),
  ];
  return (
    <div className="rounded-xl border border-border bg-surface-2 p-4">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-faint">What students will see</p>
      <dl className="grid gap-1.5 text-[13px] sm:grid-cols-[90px_1fr]">
        {rows.map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{k}</dt><dd className="text-text">{v}</dd></div>)}
      </dl>
    </div>
  );
}

function HistoryStep({ lab, readOnly, save }: { lab: LabDetail; readOnly: boolean; save: Save }) {
  const [rows, setRows] = useState<LabChange[] | null>(null);
  useEffect(() => { get<LabChange[]>(`/api/sandbox/labs/${lab.id}/history`).then(setRows, () => setRows([])); }, [lab.id, lab.version]);
  const ago = (t: number) => new Date(t * 1000).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  return (
    <Card className="p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text"><History className="size-4 text-accent" /> Changes since students got this lab</h2>
      <p className="mt-1 text-xs text-muted">Fixing a typo or a wrong test mid-lab is safe: statement and test fixes reach students at once, test changes regrade every
        submission, and new starter files go only to students who haven't opened that assignment. Undo puts back exactly what a change replaced.</p>
      {rows === null ? <Skeleton className="mt-4 h-24" /> : rows.length === 0 ? <p className="mt-4 text-sm text-muted">No changes yet.</p> : (
        <motion.ol variants={stagger(0.04)} initial="initial" animate="animate" className="mt-4 grid gap-0">
          {rows.map((c) => (
            <motion.li key={c.id} variants={item} className="relative grid grid-cols-[18px_1fr_auto] items-start gap-3 pb-4 last:pb-0">
              <span className="relative mt-1.5 grid place-items-center"><span className="size-2.5 rounded-full bg-accent" /></span>
              <div className="min-w-0">
                <p className="text-sm text-text">{c.summary}</p>
                <p className="text-xs text-muted">{ago(c.at)}{c.by ? ` · ${c.by}` : ""} · v{c.lab_version}
                  {c.regraded !== null && <span className="ml-1 text-accent">· {c.regraded} submission{c.regraded === 1 ? "" : "s"} regraded</span>}</p>
              </div>
              {!readOnly && c.can_undo && c.fields.some((f) => f !== "status") && (
                <Button size="sm" variant="ghost" onClick={() => confirm(`Undo "${c.summary}"?`) && save("POST", `/api/sandbox/labs/${lab.id}/history/${c.id}/undo`)}>
                  <Undo2 className="size-3.5" /> Undo
                </Button>
              )}
            </motion.li>
          ))}
        </motion.ol>
      )}
    </Card>
  );
}

const toLocal = (t: number) => { const d = new Date(t * 1000); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };
const fromLocal = (s: string) => new Date(s).getTime() / 1000;
