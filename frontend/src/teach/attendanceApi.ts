// Attendance through Roll Call (backend: studentide/attendance.py).

export interface Rule { min_active_minutes: number; min_typed_chars: number; require_run: boolean }

export interface Connection { connected: boolean; url: string; connected_at: number | null; rule: Rule; timezone: string }

/** A class group in the teacher's Roll Call */
export interface RollCallClass { id: string; branch: string; section: string; group: string; label: string; students: string[] }

export interface RollCallSubject { id: string | null; code: string; name: string }

export interface SentRow {
  day: string; class_id: string; rollcall_id: string; sent_at: number; sent_by: string; how: "teacher" | "lab closed";
  present: number; total: number; error: string | null;
}

/** GET /api/teach/labs/<id>/classes */
export interface LabClasses {
  classes: { class_id: string; label: string; attached_by: string; attached_at: number; n_students: number }[];
  days: string[];
  sent: SentRow[];
  rule: Rule;
  auto_send: boolean;
  describe: string;
  rollcall_url: string;
}

export interface StudentMark {
  student_id: string;
  present: boolean;
  /** what the rule says, before any override */
  auto: boolean;
  override: "P" | "A" | null;
  reason: string;
  active_minutes: number;
  typed: number;
  pasted: number;
  runs: number;
  first: number | null;
  last: number | null;
}

/** GET /api/teach/labs/<id>/attendance?day= */
export interface Preview {
  day: string;
  days: string[];
  rule: Rule;
  auto_send: boolean;
  describe: string;
  classes: { class_id: string; label: string; students: StudentMark[]; present: number; total: number; sent: SentRow | null }[];
  not_in_any_class: Omit<StudentMark, "auto" | "override">[];
}

export type LabAttendanceSummary = Record<string, { classes: string[]; days_sent: number; last_sent: number | null; errors: number }>;

/** "UG23CS001" -> prefix "UG23CS", roll 1, 3 digits: how Roll Call builds the same id. */
export function splitId(id: string): { prefix: string; roll: number; digits: number } | null {
  const m = id.match(/^(.*?)(\d+)$/);
  return m ? { prefix: m[1], roll: Number(m[2]), digits: m[2].length } : null;
}

export const dayLabel = (day: string) =>
  new Date(`${day}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
