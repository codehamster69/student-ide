// Sandbox Labs (teacher side): subjects, environments, labs of assignments, the
// shared library and cloud previews. Server: backend/studentide/sandbox.py and
// previews.py; the lab format is in docs/sandbox-labs.md.

export type Base = "c-cpp" | "python" | "java" | "linux" | "web-node" | "databases";
export type Network = "open" | "registries" | "off";
export type LabStatus = "draft" | "published" | "closed";
export type BuildStatus = "needs_approval" | "queued" | "building" | "ready" | "failed";
export type Access = "owner" | "co_teacher" | "ta" | "admin";

export interface BaseInfo { id: Base; label: string; includes: string; mb: number; tools: string[] }
export interface Tool { id: string; label: string; group: string; mb: number; apt?: string[]; pip?: string[]; npm?: string[] }

export interface Recipe {
  base: Base;
  tools: string[];
  apt: string[];
  pip: string[];
  npm: string[];
  setup: string;
  dockerfile: string;
  resources?: Partial<Resources>;
}
export interface Resources { cpus: number; memory_mb: number; disk_gb: number; pids: number }

export interface EnvVersion {
  version: number;
  status: BuildStatus;
  digest: string | null;
  log: string;
  recipe: Recipe;
  image: string;
  size_mb: number | null;
  approved_by: string | null;
  updated_at: number;
}
export interface Environment {
  id: string;
  title: string;
  owner_email: string | null;
  shared: boolean;
  mine: boolean;
  versions: EnvVersion[];
  updated_at: number;
}

export interface SubjectRow {
  id: string;
  title: string;
  code: string;
  semester: string;
  color: string;
  owner_email: string | null;
  access: Access;
  co_teachers: string[];
  tas: string[];
  n_students: number;
  n_labs: number;
  n_published: number;
  copied_from: string | null;
  environment: { id: string; title: string; version: number; status: BuildStatus; base: Base } | null;
}
export interface SubjectDetail extends SubjectRow {
  labs: LabRow[];
  roster: { id: string; section: string }[];
}

export interface LabRow {
  id: string;
  subject_id: string;
  title: string;
  description: string;
  status: LabStatus;
  network: Network;
  assessed: boolean;
  sections: string[];
  env_version: number | null;
  opens_at: number | null;
  due_at: number | null;
  min_desktop_version: string | null;
  version: number;
  based_on: string | null;
  n_assignments: number;
  shared: boolean;
  update_available?: boolean;
  updated_at: number;
}

export interface SandboxFile { path: string; content: string; executable?: boolean }
export interface TestCase { name: string; stdin: string; expected: string; hidden: boolean; compare: "text" | "json" | "tokens" }
export interface Tests { kind: "io" | "command"; command: string; timeout_s: number; cases: TestCase[] }

export interface Assignment {
  id: string;
  position: number;
  title: string;
  statement: string;
  workdir: string;
  files: SandboxFile[];
  open: string[];
  run: string;
  tests: Tests;
  solution_files: SandboxFile[];
}
export interface Definition {
  format: string;
  id: string;
  version: number;
  title: string;
  description: string;
  subject: { id: string; code: string; title: string };
  environment: { id: string; version: number; title: string; image: string; digest: string | null; status: BuildStatus;
                 recipe: Recipe; resources: Resources } | null;
  network: Network;
  assessed: boolean;
  status: LabStatus;
  assignments: Assignment[];
}
export interface LabDetail extends LabRow {
  definition: Definition;
  problems: string[];
  access: Access;
}

export interface LibraryEntry {
  id: string;
  lab_id: string;
  shared_by: string | null;
  title: string;
  summary: string;
  subject_title: string;
  difficulty: "" | "intro" | "intermediate" | "advanced";
  base: Base | "";
  topics: string[];
  version: number;
  uses: number;
  shared_at: number;
  n_assignments: number;
  lab?: Definition;
}

export interface Seats { total: number; used: number; free: number; next_free_at: number | null; idle_minutes: number; max_minutes: number }
export interface Preview {
  id: string;
  teacher_email: string;
  lab_id: string;
  lab_title: string;
  status: "starting" | "running" | "stopped" | "failed";
  error: string;
  started_at: number;
  last_active: number;
  ends_at: number;
  stop_reason: string | null;
  lab?: Definition | null;
  seats?: Seats;
}
export interface RunResult { stdout: string; stderr: string; exit_code: number; timed_out: boolean; duration_ms: number }
export interface TestResult { name: string; passed: boolean; hidden?: boolean; stdin?: string; expected?: string; got?: string; stderr?: string; timed_out?: boolean }
export interface CheckResult { passed: number; total: number; results: TestResult[] }
export type SubmissionStatus = "queued" | "grading" | "graded" | "failed" | "no_tests";
/** A graded Submit (submissions.py). Students get hidden tests as name + pass only. */
export interface Submission {
  id: string; lab_id: string; assignment_id: string; status: SubmissionStatus;
  passed: number | null; total: number | null; submitted_at: number; graded_at: number | null;
  error: string; regraded: boolean; attempts?: number; results: (TestResult & { stdout?: string; exit_code?: number })[];
}
export interface SubmissionCell extends Submission { student_id: string; session_id: string | null }
export interface SubmissionsTable {
  lab: { id: string; title: string; due_at: number | null; status: LabStatus };
  assignments: { id: string; title: string }[];
  students: { student_id: string; section: string; on_roster: boolean; assignments: Record<string, SubmissionCell | null> }[];
  grader: { enabled: boolean; queued: number };
  counts: { students: number; submitted: number; graded: number; passed_all: number };
}
export interface VerifyResult {
  ok: boolean;
  assignments: { assignment_id: string; title: string; problems: string[];
                 starter?: { passed: number; total: number }; solution?: { passed: number; total: number } }[];
}

export const NETWORK: Record<Network, { label: string; hint: string }> = {
  registries: { label: "Package registries only", hint: "apt, pip, npm, Maven and the like work; other websites don't. For assessed labs." },
  off: { label: "No network", hint: "Nothing outside the instance. For exams." },
  open: { label: "Open internet", hint: "Everything. Practice labs only, never assessed ones." },
};

export const BUILD: Record<BuildStatus, { label: string; tone: "neutral" | "accent" | "success" | "warn" | "danger" }> = {
  needs_approval: { label: "Waiting for an admin", tone: "warn" },
  queued: { label: "Queued to build", tone: "neutral" },
  building: { label: "Building", tone: "accent" },
  ready: { label: "Ready", tone: "success" },
  failed: { label: "Build failed", tone: "danger" },
};

/** Subject colours, drawn from theme tokens so both themes work. */
export const COLOR_VAR: Record<string, string> = {
  indigo: "var(--accent)", teal: "var(--success)", amber: "var(--warn)", rose: "var(--danger)",
  sky: "var(--ch-identity)", violet: "var(--ch-pairs)", emerald: "var(--ch-process)", orange: "var(--bronze)",
};
export const tint = (color: string, pct = 14) => {
  const v = COLOR_VAR[color] ?? COLOR_VAR.indigo;
  return { color: v, backgroundColor: `color-mix(in srgb, ${v} ${pct}%, transparent)` };
};

export const emptyRecipe = (base: Base = "c-cpp"): Recipe => ({ base, tools: [], apt: [], pip: [], npm: [], setup: "", dockerfile: "" });
export const emptyTests = (): Tests => ({ kind: "io", command: "", timeout_s: 10, cases: [] });
