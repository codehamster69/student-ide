/** `studentDesktop.terminal`: a shell inside a lab instance (owned by the sandbox thread). */

export interface TerminalApi {
  open(instanceId: string, opts: { cwd?: string; cols: number; rows: number }): Promise<{ id: string }>;
  write(id: string, data: string): Promise<void>;
  resize(id: string, cols: number, rows: number): Promise<void>;
  close(id: string): Promise<void>;
}

export interface TerminalEvents {
  "terminal.data": { id: string; data: string };
  "terminal.exit": { id: string; code: number | null };
}
