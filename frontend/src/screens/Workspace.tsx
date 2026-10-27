import { useCallback, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { basicSetup } from "codemirror";
import { python } from "@codemirror/lang-python";
import { cpp } from "@codemirror/lang-cpp";
import { java } from "@codemirror/lang-java";
import { javascript } from "@codemirror/lang-javascript";
import { EditorView, keymap } from "@codemirror/view";
import { EditorState, Prec } from "@codemirror/state";
import { indentUnit } from "@codemirror/language";
import { indentWithTab } from "@codemirror/commands";
import { CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, CircleAlert, Eye, EyeOff, Flag, FlaskConical, PanelLeftClose, PanelLeftOpen, Play, Terminal, Trophy } from "lucide-react";
import { api, type CheckResult, type RunResult, type Task } from "../api";
import { GradeView } from "../teach/bits";
import { LANGUAGES, type Language } from "../teach/api";
import { captureExtension, captureWindow, SNAPSHOT_EVERY_MS } from "../capture";
import { rememberLanguage, type LiveSession } from "../editor/session";
import type { Recorder } from "../recorder";
import { editorTheme } from "../editor/theme";
import { QuestionText } from "../questionText";
import { Badge, Button, Dialog, Kbd, LiveDot, LogoMark, Spinner, TextArea, cn, duration, ease } from "../ui";
import type { CompClock, SubmitResult } from "../compete/api";
import { SubmitDialog } from "../compete/SubmitDialog";
import { Countdown } from "../compete/Leaderboard";

export interface SessionSummary {
  runs: number;
  minutes: number;
  /** a lab sitting: how many of its questions the student wrote code for */
  questions?: { worked: number; total: number };
}

interface Outcome {
  text: string;
  failed: boolean;
  exitCode: number | null;
  durationMs: number | null;
  errorType: string | null;
}

/** One question of the sitting once opened: its own session, recorder and editor state.
 * In an any-language competition each language a question is opened in is its own slot (and session). */
interface Slot {
  session: LiveSession;
  language: Language;
  state: EditorState;
  initial: string;
  lastSnapshot: string;
  stdin: string;
}

const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
/** How often a competition editor checks the clock (the teacher may end early). */
const CLOCK_POLL_MS = 5000;

const SYNTAX = { python, c: cpp, cpp, java, javascript: () => javascript() };

/** The language a question is written in: its lab's, or the one picked in an any-language competition. */
function fixedLanguage(t: Task): Language {
  return !t.language || t.language === "any" ? "python" : t.language;
}

function starterFor(t: Task, language: Language): string {
  return t.language === "any" ? t.variants?.[language]?.starter_code ?? "" : t.starter_code;
}

const slotKey = (i: number, l: Language) => `${i}:${l}`;

/**
 * The editor screen. CodeMirror lives outside React state: it is created once
 * in an effect and never re-rendered, so typing triggers no React work at all.
 * Recording (captureExtension) is attached exactly as before the redesign.
 *
 * A lab opens as one sitting: `tasks` holds all its questions and the student
 * moves between them here. Each question visited is still its own recorded
 * session (created on first visit by `openSession`), so everything downstream
 * (detector, review, live view) keeps one session = one question. Switching
 * swaps the editor state, so each question keeps its code, undo history and
 * caret, and logs focus {target: "question"} out/in on the sessions involved.
 */
export function Workspace({ studentId, tasks, start = 0, session, openSession, onFinished }: {
  studentId: string;
  tasks: Task[];
  start?: number;
  /** the session for tasks[start] */
  session: LiveSession;
  /** starts the session for another question of the sitting, or (any-language competitions) another language */
  openSession?: (task: Task, language?: Language) => Promise<LiveSession>;
  onFinished: (summary: SessionSummary) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const stdin = useRef<HTMLTextAreaElement>(null);
  const view = useRef<EditorView>();
  const slots = useRef(new Map<string, Slot>());
  const activeRef = useRef(start);
  /** per question: the language it is open in (any-language competitions switch it) */
  const langOf = useRef(new Map<number, Language>([[start, session.language ?? fixedLanguage(tasks[start])]]));
  const finishRef = useRef<(reason: string) => void>(() => {});
  const onHideRef = useRef<() => void>(() => {});
  const runsRef = useRef(0);
  const t0 = useRef(performance.now());
  const linkState = useRef(new Map<string, { pending: number; ok: boolean }>());

  const [active, setActive] = useState(start);
  const [visited, setVisited] = useState<Set<number>>(() => new Set([start]));
  const [opening, setOpening] = useState<number | null>(null);
  const [switchError, setSwitchError] = useState("");
  const [running, setRunning] = useState(false);
  const [outcomes, setOutcomes] = useState<Record<number, Outcome>>({});
  const [runs, setRuns] = useState(0);
  const [link, setLink] = useState({ pending: 0, ok: true });
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [taskOpen, setTaskOpen] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [verdict, setVerdict] = useState<SubmitResult | { error: string } | null>(null);
  const [checking, setChecking] = useState(false);
  const [grades, setGrades] = useState<Record<number, CheckResult>>({});
  const [pane, setPane] = useState<"output" | "tests">("output");
  const [, setLangTick] = useState(0); // re-render after a language switch (langOf is a ref)
  const [switchingLang, setSwitchingLang] = useState(false);

  const task = tasks[active];
  const sitting = tasks.length > 1;
  const activeLang = langOf.current.get(active) ?? fixedLanguage(task);
  const sessionId = (slots.current.get(slotKey(active, activeLang))?.session ?? session).id;
  const outcome = outcomes[active] ?? null;
  const grade = grades[active] ?? null;
  const competing = !!task.competition;
  const watching = useViewers(sessionId);
  const language = activeLang;
  const lang = LANGUAGES[language];
  const pickLanguage = task.language === "any" && (task.languages?.length ?? 0) > 1;
  // Competitions submit for a score instead; a lab's Check is only for the student.
  const canCheck = (task.n_tests ?? 0) > 0 && !("competition" in task && task.competition);

  /** The question on screen. */
  const cur = () => {
    const i = activeRef.current;
    return slots.current.get(slotKey(i, langOf.current.get(i) ?? fixedLanguage(tasks[i])))!;
  };

  const makeSlot = useCallback((s: LiveSession, t: Task, language: Language): Slot => {
    const starter = starterFor(t, language);
    const doc = s.resumeCode ?? starter;
    const state = EditorState.create({
      doc,
      extensions: [
        basicSetup,
        SYNTAX[language](),
        indentUnit.of("    "),
        keymap.of([indentWithTab]),
        editorTheme,
        captureExtension(s.rec),
        Prec.highest(keymap.of([{ key: "Mod-Enter", run: () => (void runRef.current(), true) }])),
      ],
    });
    s.rec.onStatus = (pending, ok) => {
      linkState.current.set(s.id, { pending, ok });
      const all = [...linkState.current.values()];
      setLink({ pending: all.reduce((n, x) => n + x.pending, 0), ok: all.every((x) => x.ok) });
    };
    s.rec.log("snapshot", { reason: "start", text: doc });
    return { session: s, language, state, initial: starter, lastSnapshot: doc, stdin: t.sample_input };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checkCode = useCallback(async () => {
    const v = view.current;
    if (!v) return;
    const at = activeRef.current;
    setChecking(true);
    setPane("tests");
    try {
      const g = await api<CheckResult>(`/api/sessions/${cur().session.id}/check`, { code: v.state.doc.toString() });
      setGrades((m) => ({ ...m, [at]: g }));
    } catch (err) {
      setGrades((m) => ({ ...m, [at]: { check_id: "", passed: 0, total: 0, results: [{ name: `Could not check: ${(err as Error).message}`,
        passed: false, hidden: false, error_type: "network", duration_ms: 0 }] } }));
    } finally {
      setChecking(false);
    }
  }, []);

  const runningRef = useRef(false);
  const runCode = useCallback(async () => {
    const v = view.current;
    if (runningRef.current || !v) return;
    runningRef.current = true;
    // Commit "Running…" synchronously so the output never shows a stale result.
    flushSync(() => setRunning(true));
    setPane("output");
    const at = activeRef.current;
    const slot = cur();
    const { rec, id } = slot.session;
    const code = v.state.doc.toString();
    rec.log("snapshot", { reason: "run", text: code });
    slot.lastSnapshot = code;
    let out: Outcome;
    try {
      const r = await api<RunResult>(`/api/sessions/${id}/run`, { code, stdin: stdin.current?.value ?? "" });
      rec.log("run", {
        run_id: r.run_id, code_sha256: r.code_sha256, exit_code: r.exit_code,
        duration_ms: r.duration_ms, error_type: r.error_type,
      });
      out = {
        text: r.stdout + (r.stderr ? (r.stdout ? "\n" : "") + r.stderr : "") || "(no output)",
        failed: r.error_type !== null,
        exitCode: r.exit_code,
        durationMs: r.duration_ms,
        errorType: r.error_type,
      };
    } catch (err) {
      out = { text: `Could not run: ${(err as Error).message}`, failed: true, exitCode: null, durationMs: null, errorType: "network" };
    } finally {
      runsRef.current += 1;
      setRuns(runsRef.current);
      runningRef.current = false;
      setRunning(false);
    }
    setOutcomes((m) => ({ ...m, [at]: out }));
  }, []);

  const runRef = useRef(runCode);
  runRef.current = runCode;

  /** Competitions only: run the question's test cases on the server and score the result. */
  const submit = useCallback(async () => {
    const v = view.current;
    if (!v || runningRef.current) return;
    setSubmitting(true);
    const slot = cur();
    const code = v.state.doc.toString();
    slot.session.rec.log("snapshot", { reason: "run", text: code });
    slot.lastSnapshot = code;
    try {
      setVerdict(await api<SubmitResult>(`/api/sessions/${slot.session.id}/submit`, { code }));
    } catch (err) {
      setVerdict({ error: (err as Error).message });
    } finally {
      setSubmitting(false);
    }
  }, []);

  /** Move to another question of the sitting, opening its session on first visit. */
  const switchTo = async (to: number) => {
    const v = view.current;
    if (!v || to === activeRef.current || opening !== null || saving || runningRef.current) return;
    setSwitchError("");
    const from = cur();
    from.state = v.state;
    from.stdin = stdin.current?.value ?? "";
    const text = v.state.doc.toString();
    if (text !== from.lastSnapshot) {
      from.session.rec.log("snapshot", { reason: "periodic", text });
      from.lastSnapshot = text;
    }
    from.session.rec.log("focus", { target: "question", state: "out" });
    const toLang = langOf.current.get(to);
    let next = toLang && slots.current.get(slotKey(to, toLang));
    if (next) {
      next.session.rec.log("focus", { target: "question", state: "in" });
    } else {
      setOpening(to);
      try {
        const s = await openSession!(tasks[to]);
        next = makeSlot(s, tasks[to], s.language ?? fixedLanguage(tasks[to]));
        slots.current.set(slotKey(to, next.language), next);
        langOf.current.set(to, next.language);
      } catch (err) {
        from.session.rec.log("focus", { target: "question", state: "in" });
        setSwitchError((err as Error).message);
        return;
      } finally {
        setOpening(null);
      }
    }
    activeRef.current = to;
    v.setState(next.state);
    if (stdin.current) stdin.current.value = next.stdin;
    (window as any).__studentide = { rec: next.session.rec, sessionId: next.session.id }; // for end-to-end tests
    setActive(to);
    setVisited((s) => new Set(s).add(to));
    setPane("output");
    v.focus();
  };

  /** Any-language competitions: answer this question in another language. Each
   * language keeps its own code (and is its own recorded session), so switching
   * back finds the code where it was left. */
  const switchLanguage = async (to: Language) => {
    const v = view.current;
    const i = activeRef.current;
    if (!v || to === langOf.current.get(i) || switchingLang || saving || runningRef.current) return;
    setSwitchError("");
    const from = cur();
    from.state = v.state;
    from.stdin = stdin.current?.value ?? "";
    const text = v.state.doc.toString();
    if (text !== from.lastSnapshot) {
      from.session.rec.log("snapshot", { reason: "periodic", text });
      from.lastSnapshot = text;
    }
    from.session.rec.log("focus", { target: "question", state: "out" });
    let next = slots.current.get(slotKey(i, to));
    if (next) {
      next.session.rec.log("focus", { target: "question", state: "in" });
      rememberLanguage(tasks[i], to);
    } else {
      setSwitchingLang(true);
      try {
        next = makeSlot(await openSession!(tasks[i], to), tasks[i], to);
        next.stdin = from.stdin;
        slots.current.set(slotKey(i, to), next);
      } catch (err) {
        from.session.rec.log("focus", { target: "question", state: "in" });
        setSwitchError((err as Error).message);
        return;
      } finally {
        setSwitchingLang(false);
      }
    }
    langOf.current.set(i, to);
    v.setState(next.state);
    if (stdin.current) stdin.current.value = next.stdin;
    (window as any).__studentide = { rec: next.session.rec, sessionId: next.session.id }; // for end-to-end tests
    setLangTick((n) => n + 1);
    setVerdict(null);
    setOutcomes((m) => { const { [i]: _, ...rest } = m; return rest; }); // that output was the other language's
    v.focus();
  };

  useEffect(() => {
    const first = makeSlot(session, tasks[start], langOf.current.get(start)!);
    slots.current.set(slotKey(start, first.language), first);
    const v = new EditorView({ state: first.state, parent: host.current! });
    view.current = v;
    const snapTimer = window.setInterval(() => {
      const slot = cur();
      const text = v.state.doc.toString();
      if (text !== slot.lastSnapshot) {
        slot.session.rec.log("snapshot", { reason: "periodic", text });
        slot.lastSnapshot = text;
      }
    }, SNAPSHOT_EVERY_MS);
    // Window focus and tab visibility belong to whichever question is on screen.
    const stopWindow = captureWindow({ log: (...a: Parameters<Recorder["log"]>) => cur().session.rec.log(...a) } as Recorder);

    finishRef.current = (reason: string) => {
      window.clearInterval(snapTimer);
      stopWindow();
      cur().state = v.state;
      for (const slot of slots.current.values()) {
        const text = slot.state.doc.toString();
        slot.session.rec.log("snapshot", { reason: "end", text });
        // In a sitting, a question the student never wrote anything for is left, not handed in.
        const end = reason === "submit" && sitting && text === slot.initial ? "left" : reason;
        slot.session.rec.log("session_end", { wall_clock_ms: Date.now(), reason: end });
      }
    };
    const onHide = () => {
      finishRef.current("pagehide");
      for (const slot of slots.current.values()) slot.session.rec.beacon();
    };
    onHideRef.current = onHide;
    window.addEventListener("pagehide", onHide, { once: true });
    v.focus();

    return () => {
      window.clearInterval(snapTimer);
      stopWindow();
      window.removeEventListener("pagehide", onHide);
      for (const slot of slots.current.values()) slot.session.rec.onStatus = () => {};
      v.destroy();
      view.current = undefined;
    };
    // The sitting is fixed for the lifetime of this screen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const closeDialog = useCallback(() => {
    setConfirming(false);
    view.current?.focus();
  }, []);

  // Competitions: when the clock runs out the editor hands its code in by
  // itself (the server grades what it had at the end, see compete.hand_in).
  const compLab = competing ? task.lab_id : undefined;
  const [clockAt, setClockAt] = useState<{ ends_at: number | null; offset: number }>({ ends_at: task.ends_at ?? null, offset: 0 });
  const [timeUp, setTimeUp] = useState(false);
  useEffect(() => {
    if (!compLab) return;
    let alive = true;
    const poll = () => api<CompClock>(`/api/competitions/${compLab}/clock?student_id=${encodeURIComponent(studentId)}`).then((c) => {
      if (!alive) return;
      setClockAt({ ends_at: c.ends_at, offset: c.now - Date.now() / 1000 });
      if (c.state !== "live") setTimeUp(true);
    }, () => {});
    void poll();
    const t = window.setInterval(poll, CLOCK_POLL_MS);
    return () => { alive = false; window.clearInterval(t); };
  }, [compLab, studentId]);
  useEffect(() => {
    if (!compLab || clockAt.ends_at === null) return;
    const t = window.setInterval(() => {
      if (clockAt.ends_at! - (Date.now() / 1000 + clockAt.offset) <= 0) setTimeUp(true);
    }, 250);
    return () => window.clearInterval(t);
  }, [compLab, clockAt]);
  useEffect(() => {
    if (timeUp) void finishRef2.current("time_up");
  }, [timeUp]);

  /** Questions with code written in this sitting or an earlier one (for the finish dialog). */
  const worked = () => {
    if (view.current) cur().state = view.current.state;
    const touched = new Set([...slots.current.entries()].filter(([, s]) => s.state.doc.toString() !== s.initial).map(([k]) => k.split(":")[0]));
    return touched.size;
  };

  const finishing = useRef(false);
  const finish = async (reason = "submit") => {
    if (finishing.current) return;
    finishing.current = true;
    setSaving(true);
    window.removeEventListener("pagehide", onHideRef.current);
    const n = worked();
    finishRef.current(reason);
    await Promise.all([...slots.current.values()].map((s) => s.session.rec.close()));
    onFinished({ runs: runsRef.current, minutes: (performance.now() - t0.current) / 60_000,
      questions: sitting ? { worked: n, total: tasks.length } : undefined });
  };

  const finishRef2 = useRef(finish);
  finishRef2.current = finish;

  return (
    <div className="grid h-full grid-rows-[52px_1fr] bg-bg">
      {/* Top bar */}
      <header className="flex items-center gap-3 border-b border-border bg-surface px-3">
        <LogoMark className="size-6" />
        <Button variant="ghost" size="icon" onClick={() => setTaskOpen((o) => !o)} aria-label={taskOpen ? "Hide task" : "Show task"}>
          {taskOpen ? <PanelLeftClose className="size-4" /> : <PanelLeftOpen className="size-4" />}
        </Button>
        <div className="flex min-w-0 items-center gap-2 text-sm">
          {task.lab_title && (
            <>
              <span className="hidden truncate text-muted sm:inline">{task.lab_title}</span>
              <span className="hidden text-faint sm:inline">/</span>
            </>
          )}
          <span className="truncate font-semibold text-text">{task.title}</span>
          <span className="text-faint">/</span>
          <span className="font-mono text-xs text-muted">{studentId}</span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <motion.div
            layout
            transition={{ duration: duration.base, ease: ease.out }}
            className={cn(
              "flex h-7 items-center gap-2 rounded-full px-3 text-xs font-medium",
              link.ok ? "bg-success-soft text-success" : "bg-warn-soft text-warn",
            )}
            role="status"
            title="Your typing, edits and runs are being saved"
          >
            <LiveDot tone={link.ok ? "success" : "warn"} />
            {link.ok ? "Recording" : `Offline · ${link.pending} events waiting`}
          </motion.div>
          <WatchNotice v={watching} />
          {compLab && clockAt.ends_at !== null && (
            <span className="flex h-7 items-center rounded-full bg-surface-2 px-3 text-xs" title="When the clock runs out, your code is handed in for you">
              <Countdown comp={{ ends_at: clockAt.ends_at, state: timeUp ? "ended" : "live" }} offset={clockAt.offset} />
            </span>
          )}
          <div className="mx-1 h-5 w-px bg-border" />
          <Button variant="primary" size="sm" onClick={() => void runCode()} disabled={running || saving} className="pr-2">
            {running ? <Spinner className="size-3.5" /> : <Play className="size-3.5 fill-current" />}
            Run
            <Kbd className="ml-1 border-white/30">{isMac ? "⌘" : "Ctrl"} ↵</Kbd>
          </Button>
          {competing && (
            <Button variant="primary" size="sm" onClick={() => void submit()} disabled={submitting || running || saving || timeUp}
              className="bg-gold text-accent-fg hover:bg-gold hover:opacity-90">
              {submitting ? <Spinner className="size-3.5" /> : <FlaskConical className="size-3.5" />}
              Submit
            </Button>
          )}
          {canCheck && (
            <Button size="sm" onClick={() => void checkCode()} disabled={checking || saving}
              title="Run the teacher's tests on your code. Just for you; it isn't graded.">
              {checking ? <Spinner className="size-3.5" /> : <FlaskConical className="size-3.5" />}
              Check
            </Button>
          )}
          <Button size="sm" onClick={() => setConfirming(true)} disabled={saving}>
            {competing ? <Trophy className="size-3.5" /> : <Flag className="size-3.5" />}
            {competing ? "Back to board" : sitting ? "Finish lab" : "Finish"}
          </Button>
        </div>
      </header>

      <div className="flex min-h-0">
        {/* Task panel */}
        <AnimatePresence initial={false}>
          {taskOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 320, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: duration.base, ease: ease.out }}
              className="shrink-0 overflow-hidden border-r border-border bg-surface"
            >
              <div className="h-full w-[320px] overflow-y-auto p-5">
                {sitting && (
                  <nav aria-label="Questions in this lab" className="-mx-2 mb-5 grid gap-0.5 border-b border-border pb-4">
                    {tasks.map((q, i) => (
                      <button key={q.id} onClick={() => void switchTo(i)} disabled={opening !== null || saving}
                        aria-current={i === active ? "true" : undefined}
                        className={cn("flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-[13px] transition-colors disabled:cursor-wait",
                          i === active ? "bg-accent-soft text-text" : "text-muted hover:bg-surface-2 hover:text-text")}>
                        <span className={cn("grid size-6 shrink-0 place-items-center rounded-md font-mono text-[11px] font-semibold",
                          i === active ? "bg-accent text-accent-fg" : q.submitted ? "bg-success-soft text-success" : "bg-surface-2 text-muted")}>
                          {opening === i ? <Spinner className="size-3" /> : q.submitted && i !== active ? <CheckCircle2 className="size-3.5" /> : i + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate font-medium">{q.title}</span>
                        {visited.has(i) && i !== active && <span className="size-1.5 shrink-0 rounded-full bg-accent/60" title="Opened in this sitting" />}
                      </button>
                    ))}
                    {switchError && <p className="mt-1 rounded-md bg-danger-soft px-2 py-1 text-xs text-danger">{switchError}</p>}
                  </nav>
                )}
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">
                  {task.lab_id ? `Question ${active + 1}${sitting ? ` of ${tasks.length}` : ""}` : "Task"}
                </p>
                <h2 className="mt-1.5 text-lg font-semibold tracking-tight text-text">{task.title}</h2>
                <QuestionText prompt={task.prompt} source={task.source} className="mt-3 text-sm leading-relaxed text-muted" />
                {pickLanguage && (
                  <p className="mt-3 text-xs text-faint">
                    Answer in any of {task.languages!.map((l) => LANGUAGES[l].label).join(", ")}: pick it above the editor. Each language keeps its own code.
                  </p>
                )}
                {!sitting && switchError && <p className="mt-2 rounded-md bg-danger-soft px-2 py-1 text-xs text-danger" role="alert">{switchError}</p>}
                {task.tests && task.tests.length > 0 && (
                  <div className="mt-5 grid gap-2">
                    <p className="text-xs font-medium text-text">Examples</p>
                    {task.tests.slice(0, 3).map((t, i) => (
                      <div key={i} className="grid grid-cols-2 gap-2 font-mono text-[11.5px]">
                        <pre className="m-0 overflow-x-auto rounded-lg border border-border bg-surface-2 px-2.5 py-1.5 text-text">{t.stdin || "(no input)"}</pre>
                        <pre className="m-0 overflow-x-auto rounded-lg border border-border bg-surface-2 px-2.5 py-1.5 text-text">{t.expected}</pre>
                      </div>
                    ))}
                    {task.harness && (
                      <p className="text-[11px] leading-relaxed text-faint">
                        Tests call your function with these arguments (as JSON) and compare what it returns.
                      </p>
                    )}
                  </div>
                )}
                {canCheck && (
                  <p className="mt-4 flex items-start gap-1.5 rounded-lg bg-accent-soft px-3 py-2 text-xs text-accent">
                    <FlaskConical className="mt-0.5 size-3.5 shrink-0" />
                    <span>
                      {task.n_tests} test{task.n_tests === 1 ? "" : "s"} to check against
                      {task.n_hidden_tests ? <> (<EyeOff className="inline size-3" /> {task.n_hidden_tests} hidden)</> : null}.
                      Checking is just for you and isn't graded.
                    </span>
                  </p>
                )}
                {task.sample_input && (
                  <div className="mt-5">
                    <p className="mb-1.5 text-xs font-medium text-text">Sample input</p>
                    <pre className="m-0 overflow-x-auto rounded-lg border border-border bg-surface-2 px-3 py-2 font-mono text-xs text-text">{task.sample_input}</pre>
                  </div>
                )}
                {sitting && (
                  <div className="mt-6 flex gap-2">
                    <Button size="sm" className="flex-1" onClick={() => void switchTo(active - 1)} disabled={active === 0 || opening !== null}>
                      <ChevronLeft className="size-3.5" />Previous
                    </Button>
                    <Button size="sm" className="flex-1" onClick={() => void switchTo(active + 1)} disabled={active === tasks.length - 1 || opening !== null}>
                      Next<ChevronRight className="size-3.5" />
                    </Button>
                  </div>
                )}
                <div className="mt-6 border-t border-border pt-5">
                  <p className="mb-2.5 text-xs font-medium text-text">Shortcuts</p>
                  <dl className="grid gap-2 text-xs text-muted">
                    {[
                      ["Run program", `${isMac ? "⌘" : "Ctrl"} ↵`],
                      ["Indent", "Tab"],
                      ["Find", `${isMac ? "⌘" : "Ctrl"} F`],
                      ["Undo", `${isMac ? "⌘" : "Ctrl"} Z`],
                    ].map(([label, key]) => (
                      <div key={label} className="flex items-center justify-between">
                        <dt>{label}</dt>
                        <dd><Kbd className="text-text">{key}</Kbd></dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Editor + console */}
        <div className="grid min-w-0 flex-1 grid-rows-[38px_minmax(0,1fr)_minmax(200px,34%)]">
          <div className="flex items-end gap-1 overflow-x-auto border-b border-border bg-surface-2 px-2" role={sitting ? "tablist" : undefined}>
            {sitting ? tasks.map((q, i) => (
              <button key={q.id} role="tab" aria-selected={i === active} onClick={() => void switchTo(i)}
                disabled={opening !== null || saving} title={q.title}
                className={cn("flex h-[31px] shrink-0 items-center gap-2 rounded-t-lg border border-b-0 px-3 font-mono text-xs transition-colors disabled:cursor-wait",
                  i === active ? "border-border bg-surface text-text" : "border-transparent text-muted hover:text-text")}>
                {opening === i ? <Spinner className="size-3" /> : <span className="size-2 rounded-sm" style={{ background: i === active ? lang.color : "var(--text-faint)" }} />}
                q{i + 1}{lang.file.slice(lang.file.lastIndexOf("."))}
                <span className="max-w-32 truncate font-sans text-faint">{q.title}</span>
              </button>
            )) : (
              <div className="flex h-[31px] items-center gap-2 rounded-t-lg border border-b-0 border-border bg-surface px-3 font-mono text-xs text-text">
                <span className="size-2 rounded-sm" style={{ background: lang.color }} />
                {lang.file}
              </div>
            )}
            {pickLanguage && (
              <label className="relative mb-1 ml-auto flex shrink-0 items-center gap-2 self-center text-xs text-muted"
                title="Answer in any of these languages. Each keeps its own code, so you can switch back. Your submission is graded in the language on screen.">
                {switchingLang ? <Spinner className="size-3" /> : <span>Language</span>}
                <span className="relative">
                  <select value={language} onChange={(e) => void switchLanguage(e.target.value as Language)} disabled={switchingLang || saving || running}
                    aria-label="Language for this question"
                    className="h-7 appearance-none rounded-md border border-border bg-surface pl-2.5 pr-7 text-xs font-medium text-text shadow-sm outline-none hover:border-border-strong focus:border-accent">
                    {task.languages!.map((l) => <option key={l} value={l}>{LANGUAGES[l].label}</option>)}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-2 top-1/2 size-3.5 -translate-y-1/2 text-faint" />
                </span>
              </label>
            )}
          </div>
          <div ref={host} className="editor min-h-0 overflow-hidden bg-surface" />

          <section className="grid min-h-0 grid-cols-[minmax(180px,1fr)_2fr] border-t border-border bg-surface-2">
            <div className="flex min-h-0 flex-col border-r border-border">
              <PaneHeader icon={<Terminal className="size-3.5" />} label="Input" />
              <div className="min-h-0 flex-1 p-3 pt-0">
                <TextArea
                  ref={stdin}
                  defaultValue={task.sample_input}
                  spellCheck={false}
                  className="h-full resize-none font-mono text-[13px] leading-relaxed"
                  aria-label="Program input"
                />
              </div>
            </div>

            <div className="flex min-h-0 flex-col">
              <PaneHeader icon={<Play className="size-3.5" />} label="Output"
                tabs={canCheck ? { value: pane, onChange: setPane, tests: grade ? `${grade.passed}/${grade.total}` : "" } : undefined}>
                <AnimatePresence mode="wait" initial={false}>
                  <motion.span
                    key={running ? "running" : outcome ? `done-${runs}` : "idle"}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: duration.fast }}
                  >
                    {running ? (
                      <Badge tone="accent"><Spinner className="size-3" />Running</Badge>
                    ) : outcome ? (
                      outcome.failed ? (
                        <Badge tone="danger"><CircleAlert className="size-3" />{outcome.errorType ?? "Error"}{outcome.durationMs !== null && ` · ${Math.round(outcome.durationMs)} ms`}</Badge>
                      ) : (
                        <Badge tone="success"><CheckCircle2 className="size-3" />Exit {outcome.exitCode ?? 0} · {Math.round(outcome.durationMs ?? 0)} ms</Badge>
                      )
                    ) : (
                      <span className="text-xs text-faint">Not run yet</span>
                    )}
                  </motion.span>
                </AnimatePresence>
              </PaneHeader>
              <div className="relative min-h-0 flex-1 p-3 pt-0">
                <div className="relative h-full overflow-hidden rounded-lg bg-console shadow-inner">
                  {running && (
                    <div className="absolute inset-x-0 top-0 h-0.5 overflow-hidden">
                      <div className="h-full w-1/2 bg-accent animate-indeterminate" />
                    </div>
                  )}
                  {pane === "tests" && (
                    <div className="absolute inset-0 z-10 overflow-auto bg-console px-4 py-3">
                      {checking ? <p className="text-[13px] text-console-text/60">Checking…</p>
                        : grade ? <GradeView grade={grade} dark />
                        : <p className="text-[13px] text-console-text/50">Press Check to run the tests.</p>}
                    </div>
                  )}
                  <motion.pre
                    key={running ? "running" : runs}
                    initial={{ opacity: 0.4 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: duration.base }}
                    className={cn(
                      "output m-0 h-full overflow-auto whitespace-pre-wrap px-4 py-3 font-mono text-[13px] leading-relaxed",
                      running ? "text-console-text/60" : outcome?.failed ? "failed text-console-danger" : "text-console-text",
                    )}
                  >
                    {running ? "Running…" : outcome?.text ?? ""}
                  </motion.pre>
                  {!running && !outcome && (
                    <div className="pointer-events-none absolute inset-0 grid place-items-center text-center text-xs text-console-text/40">
                      <span>Press <Kbd className="mx-0.5">{isMac ? "⌘" : "Ctrl"} ↵</Kbd> to run your program</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>

      <Dialog
        open={confirming}
        onClose={saving ? () => {} : closeDialog}
        icon={<Flag className="size-4" />}
        title={competing ? "Leave this question?" : sitting ? "Finish this lab?" : "Finish this session?"}
        description={competing
          ? "Your best submission keeps its points. You can open the question again from the board while the clock runs."
          : sitting
            ? `You have written code for ${confirming ? worked() : 0} of ${tasks.length} questions. Everything is saved; while the lab is open you can come back and carry on where you left off.`
            : "You will not be able to edit it afterwards. Your code and activity have been saved as you worked."}
        actions={
          <>
            <Button onClick={closeDialog} disabled={saving}>Keep working</Button>
            <Button variant="primary" onClick={() => void finish()} disabled={saving} data-autofocus>
              {saving && <Spinner className="size-3.5" />}
              {competing ? "Back to board" : sitting ? "Finish lab" : "Finish session"}
            </Button>
          </>
        }
      />
      {competing && (
        <SubmitDialog verdict={verdict} onClose={() => { setVerdict(null); view.current?.focus(); }}
          onLeave={() => { setVerdict(null); setConfirming(true); }} />
      )}
    </div>
  );
}

interface Viewers { class_view: boolean; editor: { name: string }[] }

const VIEWERS_MS = 5000;

/** Who is watching live, polled every 5 s (the poll also tells the class view this IDE is still open). */
function useViewers(sessionId: string): Viewers {
  const [v, setV] = useState<Viewers>({ class_view: false, editor: [] });
  useEffect(() => {
    let alive = true;
    const poll = () => fetch(`/api/sessions/${sessionId}/viewers`).then((r) => (r.ok ? r.json() : null))
      .then((next: Viewers | null) => { if (alive && next) setV(next); }, () => {});
    void poll();
    const t = window.setInterval(poll, VIEWERS_MS);
    return () => { alive = false; window.clearInterval(t); };
  }, [sessionId]);
  return v;
}

/** Live viewing is never silent: a teacher on your editor gets a named banner, the class view a small pill. */
function WatchNotice({ v }: { v: Viewers }) {
  const names = v.editor.map((e) => e.name);
  return (
    <AnimatePresence mode="wait" initial={false}>
      {names.length > 0 ? (
        <motion.div key="editor" role="status" aria-live="polite"
          initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}
          transition={{ duration: duration.base, ease: ease.out }}
          title="Your teacher is looking at a read-only copy of your code right now. They cannot type in your editor."
          className="flex h-7 items-center gap-1.5 rounded-full bg-warn-soft px-3 text-xs font-medium text-warn">
          <Eye className="size-3.5" />
          <span className="max-w-56 truncate">{names.join(", ")} {names.length === 1 ? "is" : "are"} viewing your editor</span>
        </motion.div>
      ) : v.class_view ? (
        <motion.div key="class" role="status" aria-live="polite"
          initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}
          transition={{ duration: duration.base, ease: ease.out }}
          title="Your teacher has this lab's live class view open: they can see who is working, on which question, and your runs and checks. Not your code."
          className="flex h-7 items-center gap-1.5 rounded-full bg-surface-2 px-3 text-xs font-medium text-muted">
          <Eye className="size-3.5" /> Class view on
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function PaneHeader({ icon, label, children, tabs }: {
  icon: React.ReactNode; label: string; children?: React.ReactNode;
  tabs?: { value: "output" | "tests"; onChange: (v: "output" | "tests") => void; tests: string };
}) {
  return (
    <div className="flex h-10 shrink-0 items-center justify-between px-3">
      {tabs ? (
        <span className="flex items-center gap-1" role="tablist">
          {(["output", "tests"] as const).map((t) => (
            <button key={t} role="tab" aria-selected={tabs.value === t} onClick={() => tabs.onChange(t)}
              className={cn("flex h-7 items-center gap-1.5 rounded-md px-2 text-xs font-medium transition-colors",
                tabs.value === t ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text")}>
              {t === "output" ? <>{icon}{label}</> : <><FlaskConical className="size-3.5" />Tests{tabs.tests && <span className="tabular-nums text-faint">{tabs.tests}</span>}</>}
            </button>
          ))}
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted">{icon}{label}</span>
      )}
      {children}
    </div>
  );
}
