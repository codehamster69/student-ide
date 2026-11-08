import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { Activity, ArrowLeft, CheckCircle2, CircleAlert, Eye, FlaskConical, Play, Terminal } from "lucide-react";
import { Badge, Card, LiveDot, cn, item, stagger } from "../ui";
import { AuthError, get, token } from "../review/api";
import { Skeleton } from "../review/bits";
import { CodeReplay } from "../review/CodeReplay";
import { LANGUAGES } from "../teach/api";
import { STATE, ago, leaveView, type LiveEditor as LiveEditorData } from "./api";
import { ActivityBars } from "./LiveClass";
import { QuestionText } from "../questionText";
import { href } from "../routes";

const POLL_MS = 2000;
const MARK_MS = 10_000;

/** Lines (1-based, in `next`) that differ from `prev`: the block between the common head and tail. */
function changedLines(prev: string, next: string): number[] {
  const a = prev.split("\n"), b = next.split("\n");
  let head = 0;
  while (head < a.length && head < b.length && a[head] === b[head]) head++;
  let tail = 0;
  while (tail < a.length - head && tail < b.length - head && a[a.length - 1 - tail] === b[b.length - 1 - tail]) tail++;
  const out: number[] = [];
  for (let i = head; i < b.length - tail; i++) out.push(i + 1);
  return out;
}

/**
 * #/live/s/<session id>: a read-only, live copy of one student's editor. The
 * student sees a banner with the teacher's name for as long as this is open.
 */
export function LiveEditor({ id, onAuthLost }: { id: string; onAuthLost: () => void }) {
  const [d, setD] = useState<LiveEditorData | null>(null);
  const [error, setError] = useState("");
  const [changed, setChanged] = useState<number[]>([]);
  const prev = useRef<string | null>(null);
  const lastChange = useRef(0);

  const load = useCallback(() => get<LiveEditorData>(`/api/live/sessions/${id}`).then((next) => {
    if (prev.current !== null && prev.current !== next.text) {
      setChanged(changedLines(prev.current, next.text));
      lastChange.current = Date.now();
    } else if (Date.now() - lastChange.current > MARK_MS) {
      setChanged((c) => (c.length ? [] : c));
    }
    prev.current = next.text;
    setD(next);
  }, (e) => (e instanceof AuthError ? onAuthLost() : setError(e.message))), [id, onAuthLost]);

  useEffect(() => {
    void load();
    const t = window.setInterval(() => void load(), POLL_MS);
    const tok = token.get();
    return () => { window.clearInterval(t); leaveView({ session_id: id }, tok); };
  }, [load, id]);

  if (!d) {
    return (
      <div className="mx-auto max-w-[1440px] px-5 pt-8">
        {error ? <Card className="p-6 text-sm text-danger">{error}</Card> : <Skeleton className="h-[70vh] w-full rounded-2xl" />}
      </div>
    );
  }

  const s = d.session;
  const st = STATE[d.state];
  const lang = LANGUAGES[s.language] ?? LANGUAGES.python;
  return (
    <motion.div variants={stagger(0.05)} initial="initial" animate="animate" className="mx-auto max-w-[1440px] px-5 pb-12 pt-6">
      <motion.a variants={item} href={s.lab_id ? href.liveLab(s.lab_id) : href.live}
        className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted hover:text-text">
        <ArrowLeft className="size-4" /> {s.lab_title ?? "Live"}
      </motion.a>

      <motion.div variants={item} className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-text">
            <span className="font-mono">{s.student_id}</span>
            <span className="text-faint">/</span>
            <span className="truncate">{s.question_title}</span>
          </h1>
          <p className="mt-0.5 text-sm text-muted">Started {ago(d.now, s.started_at)} · last edit {ago(d.now, d.last_edit_at)}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={st.tone}><LiveDot tone={st.tone} live={st.live} />{st.label}</Badge>
          <a href={href.session(s.id)} className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-surface px-3 text-xs font-medium text-text shadow-sm hover:bg-surface-2">
            <Activity className="size-3.5" /> Timeline
          </a>
        </div>
      </motion.div>

      <motion.div variants={item} className="mb-4 flex items-center gap-2 rounded-xl bg-warn-soft px-4 py-2.5 text-[13px] text-text" role="status">
        <Eye className="size-4 shrink-0 text-warn" />
        <p><span className="font-mono">{s.student_id}</span> can see that you are viewing their editor{d.terminal ? " and terminal" : ""}. This view is read-only and is logged.</p>
      </motion.div>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
        <motion.div variants={item} className="overflow-hidden rounded-2xl border border-border bg-surface shadow-sm">
          <div className="flex h-10 items-center justify-between gap-2 border-b border-border bg-surface-2 px-3">
            <span className="flex items-center gap-2 font-mono text-xs text-text">
              <span className="size-2 rounded-sm" style={{ background: lang.color }} />{d.path ? d.path.split("/").pop() : lang.file}
              {d.files && d.files.length > 1 && <span className="font-sans text-faint">· {d.files.length} files, showing the one edited last</span>}
            </span>
            <span className="flex items-center gap-1.5 text-[11px] text-faint">
              <LiveDot tone={d.state === "typing" ? "success" : "neutral"} live={d.state === "typing"} /> updates every 2 s
            </span>
          </div>
          <div className="h-[64vh] min-h-[360px]">
            <CodeReplay doc={d.text} changed={changed} caret={d.caret ?? d.text.length} language={s.language} showCaret={!s.ended_at} />
          </div>
        </motion.div>

        <motion.aside variants={item} className="grid gap-4">
          {d.terminal && <TerminalMirror term={d.terminal} />}
          <Card className="p-4">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">Activity, last 10 minutes</p>
            <ActivityBars bins={d.activity} className="h-10" />
            {d.tab_away && <p className="mt-2 text-xs text-warn">The editor tab is in the background right now.</p>}
          </Card>

          {d.check && (
            <Card className="flex items-center gap-3 p-4">
              <FlaskConical className="size-4 text-accent" />
              <p className="text-sm text-text">
                Last check <span className="font-semibold tabular-nums">{d.check.passed}/{d.check.total}</span> tests
                <span className="text-muted"> · best {d.check.best} · {ago(d.now, d.check.created_at)}</span>
              </p>
            </Card>
          )}

          <Card className="overflow-hidden">
            <p className="flex items-center gap-1.5 border-b border-border px-4 py-2.5 text-xs font-medium text-muted">
              <Terminal className="size-3.5" /> Recent runs <span className="tabular-nums text-faint">{d.runs.length}</span>
            </p>
            {d.runs.length === 0 ? (
              <p className="px-4 py-6 text-center text-xs text-faint">No runs yet.</p>
            ) : (
              <ol className="grid max-h-[42vh] gap-px overflow-auto bg-border">
                {d.runs.map((r, i) => (
                  <li key={r.created_at} className="bg-surface px-4 py-3">
                    <p className="mb-1.5 flex items-center gap-2 text-xs">
                      <Play className="size-3 text-faint" />
                      {r.error_type
                        ? <span className="inline-flex items-center gap-1 font-medium text-danger"><CircleAlert className="size-3" />{r.error_type}</span>
                        : <span className="inline-flex items-center gap-1 font-medium text-success"><CheckCircle2 className="size-3" />Exit {r.exit_code ?? 0}</span>}
                      <span className="ml-auto text-faint">{ago(d.now, r.created_at)}</span>
                    </p>
                    <pre className={cn("m-0 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-console px-3 py-2 font-mono text-[11.5px] leading-relaxed",
                      r.error_type ? "text-console-danger" : "text-console-text", i > 0 && "max-h-24 opacity-80")}>
                      {(r.stdout + (r.stderr ? (r.stdout ? "\n" : "") + r.stderr : "")) || "(no output)"}
                    </pre>
                  </li>
                ))}
              </ol>
            )}
          </Card>

          {(s.prompt || s.source?.live_prompt) && (
            <Card className="p-4">
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">Question</p>
              <QuestionText prompt={s.prompt} source={s.source} className="max-h-48 overflow-auto text-[13px] leading-relaxed text-muted" />
            </Card>
          )}
        </motion.aside>
      </div>
    </motion.div>
  );
}

/** Sandbox Labs: the student's terminal as a read-only transcript (commands and the tail of their output;
 * the full scrollback stays on the student's machine), newest at the bottom, with what is running now. */
function TerminalMirror({ term }: { term: NonNullable<LiveEditorData["terminal"]> }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [term.commands.length, term.running?.command]);
  return (
    <Card className="overflow-hidden">
      <p className="flex items-center gap-1.5 border-b border-border px-4 py-2.5 text-xs font-medium text-muted">
        <Terminal className="size-3.5" /> Terminal <span className="text-faint">read-only</span>
        {term.running && <span className="ml-auto inline-flex items-center gap-1.5 text-success"><LiveDot tone="success" /> running</span>}
      </p>
      <div className="max-h-[38vh] overflow-auto bg-console px-3 py-2 font-mono text-[11.5px] leading-relaxed text-console-text">
        {term.commands.length === 0 && !term.running && <p className="opacity-60">No commands yet.</p>}
        {term.commands.map((c, i) => (
          <div key={i} className="mb-1.5">
            <p><span className="opacity-60">$ </span>{c.command}{c.exit_code ? <span className="text-console-danger"> · exit {c.exit_code}</span> : null}</p>
            {c.output && <pre className="m-0 whitespace-pre-wrap opacity-80">{c.output.split("\n").slice(-6).join("\n")}</pre>}
          </div>
        ))}
        {term.running && <p><span className="opacity-60">$ </span>{term.running.command} <span className="animate-pulse">▍</span></p>}
        <div ref={end} />
      </div>
    </Card>
  );
}
