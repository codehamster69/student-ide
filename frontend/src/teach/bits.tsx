import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { CheckCircle2, ChevronDown, CircleX, EyeOff, FlaskConical, Link2, Plus, Trash2 } from "lucide-react";
import { Badge, Button, Checkbox, Spinner, TextArea, cn, spring } from "../ui";
import { BLANK_TEST, LANGUAGES, type GradeResult, type Language, type QuestionSource, type TestCase } from "./api";

const select =
  "h-11 w-full appearance-none rounded-lg border border-border bg-surface pl-3 pr-9 text-sm text-text shadow-sm outline-none " +
  "transition-[border-color,box-shadow] duration-150 hover:border-border-strong focus:border-accent focus:ring-4 focus:ring-accent/15";

export function LanguageSelect({ value, onChange, className, id }: {
  value: Language; onChange: (l: Language) => void; className?: string; id?: string;
}) {
  return (
    <span className={cn("relative block", className)}>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value as Language)} className={select} aria-label="Programming language">
        {(Object.keys(LANGUAGES) as Language[]).map((l) => <option key={l} value={l}>{LANGUAGES[l].label}</option>)}
      </select>
      <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-faint" />
    </span>
  );
}

export function LanguageBadge({ language }: { language: Language }) {
  const l = LANGUAGES[language] ?? LANGUAGES.python;
  return (
    <Badge className="h-5 gap-1 px-2 text-[11px]">
      <span className="size-1.5 rounded-sm" style={{ background: l.color }} />{l.label}
    </Badge>
  );
}

const PROVIDER_NAMES: Record<string, string> = { exercism: "Exercism", leetcode: "LeetCode", hackerrank: "HackerRank", codechef: "CodeChef" };

export function SourceBadge({ source }: { source: QuestionSource | null }) {
  if (!source) return null;
  const name = PROVIDER_NAMES[source.provider] ?? source.provider;
  return (
    <a href={source.url} target="_blank" rel="noreferrer" title={source.attribution ?? `Linked from ${name}`}
      className="inline-flex h-5 items-center gap-1 rounded-full border border-border bg-surface-2 px-2 text-[11px] font-medium text-muted hover:text-text">
      <Link2 className="size-3" /> {source.linked_only ? `${name} link` : `From ${name}`}
    </a>
  );
}

const box = "bg-surface-2 font-mono text-[12px] leading-relaxed";

/** The optional test-case list inside the question form. */
export function TestsEditor({ tests, onChange, harness }: { tests: TestCase[]; onChange: (t: TestCase[]) => void; harness?: string }) {
  const [open, setOpen] = useState(tests.length > 0);
  const set = (i: number, patch: Partial<TestCase>) => onChange(tests.map((t, j) => (j === i ? { ...t, ...patch } : t)));
  const hidden = tests.filter((t) => t.hidden).length;

  return (
    <div className="rounded-xl border border-border">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
        className="flex w-full items-center gap-2 px-4 py-3 text-left">
        <FlaskConical className="size-4 text-accent" />
        <span className="text-[13px] font-medium text-text">Test cases</span>
        <span className="text-xs text-faint">optional</span>
        <span className="ml-auto text-xs text-muted">
          {tests.length ? `${tests.length} test${tests.length === 1 ? "" : "s"}${hidden ? `, ${hidden} hidden` : ""}` : "none, effort only"}
        </span>
        <ChevronDown className={cn("size-4 text-faint transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden">
            <div className="grid gap-3 border-t border-border px-4 pb-4 pt-3">
              <p className="text-xs text-muted">
                In a lab, students can press Check to see how they're doing; it never counts toward anything.
                Competitions score on these tests, so a competition question needs at least one.
              </p>
              {harness && (
                <details className="rounded-lg border border-border bg-surface-2/60 px-3 py-2 text-xs text-muted">
                  <summary className="cursor-pointer font-medium text-text">Test driver (added after the student's code when tests run)</summary>
                  <pre className="mt-2 overflow-x-auto font-mono text-[11.5px]">{harness}</pre>
                </details>
              )}
              <AnimatePresence initial={false}>
                {tests.map((t, i) => (
                  <motion.div key={i} layout transition={spring} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, height: 0 }} className="grid gap-2 rounded-lg border border-border bg-surface p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] font-semibold text-faint">#{i + 1}</span>
                      <input value={t.name} onChange={(e) => set(i, { name: e.target.value })} maxLength={120} placeholder="Name (optional)"
                        aria-label={`Test ${i + 1} name`}
                        className="h-8 min-w-0 flex-1 rounded-md bg-transparent px-2 text-[13px] text-text outline-none hover:bg-surface-2 focus:bg-surface-2" />
                      <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted" title="Students see pass or fail only">
                        <Checkbox checked={t.hidden} onChange={(e) => set(i, { hidden: e.target.checked })} className="size-4" />
                        <EyeOff className="size-3.5" /> Hidden
                      </label>
                      <Button variant="ghost" size="icon" aria-label={`Remove test ${i + 1}`} onClick={() => onChange(tests.filter((_, j) => j !== i))}>
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <TextArea rows={2} spellCheck={false} value={t.stdin} onChange={(e) => set(i, { stdin: e.target.value })}
                        placeholder="Input" aria-label={`Test ${i + 1} input`} className={box} />
                      <TextArea rows={2} spellCheck={false} value={t.expected} onChange={(e) => set(i, { expected: e.target.value })}
                        placeholder="Expected output" aria-label={`Test ${i + 1} expected output`} className={box} />
                    </div>
                    {t.compare !== "text" && <p className="text-[11px] text-faint">{t.compare === "json" ? "Compared as JSON values." : "Numbers compared within 1e-6."}</p>}
                  </motion.div>
                ))}
              </AnimatePresence>
              <Button size="sm" className="justify-self-start" onClick={() => onChange([...tests, { ...BLANK_TEST }])}>
                <Plus className="size-3.5" /> Add test
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Per-test pass/fail list, used by the teacher's "try an answer" box and the student's Check. */
export function GradeView({ grade, dark }: { grade: GradeResult; dark?: boolean }) {
  const all = grade.passed === grade.total;
  return (
    <div className="grid gap-2">
      <p className={cn("flex items-center gap-1.5 text-sm font-semibold", all ? "text-success" : dark ? "text-console-text" : "text-text")}>
        {all ? <CheckCircle2 className="size-4" /> : <CircleX className="size-4 text-danger" />}
        {grade.passed} of {grade.total} passed
      </p>
      <ul className="grid gap-1.5">
        {grade.results.map((r, i) => (
          <li key={i} className={cn("rounded-lg border px-3 py-2 text-xs",
            dark ? "border-white/10 bg-white/[0.03] text-console-text" : "border-border bg-surface-2/60 text-muted")}>
            <div className="flex items-center gap-2">
              {r.passed ? <CheckCircle2 className="size-3.5 shrink-0 text-success" /> : <CircleX className="size-3.5 shrink-0 text-danger" />}
              <span className={cn("font-medium", dark ? "text-console-text" : "text-text")}>{r.name}</span>
              {r.hidden && <span className="inline-flex items-center gap-1 text-faint"><EyeOff className="size-3" /> hidden</span>}
              {r.error_type && <span className="text-danger">{r.error_type}</span>}
              <span className="ml-auto tabular-nums text-faint">{Math.round(r.duration_ms)} ms</span>
            </div>
            {!r.passed && !r.hidden && r.expected !== undefined && (
              <div className="mt-2 grid gap-2 font-mono text-[11.5px] sm:grid-cols-3">
                <Pre label="Input" text={r.stdin ?? ""} />
                <Pre label="Expected" text={r.expected} />
                <Pre label="Got" text={r.stdout || r.stderr || "(no output)"} />
              </div>
            )}
            {!r.passed && r.error_type === "CompileError" && r.stderr && <Pre label="Compiler" text={r.stderr} />}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Pre({ label, text }: { label: string; text: string }) {
  return (
    <div className="min-w-0">
      <p className="mb-0.5 font-sans text-[10.5px] font-semibold uppercase tracking-wide text-faint">{label}</p>
      <pre className="m-0 max-h-28 overflow-auto whitespace-pre-wrap break-words">{text}</pre>
    </div>
  );
}

/** Teacher-side: run a model answer through the question's tests. */
export function TryAnswer({ run, starter }: { run: (code: string) => Promise<GradeResult>; starter: string }) {
  const [code, setCode] = useState(starter);
  const [busy, setBusy] = useState(false);
  const [grade, setGrade] = useState<GradeResult | null>(null);
  const [error, setError] = useState("");
  return (
    <details className="rounded-xl border border-border px-4 py-3">
      <summary className="cursor-pointer text-[13px] font-medium text-text">Try an answer against the saved tests</summary>
      <div className="mt-3 grid gap-2">
        <TextArea rows={6} spellCheck={false} value={code} onChange={(e) => setCode(e.target.value)} className={box} aria-label="Model answer" />
        <Button size="sm" className="justify-self-start" disabled={busy}
          onClick={async () => {
            setBusy(true); setError("");
            try { setGrade(await run(code)); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
          }}>
          {busy ? <Spinner className="size-3.5" /> : <FlaskConical className="size-3.5" />} Run tests
        </Button>
        {error && <p className="text-xs text-danger">{error}</p>}
        {grade && <GradeView grade={grade} />}
      </div>
    </details>
  );
}
