// #/sandbox/library: labs teachers chose to share (no presets; plan §5.4).
// Search, a preview drawer, and "Use this lab" into one of my subjects.
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { Library as LibraryIcon, Search, X } from "lucide-react";
import { Badge, Button, Card, EmptyState, Input, Page, PageHeader, Spinner, cn } from "../ui";
import { get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { LessonText } from "../learn/LessonText";
import { go, href } from "../routes";
import { useLoad } from "./Subjects";
import { BASE_ICON, NetworkBadge } from "./bits";
import type { LabDetail, LibraryEntry, SubjectRow } from "./api";

export function SandboxLibrary({ onAuthLost }: { onAuthLost: () => void }) {
  const [q, setQ] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [entries, setEntries] = useState<LibraryEntry[] | null>(null);
  const [subjects] = useLoad<SubjectRow[]>("/api/sandbox/subjects", onAuthLost);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      get<LibraryEntry[]>(`/api/sandbox/library?${new URLSearchParams({ q, difficulty })}`).then(setEntries, () => setEntries([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q, difficulty]);

  return (
    <Page>
      <PageHeader title="Library" description="Labs colleagues shared. Using one copies it into your subject as a draft you can change freely." />
      <div className="mb-5 flex flex-wrap gap-2">
        <label className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-3 size-4 text-faint" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title, subject or topic" className="pl-9" />
        </label>
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="h-11 rounded-lg border border-border px-3 text-sm text-text">
          <option value="">Any level</option><option value="intro">Intro</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option>
        </select>
      </div>

      {!entries && <div className="grid gap-3 sm:grid-cols-2">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}</div>}
      {entries && entries.length === 0 && (
        <EmptyState icon={LibraryIcon} title={q || difficulty ? "Nothing matches" : "Nothing shared yet"}>
          {q || difficulty ? "Try a different search or level." : "Share a lab from its Publish step and it appears here for colleagues."}
        </EmptyState>
      )}
      {entries && entries.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {entries.map((e) => {
            const Icon = e.base ? BASE_ICON[e.base] : LibraryIcon;
            return (
              <button key={e.id} onClick={() => setOpen(e.id)}
                className="grid gap-2 rounded-xl border border-border p-4 text-left shadow-sm transition-colors hover:border-border-strong">
                <span className="flex items-center gap-2 text-[15px] font-semibold text-text"><Icon className="size-4 text-accent" />{e.title}</span>
                <span className="line-clamp-2 text-sm text-muted">{e.summary || e.subject_title}</span>
                <span className="flex flex-wrap gap-1.5">
                  <Badge>{e.n_assignments} {e.n_assignments === 1 ? "assignment" : "assignments"}</Badge>
                  {e.difficulty && <Badge tone="accent">{e.difficulty}</Badge>}
                  {e.topics.map((t) => <Badge key={t}>{t}</Badge>)}
                  {e.uses > 0 && <Badge tone="success">used {e.uses}×</Badge>}
                </span>
                <span className="text-xs text-faint">{e.subject_title} · {e.shared_by ?? "admin"}</span>
              </button>
            );
          })}
        </div>
      )}
      {/* portal: the page wrapper is transformed by its enter animation, which would trap position: fixed */}
      {createPortal(<AnimatePresence>{open && <Drawer id={open} subjects={subjects ?? []} onClose={() => setOpen(null)} />}</AnimatePresence>, document.body)}
    </Page>
  );
}

function Drawer({ id, subjects, onClose }: { id: string; subjects: SubjectRow[]; onClose: () => void }) {
  const [e, setE] = useState<LibraryEntry | null>(null);
  const writable = subjects.filter((s) => s.access !== "ta");
  const [subject, setSubject] = useState(writable[0]?.id ?? "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { get<LibraryEntry>(`/api/sandbox/library/${id}`).then(setE, (err) => setMsg(err.message)); }, [id]);
  useEffect(() => { if (!subject && writable[0]) setSubject(writable[0].id); }, [writable, subject]);

  return (
    <>
      <motion.div className="fixed inset-0 z-40 bg-black/30" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
      <motion.aside initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", stiffness: 380, damping: 38 }}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-border bg-bg shadow-lg">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2 className="truncate text-base font-semibold text-text">{e?.title ?? "…"}</h2>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close"><X className="size-4" /></Button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {!e ? <Skeleton className="h-40" /> : (
            <div className="grid gap-4">
              <div className="flex flex-wrap gap-1.5">{e.lab && <NetworkBadge network={e.lab.network} />}{e.lab?.environment && <Badge>{e.lab.environment.title}</Badge>}</div>
              {e.lab?.description && <LessonText markdown={e.lab.description} language="" />}
              {e.lab?.assignments.map((a, i) => (
                <Card key={a.id} className="p-3">
                  <p className="text-sm font-medium text-text">{i + 1}. {a.title}</p>
                  <LessonText markdown={a.statement || "*No statement.*"} language="" className="mt-2" />
                  <p className="mt-2 font-mono text-[11px] text-faint">{a.files.map((f) => f.path).join("")} · {a.tests.kind === "command" ? a.tests.command : `${a.tests.cases?.length ?? 0} tests`}{a.solution_files?.length ? " · has a solution" : ""}</p>
                </Card>
              ))}
            </div>
          )}
        </div>
        <div className="grid gap-2 border-t border-border p-4">
          {msg && <p className="text-sm text-danger">{msg}</p>}
          {writable.length === 0 ? <p className="text-sm text-muted">Create a subject first, then use this lab in it.</p> : (
            <div className="flex gap-2">
              <select value={subject} onChange={(ev) => setSubject(ev.target.value)} className={cn("h-9 flex-1 rounded-lg border border-border px-2 text-sm text-text")}>
                {writable.map((s) => <option key={s.id} value={s.id}>{s.title}{s.code ? ` (${s.code})` : ""}</option>)}
              </select>
              <Button variant="primary" disabled={busy || !subject} onClick={async () => {
                setBusy(true);
                try { const lab = await send<LabDetail>("POST", `/api/sandbox/library/${id}/use`, { subject_id: subject }); go(href.sbxLab(lab.id)); }
                catch (err) { setMsg((err as Error).message); setBusy(false); }
              }}>{busy && <Spinner />} Use this lab</Button>
            </div>
          )}
        </div>
      </motion.aside>
    </>
  );
}
