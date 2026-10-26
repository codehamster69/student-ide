// Class competitions: shared types for the student arena and the teacher board.
// Competitions are the one place correctness counts: every submission runs the
// question's test cases. The board never shows anything from the review timeline.

import type { Task } from "../api";

export type CompState = "draft" | "waiting" | "live" | "ended" | "closed";
export type BoardMode = "top" | "all" | "hidden";

export interface BadgeInfo { id: string; label: string }

export interface QuestionProgress {
  tries: number;
  solved: boolean;
  points: number;
  passed: number | null;
  total: number | null;
}

export interface BoardRow {
  rank: number;
  handle: string;
  points: number;
  solved: number;
  badges: BadgeInfo[];
  me?: boolean;
  /** teacher view only */
  student_id?: string;
  runs?: number;
  fixes?: number;
  questions?: QuestionProgress[];
}

export interface CompSettings {
  lab_id: string;
  title: string;
  description: string;
  status: "draft" | "open" | "closed";
  state: CompState;
  duration_min: number | null;
  duration_s: number | null;
  board_mode: BoardMode;
  started_at: number | null;
  ends_at: number | null;
  /** server clock, to correct the countdown for a skewed lab machine */
  now: number;
}

export interface TeacherComp extends CompSettings {
  questions: { id: string; title: string; n_tests: number }[];
  roster: string[];
  board: BoardRow[];
}

export interface ArenaQuestion extends Task {
  competition: true;
  progress: QuestionProgress | null;
}

export interface ArenaView extends CompSettings {
  joined: boolean;
  me: (BoardRow & { of: number; questions: QuestionProgress[] }) | null;
  n_players: number;
  board: BoardRow[];
  questions: ArenaQuestion[];
  lobby: string[];
}

export interface SubmitResult {
  passed: number;
  total: number;
  /** stdout and expected are only present for tests that are not hidden */
  results: { name: string; passed: boolean; hidden: boolean; error_type: string | null; stdout?: string; expected?: string }[];
  standing: ArenaView["me"];
}

export const BOARD_MODES: Record<BoardMode, { label: string; about: string }> = {
  top: { label: "Top 10", about: "Students see the top ten and their own place. Nobody is shown at the bottom." },
  all: { label: "Everyone", about: "Students see the whole class ranked." },
  hidden: { label: "Reveal at end", about: "Students see only their own score until time is up, then the top ten." },
};

export const POINTS = { solve: 100, speed: 50 };

/** Seconds left on the clock, corrected by the server/client offset taken at fetch time. */
export function secondsLeft(c: Pick<CompSettings, "ends_at">, offset: number): number | null {
  return c.ends_at === null ? null : Math.max(0, c.ends_at - (Date.now() / 1000 + offset));
}

export function clock(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
    : `${m}:${String(sec).padStart(2, "0")}`;
}
