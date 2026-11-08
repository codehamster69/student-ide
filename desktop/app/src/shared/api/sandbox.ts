/**
 * `studentDesktop.sandbox`: lab instances in the local engine (owned by the sandbox
 * thread, implemented with @studentide/sandbox in src/main/modules/sandbox.ts).
 * A first sketch from the plan's Runtime interface; the owning thread refines it.
 */

export interface SetupCheck { id: string; ok: boolean; message: string; fix?: string }

export interface RunResult {
  // same shape as the backend runner (backend/studentide/runner.py)
  stdout: string;
  stderr: string;
  exit_code: number | null;
  timed_out: boolean;
  duration_ms: number;
}

export interface FileEntry { path: string; type: "file" | "dir"; size?: number }

export interface SandboxApi {
  setupCheck(): Promise<{ ok: boolean; checks: SetupCheck[] }>;
  /** Pulls the image if needed, starts the (student, subject) instance, writes starter files once. */
  openLab(labId: string): Promise<{ instanceId: string }>;
  stop(instanceId: string): Promise<void>;
  reset(instanceId: string): Promise<void>;
  listFiles(instanceId: string, dir: string): Promise<FileEntry[]>;
  readFile(instanceId: string, path: string): Promise<string>;
  writeFile(instanceId: string, path: string, content: string): Promise<void>;
  run(instanceId: string, opts: { cwd: string; language?: string; stdin?: string; timeoutMs?: number }): Promise<RunResult>;
}

export interface SandboxEvents {
  /** a schema v2 event from the instance; the renderer's Recorder logs it into the open session */
  "sandbox.event": { sessionKey: string; type: string; data: unknown };
  "sandbox.progress": { instanceId?: string; message: string; percent?: number };
}
