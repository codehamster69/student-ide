/**
 * Types of `window.studentDesktop.sandbox` and `.terminal`, the renderer side
 * of registerSandboxIpc (desktop.ts). desktop/app/src/shared/api/{sandbox,terminal}.ts
 * re-export these so the contract has one source.
 */

export interface SetupCheckItem { id: string; ok: boolean; message: string; fix?: string; severity: "error" | "warning" | "info" }

export interface OpenedAssignment {
  id: string;
  title: string;
  workdir: string;
  /** sessionKey that this assignment's sandbox events carry: "<lab id>/<assignment id>" */
  sessionKey: string;
  /** what happened to the folder: new (starter files), kept, restored from the server, or conflict-kept-both */
  files: "new" | "kept" | "restored" | "conflict-kept-both";
  open: string[];
}

export interface OpenedLab {
  instanceId: string;
  labId: string;
  subjectId: string;
  /** false on engines that cannot enforce CPU/memory limits (the setup check explains) */
  limitsEnforced: boolean;
  network: "off" | "registries" | "open";
  /** the setup recipe was replayed because the instance was new on this machine */
  setup: { replayed: number; ok: number } | null;
  assignments: OpenedAssignment[];
}

export interface SandboxFile { path: string; type: "file" | "dir" | "link" | "other"; size: number; mtimeMs: number }

export interface SandboxRunResult {
  // same fields as the web runner (backend/studentide/runner.py) plus the run id and code hash
  run_id: string;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  duration_ms: number;
  error_type: string | null;
  code_sha256: string;
}

export interface SandboxTestResult { name: string; passed: boolean; stdout: string; stderr: string; expected?: string; error_type: string | null; duration_ms: number }

export interface SandboxStats {
  state: string;
  cpuPercent: number | null;
  memoryBytes: number | null;
  memoryLimitBytes: number | null;
  diskUsedBytes: number | null;
  diskLimitBytes: number;
}

export interface SandboxApi {
  setupCheck(): Promise<{ ok: boolean; checks: SetupCheckItem[] }>;
  /** Downloads the image if needed, starts the (student, subject) instance, restores or seeds every assignment. */
  openLab(labId: string): Promise<OpenedLab>;
  stop(instanceId: string): Promise<void>;
  /** Fresh instance from the environment; lab files stay and the setup recipe is replayed. */
  reset(instanceId: string): Promise<OpenedLab["setup"]>;
  stats(instanceId: string): Promise<SandboxStats>;
  listFiles(instanceId: string, dir: string): Promise<SandboxFile[]>;
  readFile(instanceId: string, path: string): Promise<string>;
  /** Editor save; schedules a workspace upload for the assignment that holds the file. */
  writeFile(instanceId: string, path: string, content: string): Promise<void>;
  /** The Run button: the assignment's run command in its workdir. */
  run(instanceId: string, assignmentId: string, opts?: { stdin?: string; timeoutMs?: number }): Promise<SandboxRunResult>;
  /** Visible tests, locally (practice; grades come from the server). */
  test(instanceId: string, assignmentId: string): Promise<SandboxTestResult[]>;
  /** Upload the folder now with reason "submit"; returns its content hash and, when the server grades
   *  submissions, the queued submission (backend/studentide/submissions.py; poll /api/sandbox/my/submissions/{id}). */
  submit(instanceId: string, assignmentId: string): Promise<{ sha256: string; submission?: unknown }>;
  recipe(instanceId: string): Promise<{ steps: Array<{ manager: string; action: string; packages: string[]; command: string }> }>;
}

export interface SandboxEvents {
  /** a schema v2 event; the renderer's Recorder logs it into the session of sessionKey */
  "sandbox.event": { sessionKey: string; type: string; data: unknown };
  "sandbox.progress": { instanceId?: string; message: string; percent?: number };
}

export interface TerminalApi {
  /** One shell per assignment, started in its workdir. */
  open(instanceId: string, opts: { assignmentId: string; cols: number; rows: number }): Promise<{ id: string }>;
  write(id: string, data: string): Promise<void>;
  /** A paste in xterm.js: logs term_paste, then writes the text. */
  paste(id: string, text: string): Promise<void>;
  resize(id: string, cols: number, rows: number): Promise<void>;
  close(id: string): Promise<void>;
}

export interface TerminalEvents {
  "terminal.data": { id: string; data: string };
  "terminal.exit": { id: string; code: number | null };
  /** where keys typed in this terminal belong now; the renderer adds it to key events */
  "terminal.surface": { id: string; surface: "terminal" | "terminal-editor"; path?: string };
}
