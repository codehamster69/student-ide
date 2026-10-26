// Session lifecycle that does not depend on the UI framework: create the
// session on the server, start the recorder, and log session_start.

import { api, type Task } from "../api";
import { Recorder, SCHEMA_VERSION } from "../recorder";

export interface LiveSession {
  id: string;
  rec: Recorder;
}

export async function startSession(studentId: string, task: Task): Promise<LiveSession> {
  const meta = {
    user_agent: navigator.userAgent,
    language: navigator.language,
    platform: (navigator as any).userAgentData?.platform ?? navigator.platform,
    screen: { w: window.screen.width, h: window.screen.height, dpr: devicePixelRatio },
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    client_schema_version: SCHEMA_VERSION,
  };
  const { session_id } = await api<{ session_id: string }>("/api/sessions", {
    student_id: studentId, task_id: task.id, client_meta: meta,
  });
  const rec = new Recorder(session_id);
  (window as any).__studentide = { rec, sessionId: session_id }; // for end-to-end tests
  rec.log("session_start", { wall_clock_ms: Date.now() });
  return { id: session_id, rec };
}
