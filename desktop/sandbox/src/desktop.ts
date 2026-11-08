/**
 * The desktop app's `sandbox.*` and `terminal.*` IPC methods (api.ts), built on createSandbox.
 *
 * The shell (desktop/app) calls registerSandboxIpc(ctx) from its sandbox
 * module; ctx is its ModuleContext, typed structurally here so this package
 * never imports Electron. Lab definitions come from the catalogue
 * (GET /api/sandbox/my/labs/{id}, format "studentide.sandbox-lab/1"); the
 * student id comes from GET /api/me; ctx.fetch already carries the sign-in.
 */

import type { EngineInfo } from "./engine.ts";
import { createSandbox, type Sandbox } from "./index.ts";
import { homePath, type Instance, type NetworkMode } from "./instance.ts";
import { emptyRecipe, record, type Recipe } from "./recipe.ts";
import { termPaste } from "./events.ts";
import { replayRecipe, type FetchLike, type WorkspaceSync, type Assignment } from "./workspace.ts";
import type { Terminal } from "./terminal.ts";
import { watchProxy } from "./netlog.ts";
import type { OpenedLab, SandboxApi, TerminalApi } from "./api.ts";
import type { TestSpec } from "./run.ts";

export interface IpcContext {
  handle(name: string, fn: (...args: any[]) => unknown): void;
  emit(name: string, data: unknown): void;
  server(): string;
  fetch(path: string, init?: any): Promise<any>;
  userData: string;
}

export interface SandboxIpcOptions {
  /** the installer's saved engine (engine.json), or null when none is set up */
  engine: () => EngineInfo | null | Promise<EngineInfo | null>;
  /** thrown as the shell's DesktopError (its fail()) so the renderer shows title + fix */
  fail: (info: { code: string; title: string; fix?: string; detail?: string }) => never;
}

interface LabDef {
  id: string;
  subject: { id: string; code?: string };
  environment: { image: string; digest?: string | null; resources?: { cpus?: number; memory_mb?: number; disk_gb?: number; pids?: number } };
  instance?: { name?: string; volume?: string };
  network: NetworkMode;
  assignments: Array<{
    id: string; title: string; workdir: string; run: string; open?: string[];
    files?: Array<{ path: string; content: string; executable?: boolean }>; tests?: TestSpec;
  }>;
}

interface OpenLabState {
  def: LabDef;
  instance: Instance;
  sync: WorkspaceSync;
  recipe: Recipe;
  /** session key of the assignment used last; instance-wide events (net_conn) go there */
  active: string;
  stopNet?: () => void;
}

export function registerSandboxIpc(ctx: IpcContext, o: SandboxIpcOptions): { shutdown(): Promise<void> } {
  let sandbox: Sandbox | null = null;
  const labs = new Map<string, OpenLabState>(); // by instance name
  const terms = new Map<string, Terminal>();

  const fetchLike: FetchLike = (url, init) => ctx.fetch(url.startsWith(ctx.server()) ? url.slice(ctx.server().length) : url, init);

  async function sb(): Promise<Sandbox> {
    if (sandbox) return sandbox;
    const engine = await o.engine();
    if (!engine) o.fail({ code: "no_engine", title: "The lab engine is not set up on this computer.", fix: "Run the Student IDE installer, or use a machine that passes the setup check." });
    sandbox = createSandbox({ engine: engine!, dataDir: ctx.userData, onEvent: (sessionKey, ev) => ctx.emit("sandbox.event", { sessionKey, ...ev }) });
    sandbox.watchIdle();
    return sandbox;
  }

  function lab(instanceId: string): OpenLabState {
    const l = labs.get(instanceId);
    if (!l) o.fail({ code: "not_open", title: "This lab is not open.", fix: "Open the lab again." });
    return l!;
  }

  function asg(l: OpenLabState, assignmentId: string) {
    const a = l.def.assignments.find((x) => x.id === assignmentId);
    if (!a) o.fail({ code: "no_assignment", title: "This assignment is not in the lab.", fix: "Reload the lab." });
    return a!;
  }

  const ref = (l: OpenLabState, a: { id: string; workdir: string }): Assignment => ({ labId: l.def.id, assignmentId: a.id, workdir: a.workdir });
  const keyOf2 = (labId: string, assignmentId: string) => `${labId}/${assignmentId}`;
  const keyOf = (l: OpenLabState, assignmentId: string) => {
    l.active = keyOf2(l.def.id, assignmentId);
    return l.active;
  };

  /** the assignment whose folder holds this path, if any */
  function owner(l: OpenLabState, path: string) {
    const p = homePath(path);
    return l.def.assignments.find((a) => p === a.workdir || p.startsWith(`${a.workdir}/`));
  }

  async function json<T>(path: string): Promise<T> {
    const r = await ctx.fetch(path);
    if (!r.ok) o.fail({ code: `http_${r.status}`, title: r.status === 401 ? "Sign in again." : "The server did not give the lab.", detail: `${path}: ${r.status}` });
    return (await r.json()) as T;
  }

  async function replay(l: OpenLabState, instanceId: string): Promise<OpenedLab["setup"]> {
    if (!l.recipe.steps.length) return null;
    ctx.emit("sandbox.progress", { instanceId, message: `Restoring your setup: ${l.recipe.steps.length} package command(s)…` });
    const r = await replayRecipe(l.instance, l.recipe, (line) => ctx.emit("sandbox.progress", { instanceId, message: line }));
    return { replayed: r.total, ok: r.ok };
  }

  const api: SandboxApi = {
    async setupCheck() {
      const engine = await o.engine();
      if (!engine) return { ok: false, checks: [{ id: "engine.cli", ok: false, severity: "error", message: "The lab engine is not set up on this computer.", fix: "Run the Student IDE installer." }] };
      return (await sb()).setupCheck();
    },

    async openLab(labId) {
      const s = await sb();
      const me = await json<{ student_id: string }>("/api/me");
      const def = await json<LabDef>(`/api/sandbox/my/labs/${encodeURIComponent(labId)}`);
      const res = def.environment.resources ?? {};
      const instance = s.instance({
        studentId: me.student_id, subjectId: def.subject.id, image: def.environment.image, digest: def.environment.digest,
        network: def.network, hostname: def.subject.code ?? def.subject.id, name: def.instance?.name, volume: def.instance?.volume,
        limits: { cpus: res.cpus, memoryMb: res.memory_mb, diskGb: res.disk_gb, pids: res.pids },
      });
      const id = instance.name;
      ctx.emit("sandbox.progress", { instanceId: id, message: "Getting the lab environment ready…", percent: 5 });
      await instance.ensureImage((line) => ctx.emit("sandbox.progress", { instanceId: id, message: line }));
      ctx.emit("sandbox.progress", { instanceId: id, message: "Starting your Linux instance…", percent: 60 });
      const made = await instance.start();
      const sync = s.workspace(instance, { serverUrl: ctx.server(), fetch: fetchLike, studentId: me.student_id });
      sync.onError = (e) => ctx.emit("sandbox.progress", { instanceId: id, message: `Saving to the server failed; retrying on the next change (${String((e as Error)?.message ?? e)})` });
      const recipe = await sync.getRecipe(def.subject.id).catch(() => emptyRecipe());
      labs.get(id)?.stopNet?.();
      const l: OpenLabState = { def, instance, sync, recipe, active: keyOf2(def.id, def.assignments[0]?.id ?? "") };
      labs.set(id, l);
      if (def.network === "registries") {
        l.stopNet = watchProxy(instance, (ev) => ctx.emit("sandbox.event", { sessionKey: l.active, ...ev }));
      }
      const setup = made === "created" ? await replay(l, id) : null;
      ctx.emit("sandbox.progress", { instanceId: id, message: "Bringing back your files…", percent: 85 });
      const assignments: OpenedLab["assignments"] = [];
      for (const a of def.assignments) {
        const files = await sync.open(ref(l, a), a.files ?? []);
        assignments.push({ id: a.id, title: a.title, workdir: a.workdir, sessionKey: keyOf2(def.id, a.id), files, open: a.open ?? [] });
      }
      ctx.emit("sandbox.progress", { instanceId: id, message: "Ready", percent: 100 });
      return { instanceId: id, labId: def.id, subjectId: def.subject.id, limitsEnforced: instance.limitsEnforced, network: def.network, setup, assignments };
    },

    async stop(instanceId) {
      const l = lab(instanceId);
      l.stopNet?.();
      await l.sync.flushAll();
      for (const [tid, t] of terms) if (t.instance === l.instance) { t.close(); terms.delete(tid); }
      await l.instance.stop();
    },

    async reset(instanceId) {
      const l = lab(instanceId);
      await l.sync.flushAll();
      await l.instance.reset();
      return replay(l, instanceId);
    },

    async stats(instanceId) {
      const l = lab(instanceId);
      const [st, s] = await Promise.all([l.instance.status(), l.instance.stats()]);
      return { state: st.state, ...s };
    },

    listFiles: (instanceId, dir) => lab(instanceId).instance.listFiles(dir),
    readFile: async (instanceId, path) => (await lab(instanceId).instance.readFile(path)).toString("utf8"),

    async writeFile(instanceId, path, content) {
      const l = lab(instanceId);
      await l.instance.writeFile(path, content);
      const a = owner(l, path);
      if (a) l.sync.changed(ref(l, a));
    },

    async run(instanceId, assignmentId, opts = {}) {
      const l = lab(instanceId);
      const a = asg(l, assignmentId);
      const r = await (await sb()).run(l.instance, keyOf(l, a.id), { workdir: a.workdir, command: a.run, stdin: opts.stdin, timeoutMs: opts.timeoutMs ?? (a.tests?.timeout_s ?? 10) * 1000 });
      l.sync.upload(ref(l, a), { reason: "run" }).catch((e) => l.sync.onError(e, ref(l, a)));
      return r;
    },

    async test(instanceId, assignmentId) {
      const l = lab(instanceId);
      const a = asg(l, assignmentId);
      if (!a.tests) return [];
      return (await sb()).runTests(l.instance, keyOf(l, a.id), a.workdir, a.run, a.tests);
    },

    async submit(instanceId, assignmentId) {
      const l = lab(instanceId);
      const a = asg(l, assignmentId);
      try {
        return { sha256: await l.sync.upload(ref(l, a), { reason: "submit" }) };
      } catch (e) {
        return o.fail({ code: "submit_failed", title: "Your work could not be sent to the server.", fix: "Check the connection and submit again; nothing is lost.", detail: String((e as Error)?.message ?? e) });
      }
    },

    async recipe(instanceId) {
      return { steps: lab(instanceId).recipe.steps };
    },
  };

  const term: TerminalApi = {
    async open(instanceId, opts) {
      const l = lab(instanceId);
      const a = asg(l, opts.assignmentId);
      const s = await sb();
      let surface = "terminal";
      const t = s.terminal(l.instance, keyOf(l, a.id), {
        cwd: a.workdir, cols: opts.cols, rows: opts.rows,
        onPackageCommand: (command, cwd) => {
          record(l.recipe, command, cwd);
          l.sync.putRecipe(l.def.subject.id, l.recipe).catch(() => {});
        },
      });
      terms.set(t.id, t);
      t.on("data", (data: string) => ctx.emit("terminal.data", { id: t.id, data }));
      t.on("exit", (code: number | null) => {
        terms.delete(t.id);
        ctx.emit("terminal.exit", { id: t.id, code });
      });
      t.on("event", (ev: { type: string; data: Record<string, unknown> }) => {
        const now = t.surface();
        if (now.surface !== surface) {
          surface = now.surface;
          ctx.emit("terminal.surface", { id: t.id, ...now });
        }
        // a command that ended may have changed files in any assignment folder
        if (ev.type === "term_cmd" && ev.data.phase === "end") {
          for (const x of l.def.assignments) l.sync.changed(ref(l, x));
        }
      });
      return { id: t.id };
    },
    async write(id, data) {
      terms.get(id)?.write(data);
    },
    async paste(id, text) {
      const t = terms.get(id);
      if (!t) return;
      const l = [...labs.values()].find((x) => x.instance === t.instance);
      const a = l?.def.assignments.find((x) => x.workdir === t.cwd);
      if (l && a) ctx.emit("sandbox.event", { sessionKey: keyOf(l, a.id), ...termPaste(t.id, text) });
      t.write(text);
    },
    resize: async (id, cols, rows) => terms.get(id)?.resize(cols, rows),
    async close(id) {
      terms.get(id)?.close();
      terms.delete(id);
    },
  };

  for (const [m, fn] of Object.entries(api)) ctx.handle(`sandbox.${m}`, fn as (...a: any[]) => unknown);
  for (const [m, fn] of Object.entries(term)) ctx.handle(`terminal.${m}`, fn as (...a: any[]) => unknown);

  return {
    async shutdown() {
      for (const l of labs.values()) {
        l.stopNet?.();
        await l.sync.flushAll().catch(() => {});
      }
      for (const t of terms.values()) t.close();
      await sandbox?.shutdown();
    },
  };
}
