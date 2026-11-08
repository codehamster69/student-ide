/**
 * @studentide/sandbox: the local sandbox runtime of Sandbox Labs.
 *
 * Plain Node, no Electron and no native modules: the desktop app's main
 * process imports it (desktop/app/src/main/modules/sandbox.ts calls
 * registerSandboxIpc), the installer imports setupCheck. See
 * docs/sandbox-runtime.md for the whole picture.
 */

import type { spawn } from "node:child_process";
import { Engine, type EngineInfo } from "./engine.ts";
import { setupCheck, type CheckOptions, type CheckReport } from "./doctor.ts";
import { Instance, pullImage, type InstanceSpec } from "./instance.ts";
import { Terminal, type TerminalOptions } from "./terminal.ts";
import { runCommand, runTests, type RunOptions, type TestSpec } from "./run.ts";
import { WorkspaceSync, type FetchLike } from "./workspace.ts";
import type { EventSink } from "./events.ts";

export * from "./engine.ts";
export * from "./instance.ts";
export * from "./terminal.ts";
export * from "./run.ts";
export * from "./workspace.ts";
export * from "./recipe.ts";
export * from "./events.ts";
export * from "./doctor.ts";
export * from "./marks.ts";
export * from "./registries.ts";
export * from "./netlog.ts";
export { registerSandboxIpc, type IpcContext, type SandboxIpcOptions } from "./desktop.ts";
export type * from "./api.ts";

export const IDLE_STOP_MS = 30 * 60_000;

export interface SandboxOptions {
  engine: EngineInfo;
  /** the app's userData directory; sync state lives in <dataDir>/sandbox */
  dataDir: string;
  onEvent?: EventSink;
  spawnFn?: typeof spawn;
}

export interface Sandbox {
  engine: Engine;
  setupCheck(opts?: CheckOptions): Promise<CheckReport>;
  ensureImage(ref: string, onLine?: (line: string) => void): Promise<void>;
  instance(spec: InstanceSpec): Instance;
  terminal(instance: Instance, sessionKey: string, opts?: Omit<TerminalOptions, "onEvent">): Terminal;
  run(instance: Instance, sessionKey: string, opts: Omit<RunOptions, "onEvent">): ReturnType<typeof runCommand>;
  runTests(instance: Instance, sessionKey: string, workdir: string, runCmd: string, spec: TestSpec): ReturnType<typeof runTests>;
  workspace(instance: Instance, o: { serverUrl: string; fetch: FetchLike; studentId: string }): WorkspaceSync;
  /** stop instances idle for longer than idleMs (default 30 min); returns a function that ends the watch */
  watchIdle(idleMs?: number): () => void;
  /** stop every instance this sandbox started (app quit) */
  shutdown(): Promise<void>;
}

export function createSandbox(o: SandboxOptions): Sandbox {
  const engine = new Engine(o.engine, o.spawnFn);
  const instances = new Map<string, Instance>();
  const sink = (key: string) => (ev: Parameters<EventSink>[1]) => o.onEvent?.(key, ev);

  return {
    engine,
    setupCheck: (opts) => setupCheck(o.engine, { dataDir: o.dataDir, spawnFn: o.spawnFn, ...opts }),
    async ensureImage(ref, onLine) {
      if (!(await engine.exists("image", ref))) await pullImage(engine, ref, onLine);
    },
    instance(spec) {
      const inst = new Instance(engine, spec);
      const have = instances.get(inst.name);
      if (have && have.specHash === inst.specHash) return have;
      instances.set(inst.name, inst);
      return inst;
    },
    terminal: (inst, key, opts = {}) => new Terminal(inst, { ...opts, onEvent: sink(key) }).open(),
    run: (inst, key, opts) => runCommand(inst, { ...opts, onEvent: sink(key) }),
    runTests: (inst, key, workdir, cmd, spec) => runTests(inst, workdir, cmd, spec, sink(key)),
    workspace: (inst, w) => new WorkspaceSync({ instance: inst, dataDir: o.dataDir, ...w }),
    watchIdle(idleMs = IDLE_STOP_MS) {
      const t = setInterval(() => {
        for (const inst of instances.values()) {
          if (inst.idleMs() > idleMs) inst.status().then((s) => (s.state === "running" ? inst.stop() : undefined)).catch(() => {});
        }
      }, 60_000);
      t.unref?.();
      return () => clearInterval(t);
    },
    async shutdown() {
      await Promise.all([...instances.values()].map((i) => i.stop().catch(() => {})));
    },
  };
}
