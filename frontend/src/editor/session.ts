// Session lifecycle that does not depend on the UI framework: create the
// session on the server, start the recorder, and log session_start.

import { api, type Task } from "../api";
import { clientInfo } from "../desktop";
import type { Language } from "../teach/api";
import { Recorder, SCHEMA_VERSION } from "../recorder";

export interface LiveSession {
  id: string;
  rec: Recorder;
  /** a lab or competition question opened again (later sitting, back from the board, a reload): the code as the student left it, in this language */
  resumeCode?: string | null;
  /** any-language competitions: the language this session is in (one session per language) */
  language?: Language;
}

const PREF = "studentide.language";

/** Any-language competitions: the language to open a question in. The one the
 * student last used on this question, else the one they used last anywhere. */
export function preferredLanguage(task: Task): Language | undefined {
  if (task.language !== "any") return undefined;
  const options = task.languages?.length ? task.languages : ["python" as Language];
  let saved: string | null = null;
  try { saved = localStorage.getItem(`${PREF}.${task.id}`) ?? localStorage.getItem(PREF); } catch { /* private mode */ }
  return options.includes(saved as Language) ? saved as Language : options[0];
}

export function rememberLanguage(task: Task, language: Language): void {
  try {
    localStorage.setItem(`${PREF}.${task.id}`, language);
    localStorage.setItem(PREF, language);
  } catch { /* private mode */ }
}

/** One opening of a lab. Every question visited gets its own session, all sharing this id. */
export function newSittingId(): string {
  return crypto.randomUUID?.().replace(/-/g, "") ?? Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function startSession(studentId: string, task: Task, sittingId?: string, language?: Language): Promise<LiveSession> {
  language ??= preferredLanguage(task);
  const meta = {
    user_agent: navigator.userAgent,
    language: navigator.language,
    platform: (navigator as any).userAgentData?.platform ?? navigator.platform,
    screen: { w: window.screen.width, h: window.screen.height, dpr: devicePixelRatio },
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    client_schema_version: SCHEMA_VERSION,
    client: await clientInfo(),
  };
  const { session_id, resume_code } = await api<{ session_id: string; resume_code?: string | null }>("/api/sessions", {
    student_id: studentId, client_meta: meta,
    // lab questions are checked against the teacher's roster on the server; lessons are open to everyone
    ...(task.lesson ? { lesson_id: task.id } : task.lab_id ? { question_id: task.id, sitting_id: sittingId } : { task_id: task.id }),
    ...(language ? { language } : {}),
  });
  if (language) rememberLanguage(task, language);
  const rec = new Recorder(session_id);
  (window as any).__studentide = { rec, sessionId: session_id }; // for end-to-end tests
  rec.log("session_start", { wall_clock_ms: Date.now() });
  return { id: session_id, rec, resumeCode: resume_code, language };
}
