// #/sandbox: my Sandbox Labs subjects, and #/sandbox/subjects/<id>: one subject
// with its labs, environment, people and roster (plan §5.1, §6.3).
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, Boxes, ChevronRight, Copy, FileCode2, Library, Plus, Share2, Terminal, Trash2, Users, X } from "lucide-react";
import { Badge, Button, Card, Field, Input, Spinner, TextArea, cn, item, pop, stagger } from "../ui";
import { AuthError, get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { go, href } from "../routes";
import { EnvironmentPicker, RecipeEditor, useCatalogue, type EnvChoice } from "./EnvironmentBuilder";
import { BASE_ICON, BuildBadge, NetworkBadge, mb } from "./bits";
import { COLOR_VAR, emptyRecipe, tint, type Environment, type Preview, type Recipe, type SubjectDetail, type SubjectRow } from "./api";

const LAB_TONE = { draft: "neutral", published: "success", closed: "warn" } as const;

function useLoad<T>(path: string | null, onAuthLost: () => void): [T | null, string, () => void, (t: T) => void] {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!path) return;
    get<T>(path).then(setData, (e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)));
  }, [path, n, onAuthLost]);
  return [data, error, useCallback(() => setN((x) => x + 1), []), setData];
}
export { useLoad };

export function SandboxHome({ onAuthLost }: { onAuthLost: () => void }) {
  const [subjects, error] = useLoad<SubjectRow[]>("/api/sandbox/subjects", onAuthLost);
  const [creating, setCreating] = useState(false);

  return (
    <motion.div variants={stagger(0.06)} initial="initial" animate="animate" className="mx-auto max-w-[1100px] px-5 pb-20 pt-8">
      <motion.div variants={item} className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Sandbox Labs</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Labs with a whole Linux machine, a terminal and an editor. Students open them in the desktop app on their own computer;
            you can try any lab here in a short cloud preview.
          </p>
        </div>
        <div className="flex gap-2">
          <a href={href.sbxLibrary} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-surface px-3 text-sm font-medium text-text shadow-sm hover:bg-surface-2">
            <Library className="size-4" /> Library
          </a>
          <Button variant="primary" onClick={() => setCreating(true)} disabled={creating}><Plus className="size-4" /> New subject</Button>
        </div>
      </motion.div>

      <AnimatePresence>{creating && <NewSubject onClose={() => setCreating(false)} />}</AnimatePresence>
      {error && <Card className="mb-4 p-6 text-sm text-danger">{error}</Card>}
      {!subjects && <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-40 rounded-2xl" />)}</div>}

      {subjects && subjects.length === 0 && !creating && (
        <Card variants={item} className="px-6 py-12 text-center">
          <span className="mx-auto grid size-11 place-items-center rounded-xl bg-accent-soft text-accent"><Boxes className="size-5" /></span>
          <h2 className="mt-3 text-base font-semibold text-text">No subjects yet</h2>
          <p className="mx-auto mt-1 max-w-md text-sm text-muted">A subject is the home for a course's labs: its Linux environment, its students and its labs.</p>
          <div className="mx-auto mt-6 grid max-w-2xl gap-3 sm:grid-cols-2">
            <EmptyChoice icon={Plus} title="Start blank" text="Name the subject and pick its tools." onClick={() => setCreating(true)} />
            <EmptyChoice icon={Library} title="Start from the library" text="Use a lab a colleague shared." onClick={() => go(href.sbxLibrary)} />
          </div>
        </Card>
      )}

      {subjects && subjects.length > 0 && (
        <motion.div variants={stagger(0.05)} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {subjects.map((s) => <SubjectCard key={s.id} s={s} />)}
        </motion.div>
      )}
    </motion.div>
  );
}

function EmptyChoice({ icon: Icon, title, text, onClick }: { icon: typeof Plus; title: string; text: string; onClick: () => void }) {
  return (
    <motion.button whileHover={{ y: -3 }} onClick={onClick} className="grid gap-1 rounded-xl border border-border bg-surface p-4 text-left shadow-sm hover:border-border-strong">
      <Icon className="size-4 text-accent" />
      <span className="text-sm font-medium text-text">{title}</span>
      <span className="text-xs text-muted">{text}</span>
    </motion.button>
  );
}

function SubjectCard({ s }: { s: SubjectRow }) {
  const Icon = s.environment ? BASE_ICON[s.environment.base] ?? Boxes : Boxes;
  return (
    <motion.a variants={item} whileHover={{ y: -3 }} href={href.sbxSubject(s.id)}
      className="group relative grid gap-3 overflow-hidden rounded-2xl border border-border bg-surface p-4 shadow-md hover:border-border-strong">
      <span className="absolute inset-x-0 top-0 h-1" style={{ backgroundColor: COLOR_VAR[s.color] }} />
      <div className="flex items-start gap-3">
        <span className="grid size-10 place-items-center rounded-xl" style={tint(s.color)}><Icon className="size-5" /></span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold text-text">{s.title}</p>
          <p className="text-xs text-muted">{[s.code, s.semester].filter(Boolean).join(" · ") || "No course code"}</p>
        </div>
        <ChevronRight className="size-4 text-faint transition-transform group-hover:translate-x-0.5" />
      </div>
      <div className="flex flex-wrap gap-1.5 text-xs">
        <Badge>{s.n_labs} {s.n_labs === 1 ? "lab" : "labs"}{s.n_published ? `, ${s.n_published} published` : ""}</Badge>
        <Badge><Users className="size-3" /> {s.n_students}</Badge>
        {s.environment && <BuildBadge status={s.environment.status} />}
        {s.access !== "owner" && <Badge tone="accent">{s.access === "ta" ? "TA" : s.access === "co_teacher" ? "co-teacher" : "admin"}</Badge>}
      </div>
    </motion.a>
  );
}

function NewSubject({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState("");
  const [code, setCode] = useState("");
  const [semester, setSemester] = useState(defaultSemester());
  const [env, setEnv] = useState<EnvChoice>({ kind: "new", recipe: emptyRecipe() });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const s = await send<SubjectDetail>("POST", "/api/sandbox/subjects", {
        title, code, semester, ...(env.kind === "new" ? { recipe: env.recipe } : { environment_id: env.environment_id }),
      });
      go(href.sbxSubject(s.id));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <Card variants={pop} initial="initial" animate="animate" exit="exit" className="mb-6 p-5">
      <form onSubmit={submit} className="grid gap-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-text">New subject</h2>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close"><X className="size-4" /></Button>
        </div>
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr]">
          <Field label="Name"><Input required autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Data Structures" /></Field>
          <Field label="Course code"><Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS201" /></Field>
          <Field label="Semester"><Input value={semester} onChange={(e) => setSemester(e.target.value)} /></Field>
        </div>
        <div>
          <p className="mb-1 text-[13px] font-medium text-text">Environment</p>
          <p className="mb-3 text-xs text-muted">The Linux toolbox every lab of this subject runs in. Students can install more on top; grading uses this one.</p>
          <EnvironmentPicker value={env} onChange={setEnv} />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" disabled={busy || !title.trim()}>{busy ? <Spinner /> : <Plus className="size-4" />} Create subject</Button>
        </div>
      </form>
    </Card>
  );
}

function defaultSemester() {
  const d = new Date();
  return `${d.getMonth() >= 6 ? "Autumn" : "Spring"} ${d.getFullYear()}`;
}

export function SandboxSubject({ id, onAuthLost }: { id: string; onAuthLost: () => void }) {
  const [s, error, reload, setS] = useLoad<SubjectDetail>(`/api/sandbox/subjects/${id}`, onAuthLost);
  const [newLab, setNewLab] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const canEdit = s && s.access !== "ta";

  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setMsg("");
    try { await fn(); } catch (e) { setMsg((e as Error).message); } finally { setBusy(false); }
  };

  if (error) return <div className="mx-auto max-w-[1100px] px-5 pt-8"><Card className="p-6 text-sm text-danger">{error}</Card></div>;
  if (!s) return <div className="mx-auto max-w-[1100px] px-5 pt-8"><Skeleton className="h-40 rounded-2xl" /></div>;

  return (
    <motion.div variants={stagger(0.05)} initial="initial" animate="animate" className="mx-auto max-w-[1100px] px-5 pb-20 pt-6">
      <motion.a variants={item} href={href.sandbox} className="mb-4 inline-flex items-center gap-1 text-[13px] text-muted hover:text-text"><ArrowLeft className="size-3.5" /> Subjects</motion.a>
      <motion.div variants={item} className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid size-12 place-items-center rounded-2xl" style={tint(s.color)}><Boxes className="size-6" /></span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-text">{s.title}</h1>
            <p className="text-sm text-muted">{[s.code, s.semester, s.owner_email].filter(Boolean).join(" · ")}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button disabled={busy} onClick={() => act(async () => {
            const sem = prompt("Copy this subject with all its labs (as drafts) for which semester?", "");
            if (sem === null) return;
            const c = await send<SubjectDetail>("POST", `/api/sandbox/subjects/${s.id}/copy`, { semester: sem });
            go(href.sbxSubject(c.id));
          })}><Copy className="size-4" /> Copy for next semester</Button>
        </div>
      </motion.div>
      {msg && <Card className="mb-4 p-4 text-sm text-danger">{msg}</Card>}

      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        <motion.section variants={item} className="grid content-start gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text">Labs</h2>
            <a href={href.sbxLibrary} className="text-[13px] text-accent hover:underline">From the library</a>
          </div>
          {canEdit && (
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void act(async () => {
              const lab = await send<{ id: string }>("POST", `/api/sandbox/subjects/${s.id}/labs`, { title: newLab });
              go(href.sbxLab(lab.id));
            }); }}>
              <Input value={newLab} onChange={(e) => setNewLab(e.target.value)} placeholder="New lab, e.g. Linked lists" className="h-9" />
              <Button type="submit" variant="primary" disabled={busy || !newLab.trim()}><Plus className="size-4" /> Add</Button>
            </form>
          )}
          {s.labs.length === 0 && <Card className="p-6 text-center text-sm text-muted">No labs yet. Start one above, or use one from the library.</Card>}
          {s.labs.map((l) => (
            <motion.a key={l.id} variants={item} whileHover={{ x: 2 }} href={href.sbxLab(l.id)}
              className="flex items-center gap-3 rounded-xl border border-border bg-surface p-3 shadow-sm hover:border-border-strong">
              <FileCode2 className="size-4 text-accent" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-text">{l.title}</span>
                <span className="text-xs text-muted">{l.n_assignments} {l.n_assignments === 1 ? "assignment" : "assignments"}{l.due_at ? ` · due ${new Date(l.due_at * 1000).toLocaleString()}` : ""}</span>
              </span>
              {l.shared && <Badge tone="accent"><Share2 className="size-3" /> in library</Badge>}
              {l.update_available && <Badge tone="warn">update in library</Badge>}
              <NetworkBadge network={l.network} />
              <Badge tone={LAB_TONE[l.status]}>{l.status}</Badge>
            </motion.a>
          ))}
        </motion.section>

        <div className="grid content-start gap-5">
          <EnvironmentPanel s={s} canEdit={!!canEdit} onChanged={reload} onAuthLost={onAuthLost} />
          <PeoplePanel s={s} onSaved={setS} />
          <RosterPanel s={s} canEdit={!!canEdit} onSaved={setS} />
          {s.access === "owner" || s.access === "admin" ? (
            s.labs.every((l) => l.status === "draft") && (
              <button className="flex items-center gap-1.5 justify-self-start text-[13px] text-danger hover:underline" onClick={() => act(async () => {
                if (!confirm(`Delete ${s.title} and its draft labs?`)) return;
                await send("DELETE", `/api/sandbox/subjects/${s.id}`);
                go(href.sandbox);
              })}><Trash2 className="size-3.5" /> Delete subject</button>
            )
          ) : null}
        </div>
      </div>
    </motion.div>
  );
}

function Panel({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <Card variants={item} className="p-4">
      <div className="mb-3 flex items-center justify-between gap-2"><h2 className="text-sm font-semibold text-text">{title}</h2>{action}</div>
      {children}
    </Card>
  );
}

function EnvironmentPanel({ s, canEdit, onChanged, onAuthLost }: { s: SubjectDetail; canEdit: boolean; onChanged: () => void; onAuthLost: () => void }) {
  const [env, , reload] = useLoad<Environment>(s.environment ? `/api/sandbox/environments/${s.environment.id}` : null, onAuthLost);
  const { bases, tools } = useCatalogue();
  const [editing, setEditing] = useState<Recipe | null>(null);
  const [dockerfile, setDockerfile] = useState("");
  const [msg, setMsg] = useState("");
  const latest = env?.versions[env.versions.length - 1];

  if (!s.environment) {
    return <Panel title="Environment"><p className="text-sm text-muted">No environment. Labs can't be published until the subject has one.</p></Panel>;
  }
  if (!env || !latest) return <Panel title="Environment"><Skeleton className="h-16" /></Panel>;
  const Icon = BASE_ICON[latest.recipe.base] ?? Boxes;

  return (
    <Panel title="Environment" action={<BuildBadge status={latest.status} />}>
      <div className="flex items-center gap-2 text-sm text-text"><Icon className="size-4 text-accent" /> {env.title} <span className="font-mono text-xs text-faint">v{latest.version}</span></div>
      <p className="mt-1 text-xs text-muted">{latest.recipe.dockerfile ? "Raw Dockerfile" : [bases.find((b) => b.id === latest.recipe.base)?.label, ...latest.recipe.tools].filter(Boolean).join(", ")} · about {mb(latest.size_mb)}</p>
      <p className="mt-1 truncate font-mono text-[11px] text-faint" title={latest.image}>{latest.image}</p>
      {latest.status === "failed" && latest.log && <pre className="mt-2 max-h-32 overflow-auto rounded-lg bg-console p-2 font-mono text-[11px] text-console-text">{latest.log}</pre>}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" onClick={async () => setDockerfile(dockerfile ? "" : (await get<{ dockerfile: string }>(`/api/sandbox/environments/${env.id}/versions/${latest.version}/dockerfile`)).dockerfile)}>
          {dockerfile ? "Hide" : "Show"} Dockerfile
        </Button>
        {canEdit && env.mine && <Button size="sm" onClick={() => setEditing(editing ? null : latest.recipe)}>{editing ? "Cancel" : "Change tools"}</Button>}
        {canEdit && env.mine && !latest.recipe.dockerfile && (
          <Button size="sm" title="Open a fresh instance, install things in its terminal, and save the commands as the next version" onClick={async () => {
            setMsg("");
            try { const p = await send<Preview>("POST", "/api/sandbox/previews", { environment_id: env.id }); go(href.sbxPreview(p.id)); }
            catch (e) { setMsg((e as Error).message); }
          }}><Terminal className="size-3.5" /> Set up by hand</Button>
        )}
        {env.mine && (
          <Button size="sm" variant="ghost" onClick={async () => { await send("PATCH", `/api/sandbox/environments/${env.id}`, { shared: !env.shared }); reload(); }}>
            <Share2 className="size-3.5" /> {env.shared ? "Shared with all teachers" : "Share with colleagues"}
          </Button>
        )}
      </div>
      {msg && !editing && <p className="mt-2 text-xs text-danger">{msg}</p>}
      {dockerfile && <pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-console p-3 font-mono text-[11px] leading-relaxed text-console-text">{dockerfile}</pre>}
      <AnimatePresence>
        {editing && (
          <motion.div variants={pop} initial="initial" animate="animate" exit="exit" className="mt-4 grid gap-3 border-t border-border pt-4">
            <RecipeEditor recipe={editing} onChange={setEditing} bases={bases} tools={tools} />
            <p className="text-xs text-muted">Saving builds a new version. Published labs keep the version they started with until you move them.</p>
            {msg && <p className="text-sm text-danger">{msg}</p>}
            <Button variant="primary" size="sm" className="justify-self-end" onClick={async () => {
              try {
                await send("POST", `/api/sandbox/environments/${env.id}/versions`, { recipe: editing });
                setEditing(null); reload(); onChanged();
              } catch (e) { setMsg((e as Error).message); }
            }}>Save as v{latest.version + 1}</Button>
          </motion.div>
        )}
      </AnimatePresence>
      {env.versions.length > 1 && (
        <details className="mt-3 text-xs text-muted">
          <summary className="cursor-pointer">{env.versions.length} versions</summary>
          <ul className="mt-2 grid gap-1">{[...env.versions].reverse().map((v) => (
            <li key={v.version} className="flex items-center justify-between gap-2"><span className="font-mono">v{v.version}</span><span className="truncate">{v.recipe.tools.join(", ")}</span><BuildBadge status={v.status} /></li>
          ))}</ul>
        </details>
      )}
    </Panel>
  );
}

const lines = (s: string) => s.split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean);

function PeoplePanel({ s, onSaved }: { s: SubjectDetail; onSaved: (s: SubjectDetail) => void }) {
  const owner = s.access === "owner" || s.access === "admin";
  const [co, setCo] = useState(s.co_teachers.join("\n"));
  const [tas, setTas] = useState(s.tas.join("\n"));
  const [msg, setMsg] = useState("");
  return (
    <Panel title="People">
      <p className="mb-2 text-xs text-muted">Owner: <span className="font-mono">{s.owner_email ?? "admins"}</span>. Co-teachers edit; TAs view and help.</p>
      {owner ? (
        <div className="grid gap-2">
          <Field label="Co-teachers"><TextArea rows={2} value={co} onChange={(e) => setCo(e.target.value)} placeholder="name@college" className="font-mono text-xs" /></Field>
          <Field label="TAs"><TextArea rows={2} value={tas} onChange={(e) => setTas(e.target.value)} className="font-mono text-xs" /></Field>
          {msg && <p className="text-xs text-danger">{msg}</p>}
          <Button size="sm" className="justify-self-end" onClick={async () => {
            try { onSaved(await send<SubjectDetail>("PUT", `/api/sandbox/subjects/${s.id}/people`, { co_teachers: lines(co), tas: lines(tas) })); setMsg(""); }
            catch (e) { setMsg((e as Error).message); }
          }}>Save people</Button>
        </div>
      ) : (
        <ul className="grid gap-1 font-mono text-xs text-muted">{[...s.co_teachers, ...s.tas.map((t) => `${t} (TA)`)].map((e) => <li key={e}>{e}</li>)}</ul>
      )}
    </Panel>
  );
}

function RosterPanel({ s, canEdit, onSaved }: { s: SubjectDetail; canEdit: boolean; onSaved: (s: SubjectDetail) => void }) {
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");
  const sections = [...new Set(s.roster.map((r) => r.section).filter(Boolean))];
  return (
    <Panel title={`Students (${s.roster.length})`}>
      {s.roster.length > 0 && (
        <div className="mb-3 flex max-h-28 flex-wrap gap-1 overflow-y-auto">
          {s.roster.map((r) => <span key={r.id} className="rounded-md bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-muted">{r.id}{r.section && <span className="text-faint"> {r.section}</span>}</span>)}
        </div>
      )}
      {sections.length > 0 && <p className="mb-2 text-xs text-muted">Sections: {sections.join(", ")}</p>}
      {canEdit && (
        <div className="grid gap-2">
          <TextArea rows={3} value={text} onChange={(e) => setText(e.target.value)} className="font-mono text-xs"
            placeholder={"UG24CS001 to UG24CS060\nA: UG24CS001 to UG24CS030\nB: ug24cs031@college …"} />
          <p className="text-xs text-muted">Roll numbers or addresses; ranges expand; a line starting "A:" puts its students in section A. Replaces the list.</p>
          {msg && <p className="text-xs text-danger">{msg}</p>}
          <Button size="sm" className={cn("justify-self-end")} disabled={!text.trim()} onClick={async () => {
            try { onSaved(await send<SubjectDetail>("PUT", `/api/sandbox/subjects/${s.id}/roster`, { text })); setText(""); setMsg(""); }
            catch (e) { setMsg((e as Error).message); }
          }}>Save roster</Button>
        </div>
      )}
    </Panel>
  );
}
