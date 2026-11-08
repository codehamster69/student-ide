// Buffers events and uploads them in batches. Field meanings are documented
// in backend/studentide/schema.py and docs/event-schema.md.

export const SCHEMA_VERSION = 3; // v2 and v3 are additive (Sandbox Labs); the server accepts 1, 2 and 3
const FLUSH_MS = 2000;
const MAX_BATCH = 500;

export type EventType =
  | "key" | "edit" | "clipboard" | "cursor" | "run"
  | "snapshot" | "focus" | "session_start" | "session_end"
  // v2, desktop Sandbox Labs (built by desktop/sandbox, logged here by the renderer)
  | "term_cmd" | "term_output" | "term_paste" | "pkg_install" | "net_conn"
  // v3, the sidecar watcher
  | "fs_change" | "port_open";

export interface RecordedEvent {
  seq: number;
  t: number; // ms since session start
  type: EventType;
  data: Record<string, unknown>;
}

export class Recorder {
  private seq = 0;
  private queue: RecordedEvent[] = [];
  private inFlight = false;
  private timer: number | undefined;
  private stopped = false;
  // performance.now() at session start; DOM event.timeStamp shares this clock.
  readonly t0 = performance.now();
  onStatus: (pending: number, ok: boolean) => void = () => {};

  constructor(private sessionId: string) {
    this.timer = window.setInterval(() => void this.flush(), FLUSH_MS);
  }

  /** Record an event. `timeStamp` is a performance.now()-clock value (e.g. KeyboardEvent.timeStamp). */
  log(type: EventType, data: Record<string, unknown>, timeStamp?: number): void {
    if (this.stopped) return;
    const t = Math.max(0, (timeStamp ?? performance.now()) - this.t0);
    this.queue.push({ seq: this.seq++, t: Math.round(t * 1000) / 1000, type, data });
    if (this.queue.length >= MAX_BATCH) void this.flush();
  }

  get url(): string {
    return `/api/sessions/${this.sessionId}/events`;
  }

  async flush(): Promise<void> {
    if (this.inFlight || this.queue.length === 0) return;
    this.inFlight = true;
    const batch = this.queue.slice(0, MAX_BATCH);
    try {
      const res = await fetch(this.url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ schema_version: SCHEMA_VERSION, events: batch }),
      });
      if (!res.ok) throw new Error(`upload failed: ${res.status}`);
      const body = await res.json();
      for (const r of body.rejected ?? []) console.warn("event rejected by server", r);
      // Drop what was sent (accepted or rejected); keep anything logged meanwhile.
      const sent = new Set(batch.map((e) => e.seq));
      this.queue = this.queue.filter((e) => !sent.has(e.seq));
      this.onStatus(this.queue.length, true);
    } catch (err) {
      console.warn(err);
      this.onStatus(this.queue.length, false); // retried on the next tick; server ignores duplicates
    } finally {
      this.inFlight = false;
    }
    if (this.queue.length >= MAX_BATCH) void this.flush();
  }

  /** Flush everything and stop recording (normal finish). */
  async close(): Promise<void> {
    this.stopped = true;
    window.clearInterval(this.timer);
    for (let tries = 0; this.queue.length && tries < 10; tries++) {
      while (this.inFlight) await new Promise((r) => setTimeout(r, 50));
      await this.flush();
      if (this.queue.length) await new Promise((r) => setTimeout(r, 500));
    }
  }

  /** Last-chance upload while the page is going away. */
  beacon(): void {
    this.stopped = true;
    window.clearInterval(this.timer);
    if (!this.queue.length) return;
    const body = JSON.stringify({ schema_version: SCHEMA_VERSION, events: this.queue });
    if (!navigator.sendBeacon(this.url, body)) {
      void fetch(this.url, { method: "POST", body, keepalive: true });
    }
  }
}
