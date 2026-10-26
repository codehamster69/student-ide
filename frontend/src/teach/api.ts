// Teacher authoring API (/api/teach/*), same admin token as the review timeline.

export type LabStatus = "draft" | "open" | "closed";

export interface LabRow {
  id: string;
  title: string;
  description: string;
  status: LabStatus;
  everyone: boolean;
  created_at: number;
  updated_at: number;
  n_questions: number;
  n_roster: number;
  n_sessions: number;
  n_started: number;
}

export interface Question {
  id: string;
  lab_id: string;
  position: number;
  title: string;
  prompt: string;
  starter_code: string;
  sample_input: string;
  n_sessions: number;
}

export interface LabDetail extends Omit<LabRow, "n_questions" | "n_roster" | "n_started"> {
  questions: Question[];
  roster: string[];
  progress: { student_id: string; question_id: string; n: number; submitted: boolean; last_at: number }[];
}

export type QuestionFields = Pick<Question, "title" | "prompt" | "starter_code" | "sample_input">;

export const STATUS: Record<LabStatus, { label: string; about: string }> = {
  draft: { label: "Draft", about: "Only you can see it." },
  open: { label: "Open", about: "Assigned students see it and can start." },
  closed: { label: "Closed", about: "Hidden from students; recordings are kept." },
};

/** Roll numbers typed or pasted in any mix of commas, spaces and new lines. */
export function parseIds(text: string): string[] {
  return [...new Set(text.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean))];
}
