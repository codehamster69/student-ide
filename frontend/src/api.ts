import type { LivePrompt } from "./questionText";

export interface Task {
  id: string;
  title: string;
  prompt: string;
  starter_code: string;
  sample_input: string;
  /** lab questions run in the lab's language; practice tasks are Python. "any": a competition where the student picks */
  language?: "python" | "c" | "cpp" | "java" | "javascript" | "any";
  /** any-language competitions: the languages this question can be answered in */
  languages?: ("python" | "c" | "cpp" | "java" | "javascript")[];
  /** any-language competitions: starter code (and test driver) per language */
  variants?: Partial<Record<"python" | "c" | "cpp" | "java" | "javascript", { starter_code: string; harness: string }>>;
  subject?: string;
  /** optional tests: the visible ones in full, hidden ones only counted */
  tests?: { name: string; stdin: string; expected: string }[];
  n_tests?: number;
  n_hidden_tests?: number;
  harness?: string;
  /** set when the task is a question from a lab the teacher assigned */
  lab_id?: string;
  lab_title?: string;
  position?: number;
  sessions?: number;
  submitted?: boolean;
  /** set when the question belongs to a class competition (Submit runs its tests) */
  competition?: boolean;
  /** competition questions: when the clock runs out (unix seconds, server clock) */
  ends_at?: number | null;
  /** a learning-lab lesson: `prompt` is Markdown, `submitted` means done (Check passed, or ran code if it has no tests) */
  lesson?: boolean;
  /** learning lab: one line under the title in the lesson list */
  summary?: string;
  /** where the question came from; live_prompt: its text is loaded by the browser, never stored */
  source?: { url?: string; live_prompt?: LivePrompt } | null;
}

export interface Lab {
  id: string;
  kind: "lab" | "competition";
  title: string;
  description: string;
  questions: Task[];
  /** competitions only: questions stay hidden until the clock starts */
  state?: "waiting" | "live" | "ended";
  ends_at?: number | null;
  duration_s?: number | null;
  n_questions?: number;
  joined?: boolean;
}

/** A learning-lab track: lessons in one language, always open (see backend/studentide/learn.py). */
export interface LearnTrack {
  id: string;
  title: string;
  language: "python" | "c" | "cpp" | "java" | "javascript";
  /** "beginner" | "intermediate" | "advanced"; tracks come ordered beginner to advanced */
  level: string;
  summary: string;
  lessons: Task[];
}

export interface RunResult {
  run_id: string;
  code_sha256: string;
  exit_code: number | null;
  duration_ms: number;
  error_type: string | null;
  stdout: string;
  stderr: string;
}

export interface CheckResult {
  check_id: string;
  passed: number;
  total: number;
  results: { name: string; passed: boolean; hidden: boolean; error_type: string | null; duration_ms: number;
    stdin?: string; stdout?: string; expected?: string; stderr?: string }[];
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, body === undefined ? undefined : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `request failed (${res.status})`);
  }
  return res.json();
}
