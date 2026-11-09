// Research-side API for the review timeline. Every call carries the admin
// token (kept in sessionStorage, so it goes away with the tab).

export type Channel = "identity" | "pairs" | "process";
export const CHANNELS: Channel[] = ["identity", "pairs", "process"];

export interface Truth {
  condition: "honest" | "proxy" | "takeover" | "copying" | "paste";
  student: string;
  author_after: string | null;
  switch_s: number | null;
}

export interface SessionInfo {
  id: string;
  student_id: string;
  task_id: string;
  /** title of the lab question this session answered; null for practice tasks */
  task_title: string | null;
  lab_id: string | null;
  started_at: number;
  ended_at: number | null;
  end_reason: string | null;
  n_events: number;
  duration_s: number;
  phase: "baseline" | "assessed";
  /** recorded in a class competition: timed, under pressure, with its own baseline */
  context: "lab" | "competition";
  synthetic: Truth | null;
}

export interface Episode {
  channel: Channel;
  label: string;
  switch_est: number;
  first_alarm: number;
  last_alarm: number;
  n_alarms: number;
  evidence: Evidence[];
}

export interface Evidence {
  feature: string;
  label: string;
  group: string;
  z: number;
  baseline: number;
  observed: number;
  unit: string;
}

export interface SessionSummary extends SessionInfo {
  baseline: "ready" | "insufficient";
  episodes: Episode[];
  peak: Partial<Record<Channel, number>>;
  spark: Partial<Record<Channel, number[]>>;
}

export interface ChannelTrace {
  label: string;
  about: string;
  h: number;
  k: number;
  /** each channel runs at its own window length (frozen by the evaluation harness) */
  window_s: number;
  start: number[];
  end: number[];
  score: (number | null)[];
  cusum: (number | null)[];
  peak: number;
}

export interface Review {
  session: SessionInfo;
  window_s: number;
  baseline: {
    status: "ready" | "insufficient"; n_sessions: number; needed: number; days: number; n_windows?: number;
    /** competition sessions are compared only with the student's other competitions */
    context: "lab" | "competition";
  };
  channels: Partial<Record<Channel, ChannelTrace>>;
  episodes: Episode[];
  windows: { start: number; end: number; active: boolean; n_keys: number }[];
  events: {
    pastes: { t: number; length: number; lines: number; preview: string; truncated: boolean }[];
    focus: { t: number; until: number; target: string }[];
    runs: { t: number; exit_code: number | null; error_type: string | null }[];
  };
}

export interface ReplayFile {
  path: string | null;
  initial: string;
  edits: [number, [number, number, string][], string][];
}

export interface ReplayData {
  initial: string;
  edits: [number, [number, number, string][], string][];
  keys: number[];
  /** every file of a Sandbox Lab session (first = main file); one entry with path null on the web */
  files?: ReplayFile[];
}

/** Sandbox Lab lanes (backend sandbox_review.py). Times are seconds into the session. */
export interface SandboxLanes {
  commands: { t: number; end: number | null; command: string; cwd: string; exit_code: number | null; tail: string }[];
  saves: { t: number; path: string; origin: "terminal-editor" | "terminal" | "outside"; command: string | null; added_lines: number;
    removed_lines: number; added_chars: number; typed_keys: number; deleted: boolean; binary: boolean; explained: boolean; diff: string }[];
  pastes: { t: number; length: number; lines: number }[];
  ports: { t: number; port: number; process: string; open: boolean }[];
  network: { t: number; host: string; allowed: boolean }[];
  packages: { t: number; manager: string; action: string; packages: string[] }[];
  terminal_keys: number;
  quiet: { t: number; end: number; enters: number }[];
  signed: boolean;
  offline: { t: number; end: number; seconds: number; lag_s: number | null }[];
  breaks: { t: number | null; problem: string }[];
  unseen: { sha256: string; reason: string; created_at: number; files: number;
    unseen: { path: string; unseen_lines: number; unseen_chars: number; share: number; examples: string[] }[] }[];
  watching: boolean | null;
}

/** One lab as the Review tab lists it: when it ran, who came, what stood out. */
export interface LabSessionRow {
  /** "practice" for sessions outside any lab (admins only) */
  id: string;
  title: string;
  kind: "lab" | "competition" | "practice" | "sandbox";
  subject: string;
  status: "draft" | "open" | "closed" | null;
  started_at: number;
  ended_at: number;
  /** when each class sitting began */
  sittings_at: number[];
  n_students: number;
  n_sessions: number;
  n_assessed: number;
  n_with_moments: number;
  students_with_moments: number;
}

export interface StudentRow {
  student_id: string;
  n_sessions: number;
  n_baseline: number;
  baseline_ready: boolean;
}

const KEY = "studentide.review.token";

export const token = {
  get: () => { try { return sessionStorage.getItem(KEY) ?? ""; } catch { return ""; } },
  set: (v: string) => { try { sessionStorage.setItem(KEY, v); } catch { /* private mode */ } },
  clear: () => { try { sessionStorage.removeItem(KEY); } catch { /* private mode */ } },
};

export class AuthError extends Error {}

/** A lab of another teacher: show the message, stay signed in. */
const notYours = (res: Response) => res.status === 403 && res.headers.get("X-Refusal") === "not-yours";

export async function get<T>(path: string, tok = token.get()): Promise<T> {
  const res = await fetch(path, { headers: { "X-Admin-Token": tok } });
  if (res.status === 401 || res.status === 403) {
    const detail = await res.json().catch(() => ({}));
    if (notYours(res)) throw new Error(detail.detail);
    throw new AuthError(detail.detail ?? "not allowed");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(typeof detail.detail === "string" ? detail.detail : `request failed (${res.status})`);
  }
  return res.json();
}

/** Write call for the teacher screens (POST/PUT/PATCH/DELETE), same token. */
export async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: { "X-Admin-Token": token.get(), ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const detail = await res.json().catch(() => ({}));
  if (notYours(res)) throw new Error(detail.detail);
  if (res.status === 401 || res.status === 403) throw new AuthError(detail.detail ?? "not allowed");
  if (!res.ok) throw new Error(typeof detail.detail === "string" ? detail.detail : `request failed (${res.status})`);
  return detail as T;
}
