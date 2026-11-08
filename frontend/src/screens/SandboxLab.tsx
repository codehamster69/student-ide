// A Sandbox lab in the desktop app: the student's Linux instance for the
// subject (window.studentDesktop.sandbox, desktop/sandbox), an assignment rail,
// the assignment's files in an editor, a real terminal (xterm.js over
// studentDesktop.terminal), and Run / Check / Submit. Files are saved into the
// instance and the runtime syncs them to the server (docs/sandbox-runtime.md).
//
// Recording follows the lab sitting model: one opening = one sitting id, each
// assignment visited = its own session (POST /api/sessions with sandbox_lab_id).
// Editor keys and edits carry the file `path`; terminal keys carry surface
// "terminal" or "terminal-editor" and stay out of the identity channel; the
// runtime's own events (term_cmd, run, pkg_install, net_conn…) arrive as
// "sandbox.event" with a sessionKey and are logged into that assignment's session.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowLeft, Check, CircleAlert, Cpu, FileText, FlaskConical, MemoryStick, Play, RefreshCw, Send, SquareTerminal, X,
} from "lucide-react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { api } from "../api";
import { captureExtension, captureWindow, keyData, SNAPSHOT_EVERY_MS } from "../capture";
import { desktop, desktopError } from "../desktop";
import { newSittingId, startSandboxSession, type LiveSession } from "../editor/session";
import { LessonText } from "../learn/LessonText";
import { FileEditor } from "../sandbox/bits";
import type { Network } from "../sandbox/api";
import { Badge, Button, Card, Dialog, LiveDot, Spinner, TextArea, cn, spring } from "../ui";
import type { OpenedLab } from "@studentide/sandbox";
import { NETWORK_LABEL, dueText } from "./SandboxLabs";

type Opened = OpenedLab;
type OpenedAsg = Opened["assignments"][number];
type RunResult = Awaited<ReturnType<NonNullable<typeof desktop>["sandbox"]["run"]>>;
type TestResult = Awaited<ReturnType<NonNullable<typeof desktop>["sandbox"]["test"]>>[number];
type SetupCheck = Awaited<ReturnType<NonNullable<typeof desktop>["sandbox"]["setupCheck"]>>["checks"][number];

/** The lab as a student gets it (GET /api/sandbox/my/labs/{id}, format studentide.sandbox-lab/1). */
interface StudentLab {
  id: string; title: string; description: string; network: Network; assessed: boolean; due_at: number | null;
  subject: { id: string; code: string; title: string };
  environment: { title: string } | null;
  assignments: Array<{
    id: string; title: string; statement: string; run: string; open: string[];
    tests: { visible?: Array<{ name: string; stdin: string; expected: string }>; n_hidden?: number };
  }>;
}
type Spec = StudentLab["assignments"][number];

/** A graded submission (server side: "Record and grade sandbox lab work"); hidden tests carry only name + passed. */
export interface Submission {
  id: string; assignment_id: string; status: "queued" | "grading" | "graded" | "failed" | "no_tests";
  passed: number | null; total: number | null; late?: boolean; submitted_at: number; graded_at: number | null; error?: string | null;
  results?: Array<{ name: string; hidden?: boolean; passed: boolean; expected?: string; got?: string; stderr?: string; timed_out?: boolean }>;
}
const GRADING = new Set(["queued", "grading"]);

/** Latest submission per assignment, or null where the server has no grading yet (404) . */
async function latestSubmissions(labId: string, studentId: string): Promise<Record<string, Submission | null> | null> {
  try {
    const r = await api<{ assignments: Record<string, Submission | null> }>(
      `/api/sandbox/my/labs/${encodeURIComponent(labId)}/submissions?student_id=${encodeURIComponent(studentId)}`);
    return r.assignments ?? {};
  } catch { return null; }
}

/** Build outputs and tool folders that the file list leaves out (the runtime does not sync them either). */
const HIDDEN = /(^|\/)(node_modules|__pycache__|\.venv|venv|\.git|target|build|dist|\.cache)(\/|$)|\.(o|class|pyc)$|(^|\/)a\.out$/;

export function SandboxLab({ studentId, labId, onBack }: { studentId: string; labId: string; onBack: () => void }) {
  const [lab, setLab] = useState<StudentLab | null>(null);
  const [opened, setOpened] = useState<Opened | null>(null);
  const [progress, setProgress] = useState<{ message: string; percent?: number }>({ message: "Getting the lab ready…" });
  const [error, setError] = useState("");
  const [checks, setChecks] = useState<SetupCheck[] | null>(null);
  const [active, setActive] = useState("");
  const [sessions, setSessions] = useState<Record<string, LiveSession>>({});
  const [fsTick, setFsTick] = useState<Record<string, number>>({});
  const [subs, setSubs] = useState<Record<string, Submission | null> | null>(null);
  const [justSubmitted, setJustSubmitted] = useState<Record<string, boolean>>({});
  const sitting = useMemo(newSittingId, []);
  const live = useRef(new Map<string, LiveSession>());           // by assignment id
  const starting = useRef(new Map<string, Promise<LiveSession>>());
  const pending = useRef(new Map<string, Array<{ type: string; data: unknown }>>()); // by assignment id, until its session exists
  const openedRef = useRef<Opened | null>(null);
  const activeRef = useRef("");

  const ensure = useCallback((asgId: string): Promise<LiveSession> => {
    const have = live.current.get(asgId);
    if (have) return Promise.resolve(have);
    let p = starting.current.get(asgId);
    if (!p) {
      p = startSandboxSession(studentId, labId, asgId, sitting).then((s) => {
        live.current.set(asgId, s);
        for (const ev of pending.current.get(asgId) ?? []) s.rec.log(ev.type as never, ev.data as Record<string, unknown>);
        pending.current.delete(asgId);
        setSessions((cur) => ({ ...cur, [asgId]: s }));
        return s;
      });
      p.catch(() => starting.current.delete(asgId));
      starting.current.set(asgId, p);
    }
    return p;
  }, [studentId, labId, sitting]);

  const switchTo = useCallback((asgId: string) => {
    const prev = activeRef.current;
    if (prev === asgId) return;
    live.current.get(prev)?.rec.log("focus", { target: "question", state: "out" });
    activeRef.current = asgId;
    setActive(asgId);
    ensure(asgId).then((s) => s.rec.log("focus", { target: "question", state: "in" }), (e) => setError((e as Error).message));
  }, [ensure]);

  // open: the lab definition (statement, tests) and the instance, in parallel
  useEffect(() => {
    if (!desktop) { setError("Sandbox labs open in the Student IDE app."); return; }
    const offs = [
      desktop.on("sandbox.progress", (p) => setProgress({ message: p.message, percent: p.percent })),
      desktop.on("sandbox.event", ({ sessionKey, type, data }) => {
        const a = openedRef.current?.assignments.find((x) => x.sessionKey === sessionKey);
        const asgId = a?.id ?? sessionKey.split("/")[1] ?? "";
        if (type === "term_cmd" && (data as { phase?: string })?.phase === "end") setFsTick((t) => ({ ...t, [asgId]: (t[asgId] ?? 0) + 1 }));
        const s = live.current.get(asgId);
        if (s) s.rec.log(type as never, data as Record<string, unknown>);
        else pending.current.set(asgId, [...(pending.current.get(asgId) ?? []), { type, data }]);
      }),
    ];
    let cancelled = false;
    Promise.all([
      api<StudentLab>(`/api/sandbox/my/labs/${encodeURIComponent(labId)}?student_id=${encodeURIComponent(studentId)}`),
      desktop.sandbox.openLab(labId),
    ]).then(([l, o]) => {
      if (cancelled) return;
      setLab(l);
      try { localStorage.setItem("studentide.sandbox.last", labId); } catch { /* private mode */ }
      void latestSubmissions(labId, studentId).then(setSubs);
      openedRef.current = o;
      setOpened(o);
      if (o.assignments[0]) switchTo(o.assignments[0].id);
    }, async (e) => {
      if (cancelled) return;
      setError(desktopError(e).message);
      try { setChecks((await desktop!.sandbox.setupCheck()).checks.filter((c) => !c.ok)); } catch { /* the error says enough */ }
    });
    return () => { cancelled = true; offs.forEach((off) => off()); };
  }, [labId, studentId, switchTo]);

  // window focus for every open session; close all sessions when leaving the lab
  useEffect(() => {
    const unsub: Array<() => void> = [];
    for (const s of Object.values(sessions)) unsub.push(captureWindow(s.rec));
    return () => unsub.forEach((u) => u());
  }, [sessions]);
  useEffect(() => {
    const gone = () => live.current.forEach((s) => s.rec.beacon());
    window.addEventListener("pagehide", gone);
    return () => {
      window.removeEventListener("pagehide", gone);
      live.current.forEach((s) => { s.rec.log("session_end", { wall_clock_ms: Date.now(), reason: "closed" }); void s.rec.close(); });
    };
  }, []);

  // grading takes a few seconds on the server: poll while any submission is queued or grading
  const grading = !!subs && Object.values(subs).some((x) => x && GRADING.has(x.status));
  useEffect(() => {
    if (!grading) return;
    const t = setInterval(() => void latestSubmissions(labId, studentId).then((x) => x && setSubs(x)), 3000);
    return () => clearInterval(t);
  }, [grading, labId, studentId]);
  const onSubmitted = (asgId: string, sub?: Submission | null) => {
    setJustSubmitted((m) => ({ ...m, [asgId]: true }));
    if (sub) setSubs((m) => ({ ...(m ?? {}), [asgId]: sub }));
    void latestSubmissions(labId, studentId).then((x) => x && setSubs(x));
  };

  // Ctrl/Cmd+1…9: switch assignment (Run is Ctrl/Cmd+Enter inside the pane)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || !/^[1-9]$/.test(e.key)) return;
      const a = openedRef.current?.assignments[Number(e.key) - 1];
      if (a) { e.preventDefault(); switchTo(a.id); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [switchTo]);

  const leave = () => onBack();
  const chip = (id: string) => {
    const x = subs?.[id];
    if (x?.status === "graded" && x.total) return x.passed === x.total ? "pass" : "partial";
    if (x || justSubmitted[id]) return "submitted";
    return sessions[id] ? "started" : "new";
  };
  const specOf = (id: string) => lab?.assignments.find((a) => a.id === id);

  return (
    <div className="flex h-full flex-col bg-bg">
      <header className="flex flex-wrap items-center gap-3 border-b border-border bg-surface px-4 py-2.5">
        <button onClick={leave} className="inline-flex items-center gap-1 text-[13px] text-muted hover:text-text"><ArrowLeft className="size-3.5" /> Labs</button>
        <span className="h-4 w-px bg-border" />
        <div className="min-w-0">
          <h1 className="truncate text-[15px] font-semibold text-text">{lab?.title ?? "Sandbox lab"}</h1>
          {lab && <p className="truncate text-[11px] text-faint">{lab.subject.title}{lab.environment ? ` · ${lab.environment.title}` : ""}</p>}
        </div>
        {lab && <Badge tone={lab.network === "open" ? "neutral" : "accent"}>{NETWORK_LABEL[lab.network]}</Badge>}
        {lab?.due_at && <span className="text-xs text-faint">{dueText(lab.due_at)}</span>}
        <span className="flex-1" />
        {opened && <Usage instanceId={opened.instanceId} />}
        {opened && !opened.limitsEnforced && <Badge tone="warn" className="hidden md:inline-flex">No CPU/memory limits on this computer</Badge>}
        {Object.keys(sessions).length > 0 && (
          <span className="flex items-center gap-1.5 text-xs text-muted" title="Your typing, edits, terminal commands and runs in this lab are recorded for your teacher">
            <LiveDot tone="danger" /> Recorded for this lab
          </span>
        )}
      </header>

      {error ? (
        <div className="grid flex-1 place-items-center p-6">
          <Card className="grid max-w-lg gap-3 p-6">
            <p className="flex items-start gap-2 text-sm text-text"><CircleAlert className="mt-0.5 size-4 shrink-0 text-danger" />{error}</p>
            {checks?.map((c) => (
              <div key={c.id} className={cn("rounded-lg border px-3 py-2 text-[13px]", c.severity === "error" ? "border-danger/40 bg-danger-soft" : "border-warn/40 bg-warn-soft")}>
                <p className="text-text">{c.message}</p>
                {c.fix && <p className="mt-0.5 text-muted">{c.fix}</p>}
              </div>
            ))}
            <p className="text-xs text-muted">Your files are saved on the server, so you can also open this lab on another computer that passes the setup check.</p>
            <div className="flex gap-2"><Button onClick={() => location.reload()}><RefreshCw className="size-3.5" /> Try again</Button><Button variant="ghost" onClick={leave}>Back to labs</Button></div>
          </Card>
        </div>
      ) : !opened || !lab ? (
        <div className="grid flex-1 place-items-center p-6">
          <div className="grid w-full max-w-sm justify-items-center gap-3 text-center">
            <Spinner className="size-6 text-accent" />
            <AnimatePresence mode="wait">
              <motion.p key={progress.message} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} className="text-sm text-text">{progress.message}</motion.p>
            </AnimatePresence>
            <div className="h-1 w-full overflow-hidden rounded-full bg-surface-3">
              <motion.div className="h-full bg-accent" animate={{ width: `${progress.percent ?? 8}%` }} transition={spring} />
            </div>
            <p className="text-xs text-muted">The first start of a subject downloads its environment and can take a few minutes. After that it opens in seconds.</p>
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <nav className="flex w-14 shrink-0 flex-col items-center gap-1.5 border-r border-border bg-surface py-3 md:w-56 md:items-stretch md:px-2" aria-label="Assignments">
            {opened.assignments.map((a, i) => (
              <button key={a.id} onClick={() => switchTo(a.id)} title={a.title}
                className={cn("relative flex items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[13px]", a.id === active ? "text-text" : "text-muted hover:text-text")}>
                {a.id === active && <motion.span layoutId="sbx-asg" transition={spring} className="absolute inset-0 rounded-lg bg-surface-3" />}
                <span className={cn("relative grid size-6 shrink-0 place-items-center rounded-md font-mono text-[11px] font-semibold",
                  { pass: "bg-success-soft text-success", partial: "bg-warn-soft text-warn", submitted: "bg-success-soft text-success",
                    started: "bg-accent-soft text-accent", new: "bg-surface-3 text-muted" }[chip(a.id)])}>
                  {chip(a.id) === "pass" || chip(a.id) === "submitted" ? <Check className="size-3.5" /> : i + 1}
                </span>
                <span className="relative hidden min-w-0 flex-1 md:block">
                  <span className="block truncate">{a.title}</span>
                  <span className="block text-[11px] text-faint">{{ pass: "All tests pass", partial: `${subs?.[a.id]?.passed} of ${subs?.[a.id]?.total} tests pass`,
                    submitted: GRADING.has(subs?.[a.id]?.status ?? "") ? "Grading…" : "Submitted", started: "In progress", new: "Not started" }[chip(a.id)]}
                    {i < 9 && <span className="ml-1 hidden font-mono opacity-60 lg:inline">⌃{i + 1}</span>}</span>
                </span>
              </button>
            ))}
            {opened.setup && <p className="mt-auto hidden px-2 text-[11px] text-faint md:block">Setup restored: {opened.setup.ok} of {opened.setup.replayed} package commands</p>}
          </nav>
          {/* every visited assignment stays mounted, so its terminal and editor survive switching */}
          {opened.assignments.map((a) => sessions[a.id] && specOf(a.id) ? (
            <div key={a.id} className={cn("min-h-0 min-w-0 flex-1", a.id === active ? "flex" : "hidden")}>
              <AssignmentPane instanceId={opened.instanceId} a={a} spec={specOf(a.id)!} session={sessions[a.id]}
                active={a.id === active} fsTick={fsTick[a.id] ?? 0} submission={subs?.[a.id] ?? null}
                onSubmitted={(sub) => onSubmitted(a.id, sub)} />
            </div>
          ) : a.id === active ? <div key={a.id} className="grid flex-1 place-items-center"><Spinner /></div> : null)}
        </div>
      )}
    </div>
  );
}

/** CPU and memory of the instance, polled while the lab is open. */
function Usage({ instanceId }: { instanceId: string }) {
  const [s, setS] = useState<{ cpu: number | null; mem: number | null; lim: number | null } | null>(null);
  useEffect(() => {
    const tick = () => desktop?.sandbox.stats(instanceId).then((x) => setS({ cpu: x.cpuPercent, mem: x.memoryBytes, lim: x.memoryLimitBytes }), () => {});
    tick();
    const t = setInterval(tick, 5000);
    return () => clearInterval(t);
  }, [instanceId]);
  if (!s) return null;
  const gb = (b: number) => `${(b / 2 ** 30).toFixed(1)} GB`;
  return (
    <span className="hidden items-center gap-3 font-mono text-[11px] text-muted sm:flex">
      <span className="flex items-center gap-1" title="CPU"><Cpu className="size-3.5" />{s.cpu == null ? "–" : `${Math.round(s.cpu)}%`}</span>
      <span className="flex items-center gap-1" title="Memory"><MemoryStick className="size-3.5" />{s.mem == null ? "–" : gb(s.mem)}{s.lim ? ` / ${gb(s.lim)}` : ""}</span>
    </span>
  );
}

function AssignmentPane({ instanceId, a, spec, session, active, fsTick, submission, onSubmitted }: {
  instanceId: string; a: OpenedAsg; spec: Spec; session: LiveSession; active: boolean; fsTick: number;
  submission: Submission | null; onSubmitted: (sub?: Submission | null) => void;
}) {
  const sb = desktop!.sandbox;
  const [files, setFiles] = useState<string[]>([]);
  const [cur, setCur] = useState(a.open[0] ?? spec.open[0] ?? "");
  const [content, setContent] = useState<string | null>(null);
  const [saved, setSaved] = useState(true);
  const [panel, setPanel] = useState<"statement" | "output" | "tests" | "grade">("statement");
  const [stdin, setStdin] = useState(spec.tests.visible?.[0]?.stdin ?? "");
  const [out, setOut] = useState<RunResult | null>(null);
  const [tests, setTests] = useState<TestResult[] | null>(null);
  const [busy, setBusy] = useState<"" | "run" | "check" | "submit">("");
  const [confirm, setConfirm] = useState(false);
  const [note, setNote] = useState("");
  const pendingText = useRef<string | null>(null);
  const timer = useRef(0);
  const lastSnap = useRef<string | null>(null);
  const textRef = useRef<string>("");
  const abs = (p: string) => `${a.workdir}/${p}`;
  const rec = session.rec;

  const refresh = useCallback(() => sb.listFiles(instanceId, a.workdir).then((fs) => {
    const list = fs.filter((f) => f.type === "file" && !HIDDEN.test(f.path)).map((f) => f.path);
    setFiles(list);
    setCur((c) => c || list[0] || "");
  }, () => {}), [sb, instanceId, a.workdir]);
  useEffect(() => { void refresh(); }, [refresh]);

  const flush = useCallback(async () => {
    window.clearTimeout(timer.current);
    const text = pendingText.current;
    if (text === null || !cur) return;
    pendingText.current = null;
    try { await sb.writeFile(instanceId, abs(cur), text); setSaved(true); } catch (e) { setNote(desktopError(e).message); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sb, instanceId, cur]);

  // open a file: read it from the instance and log its starting text (replay needs a base per path)
  useEffect(() => {
    if (!cur) return;
    let gone = false;
    setContent(null);
    sb.readFile(instanceId, abs(cur)).then((t) => {
      if (gone) return;
      textRef.current = t;
      lastSnap.current = t;
      rec.log("snapshot", { reason: "start", text: t, path: cur });
      setContent(t);
    }, () => { if (!gone) { textRef.current = ""; setContent(""); } });
    return () => { gone = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur, instanceId]);

  // a terminal command ended: files may have changed (vim, a compiler, git); reload the open one unless unsaved
  useEffect(() => {
    if (!fsTick) return;
    void refresh();
    if (!cur || pendingText.current !== null) return;
    sb.readFile(instanceId, abs(cur)).then((t) => { if (pendingText.current === null && t !== textRef.current) { textRef.current = t; setContent(t); } }, () => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fsTick]);

  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => {
      if (cur && textRef.current !== lastSnap.current) {
        lastSnap.current = textRef.current;
        rec.log("snapshot", { reason: "periodic", text: textRef.current, path: cur });
      }
    }, SNAPSHOT_EVERY_MS);
    return () => clearInterval(t);
  }, [active, cur, rec]);

  const edit = (v: string) => {
    textRef.current = v;
    pendingText.current = v;
    setSaved(false);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), 700);
  };
  const extensions = useMemo(() => (cur ? [captureExtension(rec, { path: cur })] : []), [rec, cur]);

  const act = async (kind: "run" | "check") => {
    setBusy(kind);
    setNote("");
    try {
      await flush();
      if (cur) rec.log("snapshot", { reason: "run", text: textRef.current, path: cur });
      if (kind === "run") { setOut(await sb.run(instanceId, a.id, { stdin })); setPanel("output"); }
      else { setTests(await sb.test(instanceId, a.id)); setPanel("tests"); }
      void refresh();
    } catch (e) { setNote(desktopError(e).message); }
    finally { setBusy(""); }
  };
  const submit = async () => {
    setConfirm(false);
    setBusy("submit");
    try {
      await flush();
      const r = await sb.submit(instanceId, a.id) as { sha256: string; submission?: Submission };
      onSubmitted(r.submission);
      setPanel("grade");
      setNote("Submitted. This copy of your files goes to your teacher; you can keep working and submit again until the lab closes.");
    } catch (e) { setNote(desktopError(e).message); }
    finally { setBusy(""); }
  };

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !busy && spec.run) { e.preventDefault(); void act("run"); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const visible = spec.tests.visible ?? [];
  const passed = tests?.filter((t) => t.passed).length ?? 0;

  return (
    <div className="grid min-h-0 min-w-0 flex-1 grid-rows-[minmax(0,3fr)_minmax(140px,2fr)] gap-2 p-2">
      <div className="grid min-h-0 grid-cols-[150px_minmax(0,1fr)] gap-2 lg:grid-cols-[170px_minmax(0,1fr)_340px]">
        <Card className="flex min-h-0 flex-col overflow-hidden">
          <div className="flex items-center justify-between px-2.5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-faint">
            Files <button onClick={() => void refresh()} aria-label="Refresh files" className="hover:text-text"><RefreshCw className="size-3" /></button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-1.5">
            {files.map((f) => (
              <button key={f} onClick={async () => { await flush(); setCur(f); }} title={f}
                className={cn("flex w-full items-center gap-1.5 truncate rounded-md px-1.5 py-1 text-left font-mono text-xs", f === cur ? "bg-surface-3 text-text" : "text-muted hover:text-text")}>
                <FileText className="size-3 shrink-0" /><span className="truncate">{f}</span>
              </button>
            ))}
            {!files.length && <p className="px-1.5 text-xs text-faint">No files yet. Make some in the terminal.</p>}
          </div>
          {a.files !== "new" && a.files !== "kept" && (
            <p className="border-t border-border px-2.5 py-1.5 text-[11px] text-muted">
              {a.files === "restored" ? "Restored from your last save on the server." : "Changed here and on the server: the server copy is open, yours is kept beside it."}
            </p>
          )}
        </Card>

        <Card className="relative flex min-h-0 flex-col overflow-hidden">
          <div className="flex items-center gap-2 border-b border-border px-3 py-1.5">
            <span className="truncate font-mono text-xs text-text">{cur || "no file"}</span>
            <span className="text-[11px] text-faint">{saved ? "saved" : "saving…"}</span>
            <span className="flex-1" />
            <Button size="sm" variant="primary" disabled={!!busy || !spec.run} onClick={() => act("run")} title={spec.run ? `${spec.run} (Ctrl+Enter)` : "this assignment has no Run command"}>
              {busy === "run" ? <Spinner /> : <Play className="size-3.5 fill-current" />} Run
            </Button>
            {visible.length > 0 && (
              <Button size="sm" disabled={!!busy} onClick={() => act("check")} title="Runs the tests you can see, on this computer">
                {busy === "check" ? <Spinner /> : <FlaskConical className="size-3.5" />} Check
              </Button>
            )}
            <Button size="sm" disabled={!!busy} onClick={() => setConfirm(true)}>{busy === "submit" ? <Spinner /> : <Send className="size-3.5" />} Submit</Button>
          </div>
          <div className="min-h-0 flex-1">
            {content === null ? <div className="grid h-full place-items-center"><Spinner /></div>
              : cur ? <FileEditor key={cur} path={cur} value={content} onChange={edit} extensions={extensions} />
              : <div className="grid h-full place-items-center text-sm text-muted">Pick a file on the left.</div>}
          </div>
          <AnimatePresence>
            {note && (
              <motion.p initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className="absolute inset-x-3 bottom-3 flex items-start gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-text shadow-lg">
                <span className="flex-1">{note}</span><button onClick={() => setNote("")} aria-label="Dismiss"><X className="size-3.5 text-muted" /></button>
              </motion.p>
            )}
          </AnimatePresence>
        </Card>

        <Card className="col-span-2 hidden min-h-0 flex-col overflow-hidden lg:col-span-1 lg:flex">
          <div className="flex gap-1 border-b border-border p-1.5 text-[13px]">
            {(["statement", "output", "tests", ...(submission ? ["grade" as const] : [])] as const).map((t) => (
              <button key={t} onClick={() => setPanel(t)} className={cn("rounded-md px-2.5 py-1 font-medium capitalize", panel === t ? "bg-surface-3 text-text" : "text-muted hover:text-text")}>
                {t}{t === "tests" && tests ? ` ${passed}/${tests.length}` : ""}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {panel === "grade" && submission && <Grade s={submission} />}
            {panel === "statement" && (
              <>
                <Tips />
                <h2 className="mb-2 text-[15px] font-semibold text-text">{spec.title}</h2>
                <LessonText markdown={spec.statement || "*No statement.*"} language="" />
                {spec.run && <p className="mt-3 text-xs text-muted">Run does <code className="font-mono text-text">{spec.run}</code> in this folder.</p>}
              </>
            )}
            {panel === "output" && (out ? (
              <div className="grid gap-1.5">
                <p className="text-xs text-muted">exit {out.exit_code ?? "?"}{out.error_type ? ` · ${out.error_type}` : ""} · {out.duration_ms} ms</p>
                <pre className="max-h-[50vh] overflow-auto whitespace-pre-wrap rounded-lg bg-console p-2 font-mono text-xs text-console-text">{out.stdout}{out.stderr && <span className="text-console-danger">{out.stderr}</span>}{!out.stdout && !out.stderr && <span className="opacity-60">(no output)</span>}</pre>
              </div>
            ) : <p className="text-sm text-muted">Run to see the output here.</p>)}
            {panel === "tests" && (tests ? (
              <div className="grid gap-1.5">
                <p className="text-sm font-medium text-text">{passed} of {tests.length} tests pass{spec.tests.n_hidden ? ` · ${spec.tests.n_hidden} more checked by your teacher` : ""}</p>
                {tests.map((r, i) => (
                  <motion.div key={r.name + i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                    className={cn("rounded-lg border p-2 text-xs", r.passed ? "border-success/40 bg-success-soft" : "border-danger/40 bg-danger-soft")}>
                    <p className="flex items-center gap-1 font-medium text-text">{r.passed ? <Check className="size-3.5 text-success" /> : <X className="size-3.5 text-danger" />}{r.name}</p>
                    {!r.passed && r.expected !== undefined && <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-muted">expected {JSON.stringify(r.expected)}{"\n"}got      {JSON.stringify(r.stdout)}</pre>}
                    {!r.passed && r.stderr && <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-danger">{r.stderr.slice(-400)}</pre>}
                  </motion.div>
                ))}
              </div>
            ) : <p className="text-sm text-muted">{visible.length ? "Check runs the tests you can see, on this computer. Grades come from the server." : "This assignment has no tests you can run."}</p>)}
          </div>
          <div className="border-t border-border p-2">
            <TextArea rows={2} value={stdin} onChange={(e) => setStdin(e.target.value)} placeholder="Input for Run (stdin)" className="font-mono text-xs" />
          </div>
        </Card>
      </div>

      <Card className="flex min-h-0 flex-col overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-faint">
          <SquareTerminal className="size-3.5" /> Terminal <span className="font-mono font-normal normal-case tracking-normal">{a.workdir.replace("/home/student", "~")}</span>
        </div>
        <DesktopTerminal instanceId={instanceId} assignmentId={a.id} session={session} visible={active} />
      </Card>

      <Dialog open={confirm} onClose={() => setConfirm(false)} title={`Submit “${spec.title}”?`} icon={<Send className="size-5" />}
        description={<>Every file in this assignment's folder is sent to the server as your submission{tests ? `; ${passed} of ${tests.length} visible tests pass here` : ""}. You can submit again later.</>}
        actions={<><Button variant="ghost" onClick={() => setConfirm(false)}>Not yet</Button><Button variant="primary" data-autofocus onClick={() => void submit()}>Submit</Button></>} />
    </div>
  );
}

/** One shell in the assignment folder, inside the instance. Keys are logged with their surface; pastes go through terminal.paste. */
function DesktopTerminal({ instanceId, assignmentId, session, visible }: { instanceId: string; assignmentId: string; session: LiveSession; visible: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const resizeRef = useRef<() => void>(() => {});
  const [gen, setGen] = useState(0);
  const [exited, setExited] = useState(false);

  useEffect(() => {
    const d = desktop!;
    const rec = session.rec;
    const css = getComputedStyle(document.documentElement);
    const term = new XTerm({
      fontFamily: css.getPropertyValue("--font-mono") || "monospace", fontSize: 13, cursorBlink: true, scrollback: 5000,
      theme: { background: css.getPropertyValue("--console").trim() || "#111", foreground: css.getPropertyValue("--console-text").trim() || "#eee" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(host.current!);
    try { fit.fit(); } catch { /* hidden */ }
    let id = "";
    let surface: { surface: "terminal" | "terminal-editor"; path?: string } = { surface: "terminal" };
    const offs = [
      d.on("terminal.data", (e) => { if (e.id === id) term.write(e.data); }),
      d.on("terminal.exit", (e) => { if (e.id === id) { term.write("\r\n\x1b[2m[shell ended]\x1b[0m\r\n"); setExited(true); } }),
      d.on("terminal.surface", (e) => { if (e.id === id) surface = { surface: e.surface, ...(e.path ? { path: e.path } : {}) }; }),
    ];
    d.terminal.open(instanceId, { assignmentId, cols: term.cols, rows: term.rows }).then((r) => { id = r.id; }, (e) => term.write(`\x1b[31m${desktopError(e).message}\x1b[0m\r\n`));
    const data = term.onData((s) => { if (id) void d.terminal.write(id, s); });
    const resize = () => {
      try { fit.fit(); } catch { return; }
      if (id) void d.terminal.resize(id, term.cols, term.rows);
    };
    resizeRef.current = resize;
    const el = host.current!;
    const down = (e: KeyboardEvent) => rec.log("key", { ...keyData(e, "down"), ...surface }, e.timeStamp);
    const up = (e: KeyboardEvent) => rec.log("key", { ...keyData(e, "up"), ...surface }, e.timeStamp);
    const paste = (e: ClipboardEvent) => {
      const text = e.clipboardData?.getData("text/plain") ?? "";
      e.preventDefault();
      e.stopPropagation();
      if (id && text) void d.terminal.paste(id, text); // the runtime logs term_paste, then types it
    };
    el.addEventListener("keydown", down, true);
    el.addEventListener("keyup", up, true);
    el.addEventListener("paste", paste, true);
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    return () => {
      ro.disconnect(); data.dispose(); offs.forEach((off) => off());
      el.removeEventListener("keydown", down, true); el.removeEventListener("keyup", up, true); el.removeEventListener("paste", paste, true);
      if (id) void d.terminal.close(id);
      term.dispose();
    };
  }, [instanceId, assignmentId, session, gen]);

  useEffect(() => { if (visible) requestAnimationFrame(() => resizeRef.current()); }, [visible]);

  return (
    <div className="relative min-h-0 flex-1 bg-console">
      <div key={gen} ref={host} className="absolute inset-0 overflow-hidden p-2" />
      {exited && (
        <button onClick={() => { setExited(false); setGen((g) => g + 1); }}
          className="absolute bottom-3 right-3 rounded-md bg-surface px-2.5 py-1 text-xs font-medium text-text shadow">New shell</button>
      )}
    </div>
  );
}

/** The server's grade for the latest submission: every test, hidden ones by name only. */
function Grade({ s }: { s: Submission }) {
  if (GRADING.has(s.status)) return <p className="flex items-center gap-2 text-sm text-muted"><Spinner /> Grading on the server…</p>;
  if (s.status === "failed") return <p className="text-sm text-danger">Grading failed: {s.error ?? "unknown error"}. Your submission is kept; your teacher can grade it again.</p>;
  if (s.status === "no_tests") return <p className="text-sm text-muted">Submitted {new Date(s.submitted_at * 1000).toLocaleString()}. This assignment is marked by your teacher.</p>;
  const all = s.total != null && s.passed === s.total;
  return (
    <div className="grid gap-1.5">
      <motion.p initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className={cn("flex items-center gap-1.5 text-sm font-semibold", all ? "text-success" : "text-text")}>
        {all && <Check className="size-4" />}{s.passed} of {s.total} tests pass{s.late ? " · late" : ""}
      </motion.p>
      <p className="text-[11px] text-faint">Graded {s.graded_at ? new Date(s.graded_at * 1000).toLocaleString() : ""} on the server, hidden tests included.</p>
      {s.results?.map((r, i) => (
        <motion.div key={r.name + i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}
          className={cn("rounded-lg border p-2 text-xs", r.passed ? "border-success/40 bg-success-soft" : "border-danger/40 bg-danger-soft")}>
          <p className="flex items-center gap-1 font-medium text-text">{r.passed ? <Check className="size-3.5 text-success" /> : <X className="size-3.5 text-danger" />}{r.name}
            {r.hidden && <Badge className="ml-1">hidden</Badge>}{r.timed_out && <Badge tone="warn" className="ml-1">timed out</Badge>}</p>
          {!r.passed && !r.hidden && r.expected !== undefined && <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-muted">expected {JSON.stringify(r.expected)}{"\n"}got      {JSON.stringify(r.got)}</pre>}
        </motion.div>
      ))}
    </div>
  );
}

/** First-visit orientation, like the run/evaluate actions VPL and CodeGrade put up front; dismissed once for every lab. */
function Tips() {
  const KEY = "studentide.sandbox.tips";
  const [show, setShow] = useState(() => { try { return !localStorage.getItem(KEY); } catch { return true; } });
  if (!show) return null;
  const close = () => { setShow(false); try { localStorage.setItem(KEY, "1"); } catch { /* private mode */ } };
  return (
    <div className="mb-3 rounded-lg border border-accent/30 bg-accent-soft p-2.5 text-[12px] text-text">
      <div className="flex items-start justify-between gap-2">
        <strong className="font-semibold">How this lab works</strong>
        <button onClick={close} aria-label="Hide tips"><X className="size-3.5 text-muted" /></button>
      </div>
      <ol className="mt-1 grid list-decimal gap-0.5 pl-4 text-muted">
        <li>Edit the files on the left; they save by themselves.</li>
        <li><strong className="text-text">Run</strong> (Ctrl+Enter) runs the assignment; <strong className="text-text">Check</strong> tries the tests you can see.</li>
        <li>The terminal below is a full Linux shell: install packages, use git, vim, gdb…</li>
        <li><strong className="text-text">Submit</strong> sends your files to be graded. Your work also follows you to any other computer.</li>
      </ol>
    </div>
  );
}
