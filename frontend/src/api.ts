export interface Task {
  id: string;
  title: string;
  prompt: string;
  starter_code: string;
  sample_input: string;
  /** set when the task is a question from a lab the teacher assigned */
  lab_id?: string;
  lab_title?: string;
  position?: number;
  sessions?: number;
  submitted?: boolean;
  /** set when the question belongs to a class competition (Submit runs its tests) */
  competition?: boolean;
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

export interface RunResult {
  run_id: string;
  code_sha256: string;
  exit_code: number | null;
  duration_ms: number;
  error_type: string | null;
  stdout: string;
  stderr: string;
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
