/**
 * The desktop app's event journal (plan 4.3 "Online required, with a short
 * reconnect buffer", 4.4 "Events dropped, reordered or edited").
 *
 * The renderer's Recorder hands every batch to the main process
 * (`journal.append`), which appends it to `<dir>/<session>.jsonl` before
 * acknowledging (fsync every 500 ms) and uploads from there. So a dropped
 * connection, a crash or a quit loses nothing: the next start picks up where
 * the file left off.
 *
 * Uploads are signed and hash-chained (backend/studentide/batches.py): each
 * install has an Ed25519 key (kept encrypted by the shell's KeyStore, i.e.
 * Electron safeStorage), registered once per student with POST /api/devices.
 * A batch's payload is the exact JSON text that is signed; its sha256 is the
 * next batch's prev_hash.
 *
 * Offline: the student keeps working for OFFLINE_LIMIT_MS (5 minutes) with a
 * calm "Reconnecting…" pill; after that `readOnly` turns on until the server
 * answers again. The first batch after an outage carries how long it lasted
 * (offline_ms), so the review shows the gap as a gap, never as a flag.
 *
 * Plain Node (no Electron), so it is tested in this package; desktop/app's
 * journal module wires it to the cookie-carrying fetch and safeStorage.
 */

import { closeSync, existsSync, fsyncSync, mkdirSync, openSync, readFileSync, readdirSync, renameSync, unlinkSync, writeFileSync, writeSync } from "node:fs";
import { join } from "node:path";
import { createPrivateKey, createPublicKey, generateKeyPairSync, sign, createHash, type KeyObject } from "node:crypto";

export const OFFLINE_LIMIT_MS = 5 * 60_000;
export const FSYNC_MS = 500;
export const TICK_MS = 1000;
export const PING_MS = 5000;
export const MAX_BATCH = 500;
export const SCHEMA_VERSION = 3;

export interface JournalState {
  online: boolean;
  /** Date.now() when the connection was lost; null while online */
  offlineSince: number | null;
  /** past the 5-minute buffer: editor and terminal stop taking input until the server answers */
  readOnly: boolean;
  /** events written here and not yet accepted by the server */
  pending: number;
  /** ms of buffer left before read-only (null while online) */
  remainingMs: number | null;
}

export interface KeyStore {
  /** the saved (decrypted) PKCS#8 DER private key, or null on first run */
  load(): Buffer | null;
  save(der: Buffer): void;
}

export interface JournalOptions {
  dir: string;
  /** fetch to the server with the app's sign-in (path relative to the server) */
  fetch(path: string, init?: { method?: string; headers?: Record<string, string>; body?: string }): Promise<{ ok: boolean; status: number; json(): Promise<any> }>;
  keys: KeyStore;
  appVersion?: string;
  platform?: string;
  onState?(s: JournalState): void;
  now?(): number;
  mono?(): number;
  offlineLimitMs?: number;
}

interface SessionFile {
  id: string;
  fd: number;
  dirty: boolean;
  /** events in the file, in order */
  lines: string[];
  /** how many of `lines` the server has accepted */
  sent: number;
  batchSeq: number;
  prevHash: string;
  closed: boolean;
  /** server refused the session (gone, not yours): stop trying */
  dead: boolean;
}

const b64 = (b: Buffer) => b.toString("base64");

export class Journal {
  private o: JournalOptions;
  private sessions = new Map<string, SessionFile>();
  private key: KeyObject;
  private pubB64: string;
  private devices: Record<string, string> = {}; // student id -> device id
  private student: string | null = null;
  private online = true;
  private offlineSince: number | null = null;
  private outageMs = 0; // length of the outage that just ended, sent once
  private lastContact = 0;
  private busy = false;
  private timers: NodeJS.Timeout[] = [];
  private lastState = "";

  constructor(o: JournalOptions) {
    this.o = o;
    mkdirSync(o.dir, { recursive: true });
    let der = o.keys.load();
    if (!der) {
      der = generateKeyPairSync("ed25519").privateKey.export({ format: "der", type: "pkcs8" }) as Buffer;
      o.keys.save(der);
    }
    this.key = createPrivateKey({ key: der, format: "der", type: "pkcs8" });
    const jwk = createPublicKey(this.key).export({ format: "jwk" }) as { x: string };
    this.pubB64 = b64(Buffer.from(jwk.x, "base64url"));
    try { this.devices = JSON.parse(readFileSync(join(o.dir, "devices.json"), "utf8")); } catch { /* first run */ }
    this.reopen();
  }

  private now = () => this.o.now?.() ?? Date.now();
  private get limit() { return this.o.offlineLimitMs ?? OFFLINE_LIMIT_MS; }

  /** Sessions left from an earlier run (crash, quit while offline) are uploaded too. */
  private reopen() {
    for (const f of readdirSync(this.o.dir)) {
      const m = /^([0-9a-zA-Z_-]{1,64})\.jsonl$/.exec(f);
      if (m) this.file(m[1]!);
    }
  }

  private file(id: string): SessionFile {
    let s = this.sessions.get(id);
    if (s) return s;
    if (!/^[0-9a-zA-Z_-]{1,64}$/.test(id)) throw new Error("bad session id");
    const path = join(this.o.dir, `${id}.jsonl`);
    const lines = existsSync(path) ? readFileSync(path, "utf8").split("\n").filter(Boolean) : [];
    let meta = { sent: 0, batchSeq: 0, prevHash: "", closed: false };
    try { meta = { ...meta, ...JSON.parse(readFileSync(join(this.o.dir, `${id}.json`), "utf8")) }; } catch { /* new */ }
    s = { id, fd: openSync(path, "a"), dirty: false, lines, ...meta, dead: false };
    this.sessions.set(id, s);
    return s;
  }

  private saveMeta(s: SessionFile) {
    const tmp = join(this.o.dir, `${s.id}.json.tmp`);
    writeFileSync(tmp, JSON.stringify({ sent: s.sent, batchSeq: s.batchSeq, prevHash: s.prevHash, closed: s.closed }));
    renameSync(tmp, join(this.o.dir, `${s.id}.json`));
  }

  /** Write events to disk (acknowledged once written; fsync follows within FSYNC_MS). */
  append(sessionId: string, events: unknown[]): JournalState {
    const s = this.file(sessionId);
    if (events.length) {
      const text = events.map((e) => JSON.stringify(e)).join("\n") + "\n";
      writeSync(s.fd, text);
      s.lines.push(...text.trimEnd().split("\n"));
      s.dirty = true;
    }
    return this.state();
  }

  /** The renderer finished this session: upload the rest, then delete the files. */
  close(sessionId: string): void {
    const s = this.sessions.get(sessionId);
    if (!s) return;
    s.closed = true;
    this.saveMeta(s);
  }

  state(): JournalState {
    let pending = 0;
    for (const s of this.sessions.values()) if (!s.dead) pending += s.lines.length - s.sent;
    const since = this.offlineSince;
    const remaining = since === null ? null : Math.max(0, this.limit - (this.now() - since));
    return { online: this.online, offlineSince: since, readOnly: remaining === 0, pending, remainingMs: remaining };
  }

  private emit() {
    const s = this.state();
    const k = JSON.stringify([s.online, s.offlineSince, s.readOnly]);
    if (k !== this.lastState) {
      this.lastState = k;
      this.o.onState?.(s);
    }
  }

  start(): void {
    this.timers.push(setInterval(() => this.fsync(), FSYNC_MS));
    this.timers.push(setInterval(() => void this.tick(), TICK_MS));
  }

  async stop(): Promise<void> {
    for (const t of this.timers) clearInterval(t);
    this.timers = [];
    await this.tick().catch(() => {});
    this.fsync();
    for (const s of this.sessions.values()) closeSync(s.fd);
    this.sessions.clear();
  }

  fsync(): void {
    for (const s of this.sessions.values()) {
      if (!s.dirty) continue;
      try { fsyncSync(s.fd); } catch { /* the next write retries */ }
      s.dirty = false;
    }
  }

  private wentOffline() {
    if (this.online) {
      this.online = false;
      this.offlineSince = this.now();
    }
  }

  private cameBack() {
    if (!this.online && this.offlineSince !== null) this.outageMs = this.now() - this.offlineSince;
    this.online = true;
    this.offlineSince = null;
    this.lastContact = this.now();
  }

  private async deviceId(): Promise<string> {
    if (!this.student) {
      const r = await this.o.fetch("/api/me");
      if (!r.ok) throw new Error(`me ${r.status}`);
      this.student = String((await r.json()).student_id ?? "");
      if (!this.student) throw new Error("not signed in");
    }
    const known = this.devices[this.student];
    if (known) return known;
    const r = await this.o.fetch(`/api/devices?student_id=${encodeURIComponent(this.student)}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ public_key: this.pubB64, app_version: this.o.appVersion ?? "", platform: this.o.platform ?? "" }),
    });
    if (!r.ok) throw new Error(`devices ${r.status}`);
    const id = String((await r.json()).device_id);
    this.devices[this.student] = id;
    writeFileSync(join(this.o.dir, "devices.json"), JSON.stringify(this.devices));
    return id;
  }

  /** One upload round: every session with pending events sends its next batch. */
  async tick(): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    try {
      let sentSomething = false;
      for (const s of [...this.sessions.values()]) {
        if (s.dead) continue;
        while (s.sent < s.lines.length) {
          const ok = await this.sendBatch(s);
          if (!ok) break;
          sentSomething = true;
        }
        if (s.closed && s.sent >= s.lines.length) this.forget(s);
      }
      // nothing to send: still notice an outage (and its end) so the pill and read-only are right
      if (!sentSomething && (!this.online || this.now() - this.lastContact > PING_MS)) {
        try {
          const r = await this.o.fetch("/api/desktop/config");
          if (r.status >= 500) this.wentOffline(); else this.cameBack();
        } catch {
          this.wentOffline();
        }
      }
    } finally {
      this.busy = false;
      this.emit();
    }
  }

  private async sendBatch(s: SessionFile): Promise<boolean> {
    const lines = s.lines.slice(s.sent, s.sent + MAX_BATCH);
    let device: string;
    try {
      device = await this.deviceId();
    } catch {
      this.wentOffline();
      return false;
    }
    const events = lines.map((l) => JSON.parse(l));
    // still offline as far as we know: if this send gets through, the outage ends now
    const outage = !this.online && this.offlineSince !== null ? this.now() - this.offlineSince : this.outageMs;
    const payload = JSON.stringify({
      session_id: s.id, batch_seq: s.batchSeq, prev_hash: s.prevHash, wall_ms: this.now(),
      mono_ms: this.o.mono?.() ?? performance.now(), offline_ms: outage, events,
    });
    const sig = b64(sign(null, Buffer.from(payload, "utf8"), this.key));
    let r;
    try {
      r = await this.o.fetch(`/api/sessions/${s.id}/events`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ schema_version: SCHEMA_VERSION, signed: { device_id: device, payload, sig } }),
      });
    } catch {
      this.wentOffline();
      return false;
    }
    if (r.status === 409 && this.student) {
      delete this.devices[this.student]; // the server forgot this install: register again next round
      return false;
    }
    if (r.status >= 500 || r.status === 0) {
      this.wentOffline();
      return false;
    }
    this.cameBack();
    if (r.status === 401 || r.status === 403 || r.status === 404) {
      s.dead = r.status !== 401; // 401: signed out; kept until the student signs in again
      return false;
    }
    // 2xx, or a 4xx for a batch the server can never take: either way move on, never loop on it
    s.sent += lines.length;
    s.prevHash = createHash("sha256").update(payload, "utf8").digest("hex");
    s.batchSeq += 1;
    this.outageMs = 0;
    this.saveMeta(s);
    return true;
  }

  private forget(s: SessionFile) {
    closeSync(s.fd);
    this.sessions.delete(s.id);
    for (const ext of [".jsonl", ".json"]) {
      try { unlinkSync(join(this.o.dir, s.id + ext)); } catch { /* gone */ }
    }
  }
}
