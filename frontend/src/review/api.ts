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

export interface ReplayData {
  initial: string;
  edits: [number, [number, number, string][], string][];
  keys: number[];
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

export async function get<T>(path: string, tok = token.get()): Promise<T> {
  const res = await fetch(path, { headers: { "X-Admin-Token": tok } });
  if (res.status === 401 || res.status === 403) {
    const detail = await res.json().catch(() => ({}));
    throw new AuthError(detail.detail ?? "not allowed");
  }
  if (!res.ok) throw new Error(`request failed (${res.status})`);
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
  if (res.status === 401 || res.status === 403) throw new AuthError(detail.detail ?? "not allowed");
  if (!res.ok) throw new Error(typeof detail.detail === "string" ? detail.detail : `request failed (${res.status})`);
  return detail as T;
}
