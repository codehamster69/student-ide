// #/sandbox/previews/<id>: "Try as a student" in a cloud preview instance.
// Assignment tabs, statement, file tree + editor, a real terminal, Run and Check
// (every test, hidden ones too). Not study data: only teachers open previews.
import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { ArrowLeft, Check, CircleStop, FileText, FlaskConical, Play, RefreshCw, Timer, X } from "lucide-react";
import { Badge, Button, Card, Spinner, TextArea, cn } from "../ui";
import { get, send, token } from "../review/api";
import { LessonText } from "../learn/LessonText";
import { href } from "../routes";
import { FileEditor, NetworkBadge, PreviewTerminal } from "./bits";
import type { CheckResult, Preview, RunResult } from "./api";

export function SandboxPreview({ id, onAuthLost }: { id: string; onAuthLost: () => void }) {
  const [p, setP] = useState<Preview | null>(null);
  const [error, setError] = useState("");
  const [asg, setAsg] = useState<string>("");

  const load = useCallback(() => get<Preview>(`/api/sandbox/previews/${id}`).then((x) => {
    setP(x);
    setAsg((cur) => cur || x.lab?.assignments[0]?.id || "");
  }, (e) => (e.message?.includes("sign") ? onAuthLost() : setError(e.message))), [id, onAuthLost]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {  // poll while starting, then now and then so the countdown and stop reason stay true
    const t = setInterval(load, p?.status === "starting" ? 1500 : 30_000);
    return () => clearInterval(t);
  }, [load, p?.status]);

  if (error) return <div className="mx-auto max-w-[1100px] px-5 pt-8"><Card className="p-6 text-sm text-danger">{error}</Card></div>;
  if (!p) return <div className="grid place-items-center pt-24"><Spinner /></div>;
  const lab = p.lab;
  const a = lab?.assignments.find((x) => x.id === asg);

  return (
    <div className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-[1600px] flex-col gap-3 px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <a href={href.sbxLab(p.lab_id)} className="inline-flex items-center gap-1 text-[13px] text-muted hover:text-text"><ArrowLeft className="size-3.5" /> Back to the lab</a>
        <h1 className="text-base font-semibold text-text">{p.lab_title}</h1>
        <Badge tone="accent">Preview as a student</Badge>
        {lab && <NetworkBadge network={lab.network === "open" ? "registries" : lab.network} />}
        <span className="flex-1" />
        {p.status === "running" && <Countdown endsAt={p.ends_at} />}
        {(p.status === "running" || p.status === "starting") && (
          <Button size="sm" onClick={async () => { await send("POST", `/api/sandbox/previews/${id}/stop`); void load(); }}><CircleStop className="size-3.5" /> Stop</Button>
        )}
      </div>

      {p.status === "starting" && (
        <Card className="grid flex-1 place-items-center p-10 text-center">
          <div className="grid justify-items-center gap-3">
            <Spinner className="size-6 text-accent" />
            <p className="text-sm text-text">Starting a fresh instance of {lab?.environment?.title ?? "the environment"}…</p>
            <p className="text-xs text-muted">The first start of a new environment can take a few minutes while its image is fetched.</p>
          </div>
        </Card>
      )}
      {(p.status === "stopped" || p.status === "failed") && (
        <Card className="grid flex-1 place-items-center p-10 text-center">
          <div className="grid justify-items-center gap-3">
            <p className="text-sm text-text">{p.status === "failed" ? `The preview could not start: ${p.error}` : `This preview stopped (${p.stop_reason ?? "stopped"}).`}</p>
            <p className="text-xs text-muted">Previews stop after {p.seats?.idle_minutes ?? 15} idle minutes and at {p.seats?.max_minutes ?? 60} minutes; files are not kept.</p>
            <Button variant="primary" onClick={async () => {
              const n = await send<Preview>("POST", "/api/sandbox/previews", { lab_id: p.lab_id });
              location.hash = href.sbxPreview(n.id);
            }}><RefreshCw className="size-4" /> Start a new one</Button>
          </div>
        </Card>
      )}

      {p.status === "running" && lab && a && (
        <>
          <div className="flex gap-1 overflow-x-auto">
            {lab.assignments.map((x, i) => (
              <button key={x.id} onClick={() => setAsg(x.id)} className={cn("relative shrink-0 rounded-lg px-3 py-1.5 text-[13px] font-medium",
                x.id === asg ? "text-text" : "text-muted hover:text-text")}>
                {x.id === asg && <motion.span layoutId="asg-tab" className="absolute inset-0 rounded-lg bg-surface-3" />}
                <span className="relative">{i + 1}. {x.title}</span>
              </button>
            ))}
          </div>
          {/* every assignment's workspace stays mounted, so its terminal and editor survive switching */}
          {lab.assignments.map((x) => (
            <div key={x.id} className={cn("min-h-0 flex-1", x.id === asg ? "grid" : "hidden")}>
              <Workspace previewId={id} assignment={x} onTouched={load} />
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function Countdown({ endsAt }: { endsAt: number }) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => { const t = setInterval(() => setNow(Date.now() / 1000), 1000); return () => clearInterval(t); }, []);
  const left = Math.max(0, endsAt - now);
  return <span className={cn("flex items-center gap-1 font-mono text-xs", left < 120 ? "text-warn" : "text-muted")}><Timer className="size-3.5" />{Math.floor(left / 60)}:{String(Math.floor(left % 60)).padStart(2, "0")}</span>;
}

type A = NonNullable<Preview["lab"]>["assignments"][number];

function Workspace({ previewId, assignment: a, onTouched }: { previewId: string; assignment: A; onTouched: () => void }) {
  const base = `/api/sandbox/previews/${previewId}`;
  const q = `assignment_id=${encodeURIComponent(a.id)}`;
  const [files, setFiles] = useState<{ path: string; size: number }[]>([]);
  const [cur, setCur] = useState(a.open[0] ?? a.files[0]?.path ?? "");
  const [content, setContent] = useState<string | null>(null);
  const [saved, setSaved] = useState(true);
  const [stdin, setStdin] = useState(a.tests.cases?.find((c) => !c.hidden)?.stdin ?? "");
  const [out, setOut] = useState<RunResult | null>(null);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [busy, setBusy] = useState<"" | "run" | "check">("");
  const [panel, setPanel] = useState<"statement" | "output">("statement");
  const timer = useRef<number>(0);
  const pending = useRef<string | null>(null);

  const refresh = useCallback(() => get<{ files: { path: string; size: number }[] }>(`${base}/files?${q}`).then((r) => setFiles(r.files), () => {}), [base, q]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!cur) return;
    setContent(null);
    get<{ content: string }>(`${base}/files?${q}&path=${encodeURIComponent(cur)}`).then((r) => setContent(r.content), () => setContent(""));
  }, [base, q, cur]);

  const flush = async () => {
    window.clearTimeout(timer.current);
    if (pending.current === null) return;
    const body = { path: cur, content: pending.current };
    pending.current = null;
    await send("PUT", `${base}/files?${q}`, body);
    setSaved(true);
  };
  const edit = (v: string) => {
    pending.current = v;
    setSaved(false);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => void flush(), 800);
  };
  const act = async (kind: "run" | "check") => {
    setBusy(kind);
    try {
      await flush();
      if (kind === "run") { setOut(await send<RunResult>("POST", `${base}/run`, { assignment_id: a.id, stdin })); setCheck(null); }
      else { setCheck(await send<CheckResult>("POST", `${base}/check`, { assignment_id: a.id })); setOut(null); }
      setPanel("output");
      onTouched();
    } catch (e) { setOut({ stdout: "", stderr: (e as Error).message, exit_code: -1, timed_out: false, duration_ms: 0 }); setPanel("output"); }
    finally { setBusy(""); }
  };
  const wsUrl = `${location.origin}${base}/terminal?${q}${token.get() ? `&token=${encodeURIComponent(token.get())}` : ""}`;

  return (
    <div className="grid min-h-0 gap-3 lg:grid-cols-[minmax(260px,1fr)_2fr]">
      <Card className="flex min-h-0 flex-col overflow-hidden">
        <div className="flex gap-1 border-b border-border p-1.5 text-[13px]">
          {(["statement", "output"] as const).map((t) => (
            <button key={t} onClick={() => setPanel(t)} className={cn("rounded-md px-2.5 py-1 font-medium capitalize", panel === t ? "bg-surface-3 text-text" : "text-muted")}>{t}</button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {panel === "statement" ? <LessonText markdown={a.statement || "*No statement.*"} language="" /> : (
            <div className="grid gap-3">
              {out && (
                <div className="grid gap-1">
                  <p className="text-xs text-muted">exit {out.exit_code}{out.timed_out ? " · timed out" : ""} · {out.duration_ms} ms</p>
                  <pre className="max-h-80 overflow-auto rounded-lg bg-console p-2 font-mono text-xs text-console-text">{out.stdout}{out.stderr && <span className="text-console-danger">{out.stderr}</span>}</pre>
                </div>
              )}
              {check && (
                <div className="grid gap-1.5">
                  <p className="text-sm font-medium text-text">{check.passed} of {check.total} tests pass</p>
                  {check.results.map((r, i) => (
                    <motion.div key={i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                      className={cn("rounded-lg border p-2 text-xs", r.passed ? "border-success/40 bg-success-soft" : "border-danger/40 bg-danger-soft")}>
                      <p className="flex items-center gap-1 font-medium text-text">{r.passed ? <Check className="size-3.5 text-success" /> : <X className="size-3.5 text-danger" />}{r.name}{r.hidden && <Badge className="ml-1">hidden</Badge>}</p>
                      {!r.passed && r.expected !== undefined && <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-muted">expected {JSON.stringify(r.expected)}{"\n"}got      {JSON.stringify(r.got)}</pre>}
                      {!r.passed && r.stderr && <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] text-danger">{r.stderr.slice(-400)}</pre>}
                    </motion.div>
                  ))}
                </div>
              )}
              {!out && !check && <p className="text-sm text-muted">Run or Check to see output here.</p>}
            </div>
          )}
        </div>
        <div className="grid gap-2 border-t border-border p-2">
          <TextArea rows={2} value={stdin} onChange={(e) => setStdin(e.target.value)} placeholder="Input for Run" className="font-mono text-xs" />
          <div className="flex gap-2">
            <Button size="sm" variant="primary" disabled={!!busy || !a.run} onClick={() => act("run")} title={a.run || "no Run command"}>{busy === "run" ? <Spinner /> : <Play className="size-3.5" />} Run</Button>
            <Button size="sm" disabled={!!busy} onClick={() => act("check")}>{busy === "check" ? <Spinner /> : <FlaskConical className="size-3.5" />} Check</Button>
            <span className="self-center truncate font-mono text-[11px] text-faint">{a.run}</span>
          </div>
        </div>
      </Card>

      <div className="grid min-h-0 grid-rows-[3fr_2fr] gap-3">
        <Card className="grid min-h-0 grid-cols-[160px_1fr] overflow-hidden">
          <div className="min-h-0 overflow-y-auto border-r border-border bg-surface-2 p-1.5">
            <div className="mb-1 flex items-center justify-between px-1.5 text-[11px] font-semibold uppercase tracking-wide text-faint">Files
              <button onClick={() => void refresh()} aria-label="Refresh files"><RefreshCw className="size-3" /></button></div>
            {files.map((f) => (
              <button key={f.path} onClick={async () => { await flush(); setCur(f.path); }}
                className={cn("flex w-full items-center gap-1.5 truncate rounded-md px-1.5 py-1 text-left font-mono text-xs", f.path === cur ? "bg-surface text-text shadow-sm" : "text-muted hover:text-text")}>
                <FileText className="size-3 shrink-0" />{f.path}
              </button>
            ))}
          </div>
          <div className="relative min-h-0">
            {content === null ? <div className="grid h-full place-items-center"><Spinner /></div> : <FileEditor key={cur} path={cur} value={content} onChange={edit} />}
            <span className="absolute right-2 top-1 text-[11px] text-faint">{saved ? "saved" : "saving…"}</span>
          </div>
        </Card>
        <PreviewTerminal url={wsUrl} onClosed={() => void refresh()} />
      </div>
    </div>
  );
}
