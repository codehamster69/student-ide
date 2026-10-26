import { useCallback, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { basicSetup } from "codemirror";
import { python } from "@codemirror/lang-python";
import { EditorView, keymap } from "@codemirror/view";
import { Prec } from "@codemirror/state";
import { indentUnit } from "@codemirror/language";
import { indentWithTab } from "@codemirror/commands";
import { CheckCircle2, CircleAlert, Flag, PanelLeftClose, PanelLeftOpen, Play, Terminal } from "lucide-react";
import { api, type RunResult, type Task } from "../api";
import { captureExtension, captureWindow, SNAPSHOT_EVERY_MS } from "../capture";
import type { LiveSession } from "../editor/session";
import { editorTheme } from "../editor/theme";
import { Badge, Button, Dialog, Kbd, LiveDot, LogoMark, Spinner, TextArea, cn, duration, ease } from "../ui";

export interface SessionSummary {
  runs: number;
  minutes: number;
}

interface Outcome {
  text: string;
  failed: boolean;
  exitCode: number | null;
  durationMs: number | null;
  errorType: string | null;
}

const isMac = /Mac|iPhone|iPad/.test(navigator.platform);

/**
 * The editor screen. CodeMirror lives outside React state: it is created once
 * in an effect and never re-rendered, so typing triggers no React work at all.
 * Recording (captureExtension) is attached exactly as before the redesign.
 */
export function Workspace({ studentId, task, session, onFinished }: {
  studentId: string;
  task: Task;
  session: LiveSession;
  onFinished: (summary: SessionSummary) => void;
}) {
  const { rec, id: sessionId } = session;
  const host = useRef<HTMLDivElement>(null);
  const stdin = useRef<HTMLTextAreaElement>(null);
  const view = useRef<EditorView>();
  const finishRef = useRef<(reason: string) => void>(() => {});
  const onHideRef = useRef<() => void>(() => {});
  const lastSnapshot = useRef(task.starter_code);
  const runsRef = useRef(0);

  const [running, setRunning] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [runs, setRuns] = useState(0);
  const [link, setLink] = useState({ pending: 0, ok: true });
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [taskOpen, setTaskOpen] = useState(true);

  const runningRef = useRef(false);
  const runCode = useCallback(async () => {
    const v = view.current;
    if (runningRef.current || !v) return;
    runningRef.current = true;
    // Commit "Running…" synchronously so the output never shows a stale result.
    flushSync(() => setRunning(true));
    const code = v.state.doc.toString();
    rec.log("snapshot", { reason: "run", text: code });
    lastSnapshot.current = code;
    try {
      const r = await api<RunResult>(`/api/sessions/${sessionId}/run`, { code, stdin: stdin.current?.value ?? "" });
      rec.log("run", {
        run_id: r.run_id, code_sha256: r.code_sha256, exit_code: r.exit_code,
        duration_ms: r.duration_ms, error_type: r.error_type,
      });
      setOutcome({
        text: r.stdout + (r.stderr ? (r.stdout ? "\n" : "") + r.stderr : "") || "(no output)",
        failed: r.error_type !== null,
        exitCode: r.exit_code,
        durationMs: r.duration_ms,
        errorType: r.error_type,
      });
    } catch (err) {
      setOutcome({ text: `Could not run: ${(err as Error).message}`, failed: true, exitCode: null, durationMs: null, errorType: "network" });
    } finally {
      runsRef.current += 1;
      setRuns(runsRef.current);
      runningRef.current = false;
      setRunning(false);
    }
  }, [rec, sessionId]);

  const runRef = useRef(runCode);
  runRef.current = runCode;

  useEffect(() => {
    rec.onStatus = (pending, ok) => setLink({ pending, ok });

    const v = new EditorView({
      doc: task.starter_code,
      parent: host.current!,
      extensions: [
        basicSetup,
        python(),
        indentUnit.of("    "),
        keymap.of([indentWithTab]),
        editorTheme,
        captureExtension(rec),
        Prec.highest(keymap.of([{ key: "Mod-Enter", run: () => (void runRef.current(), true) }])),
      ],
    });
    view.current = v;
    rec.log("snapshot", { reason: "start", text: v.state.doc.toString() });
    const snapTimer = window.setInterval(() => {
      const text = v.state.doc.toString();
      if (text !== lastSnapshot.current) {
        rec.log("snapshot", { reason: "periodic", text });
        lastSnapshot.current = text;
      }
    }, SNAPSHOT_EVERY_MS);
    const stopWindow = captureWindow(rec);

    finishRef.current = (reason: string) => {
      window.clearInterval(snapTimer);
      stopWindow();
      rec.log("snapshot", { reason: "end", text: v.state.doc.toString() });
      rec.log("session_end", { wall_clock_ms: Date.now(), reason });
    };
    const onHide = () => { finishRef.current("pagehide"); rec.beacon(); };
    onHideRef.current = onHide;
    window.addEventListener("pagehide", onHide, { once: true });
    v.focus();

    return () => {
      window.clearInterval(snapTimer);
      stopWindow();
      window.removeEventListener("pagehide", onHide);
      rec.onStatus = () => {};
      v.destroy();
      view.current = undefined;
    };
    // The session and task are fixed for the lifetime of this screen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const closeDialog = useCallback(() => {
    setConfirming(false);
    view.current?.focus();
  }, []);

  const finish = async () => {
    setSaving(true);
    window.removeEventListener("pagehide", onHideRef.current);
    finishRef.current("submit");
    await rec.close();
    onFinished({ runs: runsRef.current, minutes: (performance.now() - rec.t0) / 60_000 });
  };

  return (
    <div className="grid h-full grid-rows-[52px_1fr] bg-bg">
      {/* Top bar */}
      <header className="flex items-center gap-3 border-b border-border bg-surface px-3">
        <LogoMark className="size-6" />
        <Button variant="ghost" size="icon" onClick={() => setTaskOpen((o) => !o)} aria-label={taskOpen ? "Hide task" : "Show task"}>
          {taskOpen ? <PanelLeftClose className="size-4" /> : <PanelLeftOpen className="size-4" />}
        </Button>
        <div className="flex min-w-0 items-center gap-2 text-sm">
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
          <div className="mx-1 h-5 w-px bg-border" />
          <Button variant="primary" size="sm" onClick={() => void runCode()} disabled={running || saving} className="pr-2">
            {running ? <Spinner className="size-3.5" /> : <Play className="size-3.5 fill-current" />}
            Run
            <Kbd className="ml-1 border-white/30">{isMac ? "⌘" : "Ctrl"} ↵</Kbd>
          </Button>
          <Button size="sm" onClick={() => setConfirming(true)} disabled={saving}>
            <Flag className="size-3.5" />
            Finish
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
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">Task</p>
                <h2 className="mt-1.5 text-lg font-semibold tracking-tight text-text">{task.title}</h2>
                <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-muted">{task.prompt}</p>
                {task.sample_input && (
                  <div className="mt-5">
                    <p className="mb-1.5 text-xs font-medium text-text">Sample input</p>
                    <pre className="m-0 overflow-x-auto rounded-lg border border-border bg-surface-2 px-3 py-2 font-mono text-xs text-text">{task.sample_input}</pre>
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
          <div className="flex items-end gap-1 border-b border-border bg-surface-2 px-2">
            <div className="flex h-[31px] items-center gap-2 rounded-t-lg border border-b-0 border-border bg-surface px-3 font-mono text-xs text-text">
              <span className="size-2 rounded-sm bg-[#3776ab]" />
              main.py
            </div>
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
              <PaneHeader icon={<Play className="size-3.5" />} label="Output">
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
        title="Finish this session?"
        description="You will not be able to edit it afterwards. Your code and activity have been saved as you worked."
        actions={
          <>
            <Button onClick={closeDialog} disabled={saving}>Keep working</Button>
            <Button variant="primary" onClick={() => void finish()} disabled={saving} data-autofocus>
              {saving && <Spinner className="size-3.5" />}
              Finish session
            </Button>
          </>
        }
      />
    </div>
  );
}

function PaneHeader({ icon, label, children }: { icon: React.ReactNode; label: string; children?: React.ReactNode }) {
  return (
    <div className="flex h-10 shrink-0 items-center justify-between px-3">
      <span className="flex items-center gap-1.5 text-xs font-medium text-muted">{icon}{label}</span>
      {children}
    </div>
  );
}
