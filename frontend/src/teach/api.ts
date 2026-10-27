import type { LivePrompt } from "../questionText";
// Teacher authoring API (/api/teach/*), same admin token as the review timeline.

export type LabStatus = "draft" | "open" | "closed";
export type Language = "python" | "c" | "cpp" | "java" | "javascript";

export const LANGUAGES: Record<Language, { label: string; file: string; color: string }> = {
  python: { label: "Python", file: "main.py", color: "#3776ab" },
  c: { label: "C", file: "main.c", color: "#5c6bc0" },
  cpp: { label: "C++", file: "main.cpp", color: "#00599c" },
  java: { label: "Java", file: "Main.java", color: "#e76f00" },
  javascript: { label: "JavaScript", file: "main.js", color: "#d4b106" },
};

/** Optional. stdin in, stdout out; hidden ones show students pass/fail only. */
export interface TestCase {
  name: string;
  stdin: string;
  expected: string;
  hidden: boolean;
  compare: "text" | "json" | "tokens" | "checker";
}

/** Where an imported or linked question came from. */
export interface QuestionSource {
  provider: string;
  url: string;
  ref?: string;
  license?: string;
  attribution?: string;
  linked_only?: boolean;
  notes?: string[];
  /** the text is loaded live by the browser and never stored (LeetCode) */
  live_prompt?: LivePrompt;
}

export interface LabRow {
  id: string;
  title: string;
  description: string;
  status: LabStatus;
  /** a class competition is a lab with a clock, test-graded submissions and a leaderboard */
  kind: "lab" | "competition";
  everyone: boolean;
  subject: string;
  language: Language;
  created_at: number;
  updated_at: number;
  n_questions: number;
  n_roster: number;
  n_sessions: number;
  n_started: number;
  /** the teacher who made it; null = from before ownership, admins only until handed over */
  owner_email: string | null;
  /** colleagues it is shared with: same rights as the owner except resharing */
  co_teachers: string[];
  /** how the signed-in teacher reaches it */
  access: "owner" | "co_teacher" | "admin";
}

export interface Question {
  id: string;
  lab_id: string;
  position: number;
  title: string;
  prompt: string;
  starter_code: string;
  sample_input: string;
  tests: TestCase[];
  harness: string;
  source: QuestionSource | null;
  n_sessions: number;
}

export interface LabDetail extends Omit<LabRow, "n_questions" | "n_roster" | "n_started"> {
  questions: Question[];
  roster: string[];
  progress: { student_id: string; question_id: string; n: number; submitted: boolean; last_at: number }[];
}

export type QuestionFields = Pick<Question, "title" | "prompt" | "starter_code" | "sample_input" | "tests">;

export interface Provider {
  id: string;
  name: string;
  /** live: fetched when browsed; bundled: an openly licensed dataset shipped with the app; link_only: links only */
  status: "live" | "bundled" | "link_only";
  about: string;
  terms_url: string;
  hosts: string[];
  license: string;
  can_browse: boolean;
  can_link: boolean;
  /** lab languages it has questions for; null: every language */
  languages: Language[] | null;
}

export interface SourceCategory { id: string; label: string; count: number }
export interface SourceSummary { ref: string; title: string; difficulty: string; categories: string[]; blurb: string }
export interface SourcePreview {
  title: string;
  prompt: string;
  starter_code: string;
  tests: TestCase[];
  harness: string;
  source: QuestionSource;
  notes: string[];
}

export interface GradeResult {
  passed: number;
  total: number;
  results: { name: string; passed: boolean; hidden: boolean; error_type: string | null; duration_ms: number;
    stdin?: string; stdout?: string; expected?: string; stderr?: string }[];
}

export const BLANK_TEST: TestCase = { name: "", stdin: "", expected: "", hidden: false, compare: "text" };

export const STATUS: Record<LabStatus, { label: string; about: string }> = {
  draft: { label: "Draft", about: "Only you can see it." },
  open: { label: "Open", about: "Assigned students see it and can start." },
  closed: { label: "Closed", about: "Hidden from students; recordings are kept." },
};

/** Roll numbers typed or pasted in any mix of commas, spaces and new lines. */
export function parseIds(text: string): string[] {
  return [...new Set(text.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean))];
}
