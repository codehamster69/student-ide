// Live classroom view (/api/live/*), same teacher sign-in as the review timeline.

import type { Language } from "../teach/api";

/** typing: edited in the last 20 s; active: in the last 2 min; idle: longer; away: the IDE tab is in the background;
 *  offline: the IDE stopped answering; submitted / left: the session is over. */
export type LiveState = "typing" | "active" | "idle" | "away" | "offline" | "submitted" | "left" | "not_started";

export interface LiveLab {
  id: string;
  title: string;
  kind: "lab" | "competition";
  language: Language;
  n_questions: number;
  n_roster: number;
  everyone: boolean;
  n_in_session: number;
  n_online: number;
}

export interface LiveStudent {
  student_id: string;
  state: LiveState;
  session_id: string | null;
  question_id: string | null;
  question_title: string | null;
  position: number | null;
  started_at: number | null;
  last_edit_at: number | null;
  /** edits per 30 s over the last 10 minutes, oldest first */
  activity: number[];
  tab_away: boolean;
  pastes: number;
  runs: number;
  run_errors: number;
  last_run: { at: number; ok: boolean; error_type: string | null } | null;
  check: { passed: number; total: number; at: number; best: number } | null;
  submitted: string[];
  /** moments worth a conversation found so far in this lab (review timeline) */
  moments: number;
  last_moment_at: number | null;
  /** the latest session in this lab with a moment (where "Timeline" should open) */
  moment_session_id: string | null;
  /** a teacher has this student's editor open right now */
  watched: boolean;
}

export interface LiveClass {
  lab: { id: string; title: string; kind: "lab" | "competition"; status: string; language: Language };
  questions: { id: string; title: string; position: number }[];
  students: LiveStudent[];
  now: number;
  editor_view: boolean;
}

export interface LiveEditor {
  session: {
    id: string; student_id: string; lab_id: string | null; lab_title: string | null; question_id: string | null;
    question_title: string; prompt: string; language: Language; started_at: number; ended_at: number | null; end_reason: string | null;
  };
  state: LiveState;
  text: string;
  caret: number | null;
  last_edit_at: number | null;
  tab_away: boolean;
  activity: number[];
  runs: { created_at: number; exit_code: number | null; error_type: string | null; duration_ms: number; stdin: string; stdout: string; stderr: string }[];
  check: { passed: number; total: number; created_at: number; best: number } | null;
  now: number;
}

export const STATE: Record<LiveState, { label: string; tone: "success" | "accent" | "neutral" | "warn"; live: boolean }> = {
  typing: { label: "Typing", tone: "success", live: true },
  active: { label: "Working", tone: "accent", live: false },
  idle: { label: "Quiet", tone: "neutral", live: false },
  away: { label: "Other tab", tone: "warn", live: false },
  offline: { label: "Not connected", tone: "neutral", live: false },
  submitted: { label: "Finished", tone: "success", live: false },
  left: { label: "Left", tone: "neutral", live: false },
  not_started: { label: "Not started", tone: "neutral", live: false },
};

/** Tell the server this teacher left the page, so the student's banner goes away at once. */
export function leaveView(q: { lab_id?: string; session_id?: string }, token: string) {
  const qs = new URLSearchParams(q as Record<string, string>).toString();
  void fetch(`/api/live/views?${qs}`, { method: "DELETE", headers: { "X-Admin-Token": token }, keepalive: true }).catch(() => {});
}

export function ago(now: number, t: number | null): string {
  if (t === null) return "never";
  const s = Math.max(0, Math.round(now - t));
  if (s < 10) return "just now";
  if (s < 60) return `${s} s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return `${Math.floor(s / 3600)} h ago`;
}
