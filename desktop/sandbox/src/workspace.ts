/**
 * Work that follows the student: workspace snapshots and the setup recipe.
 *
 * Each assignment folder is packed as a gzipped tarball (build outputs left
 * out, capped at 5 MB) and uploaded to the server about 10 s after the last
 * change, on every Run and on Submit. Opening the lab on another machine
 * restores the latest snapshot (plan 3.2). The setup recipe (recipe.ts) is
 * synced per subject and replayed on a fresh instance. The server side is
 * backend/studentide/workspaces.py.
 *
 * Nothing is ever silently lost: if both this machine and the server changed
 * since the last sync, the server copy is restored and the local files are
 * kept next to it in `<workdir>.local-<time>`.
 */

import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { homePath, type Instance } from "./instance.ts";
import { emptyRecipe, replayScript, shq, type Recipe } from "./recipe.ts";
import { DEFAULT_EXCLUDES, workdirHash } from "./run.ts";

export const MAX_SNAPSHOT = 5 * 1024 * 1024;
export const UPLOAD_DELAY_MS = 10_000;

export class SnapshotTooLarge extends Error {
  readonly bytes: number;
  constructor(bytes: number) {
    super(`workspace is larger than ${MAX_SNAPSHOT / 1024 / 1024} MB after leaving out build outputs`);
    this.bytes = bytes;
  }
}

export async function snapshot(instance: Instance, workdir: string, excludes = DEFAULT_EXCLUDES): Promise<Buffer> {
  const w = homePath(workdir);
  const ex = excludes.map((e) => `--exclude=${shq(e)}`).join(" ");
  const r = await instance.exec(["sh", "-c", `tar -czf - ${ex} -C ${shq(w)} .`], { timeoutMs: 60_000, maxStdout: MAX_SNAPSHOT + 1 });
  if (r.code !== 0 && r.stdout.length <= MAX_SNAPSHOT) throw new Error(`could not pack ${w}: ${r.stderr.trim()}`);
  if (r.stdout.length > MAX_SNAPSHOT) throw new SnapshotTooLarge(r.stdout.length);
  return r.stdout;
}

export async function restore(instance: Instance, workdir: string, tgz: Buffer): Promise<void> {
  const w = homePath(workdir);
  const r = await instance.exec(["sh", "-c", `mkdir -p ${shq(w)} && tar -xzf - -C ${shq(w)}`], { stdin: tgz, timeoutMs: 60_000 });
  if (r.code !== 0) throw new Error(`could not restore ${w}: ${r.stderr.trim()}`);
}

// ---- server sync ----

/** Fetch bound to the signed-in session (the shell injects Electron's session.fetch). */
export type FetchLike = (url: string, init?: { method?: string; headers?: Record<string, string>; body?: Uint8Array | string }) => Promise<{
  ok: boolean; status: number; json(): Promise<any>; arrayBuffer(): Promise<ArrayBuffer>;
}>;

export interface Assignment {
  labId: string;
  assignmentId: string;
  workdir: string;
}

export interface SyncState {
  /** content hash last uploaded or restored, per "<lab>/<assignment>" */
  synced: Record<string, string>;
  recipeAt: Record<string, number>;
}

export type OpenOutcome = "restored" | "kept" | "conflict-kept-both" | "new";

export class WorkspaceSync {
  readonly instance: Instance;
  readonly base: string;
  readonly fetch: FetchLike;
  readonly stateFile: string;
  readonly studentId: string;
  private state: SyncState = { synced: {}, recipeAt: {} };
  private timers = new Map<string, NodeJS.Timeout>();
  private loaded = false;
  onError: (e: unknown, a: Assignment) => void = () => {};

  constructor(o: { instance: Instance; serverUrl: string; fetch: FetchLike; dataDir: string; studentId: string }) {
    this.instance = o.instance;
    this.studentId = o.studentId;
    this.base = o.serverUrl.replace(/\/+$/, "");
    this.fetch = o.fetch;
    this.stateFile = join(o.dataDir, "sandbox", `sync-${o.instance.name}.json`);
  }

  private key = (a: Assignment): string => `${a.labId}/${a.assignmentId}`;
  private q = (): string => `?student_id=${encodeURIComponent(this.studentId)}`;
  private url = (a: Assignment, suffix = ""): string =>
    `${this.base}/api/workspaces/${encodeURIComponent(a.labId)}/${encodeURIComponent(a.assignmentId)}${suffix}${this.q()}`;

  private async load(): Promise<void> {
    if (this.loaded) return;
    try {
      this.state = { synced: {}, recipeAt: {}, ...JSON.parse(await readFile(this.stateFile, "utf8")) };
    } catch {
      /* first run on this machine */
    }
    this.loaded = true;
  }

  private async save(): Promise<void> {
    await mkdir(dirname(this.stateFile), { recursive: true });
    await writeFile(this.stateFile, JSON.stringify(this.state));
  }

  /**
   * Call when an assignment opens. Seeds starter files for a brand-new
   * assignment, otherwise reconciles this machine with the server.
   */
  async open(a: Assignment, starter: Array<{ path: string; content: string; executable?: boolean }> = []): Promise<OpenOutcome> {
    await this.load();
    const k = this.key(a);
    const metaRes = await this.fetch(this.url(a, "/meta"));
    const server: { sha256: string } | null = metaRes.ok ? await metaRes.json() : null;
    const exists = (await this.instance.exec(["test", "-d", homePath(a.workdir)], { timeoutMs: 30_000 })).code === 0;

    if (!exists) {
      if (server) {
        await this.download(a);
        this.state.synced[k] = server.sha256;
        await this.save();
        return "restored";
      }
      await this.instance.seedAssignment(a.workdir, starter);
      return "new";
    }
    if (!server) return "kept"; // first upload happens on the first change
    const local = await workdirHash(this.instance, a.workdir);
    const last = this.state.synced[k];
    if (local === server.sha256) {
      this.state.synced[k] = local;
      await this.save();
      return "kept";
    }
    if (last === server.sha256) return "kept"; // only this machine changed; next upload sends it
    const localChanged = last !== undefined && local !== last;
    const unknownHistory = last === undefined; // folder here, never synced from this machine
    if (localChanged || unknownHistory) {
      const keep = `${homePath(a.workdir)}.local-${new Date().toISOString().replace(/[:.]/g, "-")}`;
      await this.instance.exec(["mv", homePath(a.workdir), keep], { timeoutMs: 30_000 });
      await this.download(a);
      this.state.synced[k] = server.sha256;
      await this.save();
      return "conflict-kept-both";
    }
    await this.instance.exec(["rm", "-rf", homePath(a.workdir)], { timeoutMs: 30_000 });
    await this.download(a);
    this.state.synced[k] = server.sha256;
    await this.save();
    return "restored";
  }

  private async download(a: Assignment): Promise<void> {
    const r = await this.fetch(this.url(a));
    if (!r.ok) throw new Error(`workspace download failed (${r.status})`);
    await restore(this.instance, a.workdir, Buffer.from(await r.arrayBuffer()));
  }

  /** Something changed (editor save, terminal command ended): upload after a quiet period. */
  changed(a: Assignment, delayMs = UPLOAD_DELAY_MS): void {
    const k = this.key(a);
    clearTimeout(this.timers.get(k));
    this.timers.set(k, setTimeout(() => {
      this.timers.delete(k);
      this.upload(a).catch((e) => this.onError(e, a));
    }, delayMs));
  }

  /** Upload now if the content changed (on Run and Submit). Returns the content hash. */
  async upload(a: Assignment, opts: { force?: boolean; reason?: "change" | "run" | "submit" } = {}): Promise<string> {
    await this.load();
    const k = this.key(a);
    clearTimeout(this.timers.get(k));
    this.timers.delete(k);
    const hash = await workdirHash(this.instance, a.workdir);
    const reason = opts.reason ?? "change";
    if (!opts.force && reason !== "submit" && this.state.synced[k] === hash) return hash;
    const tgz = await snapshot(this.instance, a.workdir);
    const r = await this.fetch(this.url(a), {
      method: "PUT",
      headers: { "Content-Type": "application/gzip", "X-Workspace-Sha256": hash, "X-Workspace-Reason": reason, ...(this.state.synced[k] ? { "X-Workspace-Parent": this.state.synced[k]! } : {}) },
      body: new Uint8Array(tgz),
    });
    // the server's reason (lab closed, not on the roster) is what the student needs to read
    if (!r.ok) throw new Error(await r.json().then((j) => (typeof j?.detail === "string" ? j.detail : ""), () => "") || `workspace upload failed (${r.status})`);
    this.state.synced[k] = hash;
    await this.save();
    return hash;
  }

  async flushAll(): Promise<void> {
    const pending = [...this.timers.keys()];
    for (const k of pending) {
      const [labId, assignmentId] = k.split("/") as [string, string];
      clearTimeout(this.timers.get(k));
      this.timers.delete(k);
      // workdir follows the lab definition rule
      await this.upload({ labId, assignmentId, workdir: `/home/student/labs/${labId}/${assignmentId}` }).catch(() => {});
    }
  }

  // ---- setup recipe, per subject ----

  private recipeUrl = (subjectId: string): string => `${this.base}/api/workspaces/recipes/${encodeURIComponent(subjectId)}${this.q()}`;

  async getRecipe(subjectId: string): Promise<Recipe> {
    const r = await this.fetch(this.recipeUrl(subjectId));
    if (r.status === 404) return emptyRecipe();
    if (!r.ok) throw new Error(`recipe download failed (${r.status})`);
    const j = await r.json();
    return { version: 1, steps: Array.isArray(j.steps) ? j.steps : [] };
  }

  async putRecipe(subjectId: string, recipe: Recipe): Promise<void> {
    const r = await this.fetch(this.recipeUrl(subjectId), {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(recipe),
    });
    if (!r.ok) throw new Error(`recipe upload failed (${r.status})`);
  }
}

/** Replay a recipe in a fresh instance ("Restoring your setup: installing 4 packages…"). */
export async function replayRecipe(instance: Instance, recipe: Recipe, onLine?: (line: string) => void): Promise<{ ok: number; total: number }> {
  if (!recipe.steps.length) return { ok: 0, total: 0 };
  const r = await instance.exec(["bash", "-l"], { stdin: replayScript(recipe), timeoutMs: 30 * 60_000 });
  const lines = r.stdout.toString("utf8").split("\n");
  lines.filter((l) => l.startsWith("[setup]")).forEach((l) => onLine?.(l));
  const m = /\[setup\] done (\d+)\/(\d+)/.exec(lines.join("\n"));
  return { ok: Number(m?.[1] ?? 0), total: Number(m?.[2] ?? recipe.steps.length) };
}
