/**
 * `journal.*`: the event journal in the main process (see shared/api/journal.ts).
 * The private key is kept with Electron safeStorage (the OS keychain) when it is
 * available; otherwise in the app's data folder, and the review shows such
 * installs the same way (signing still proves the batches came in order from one install).
 */

import { app, safeStorage } from "electron";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { Journal, type KeyStore } from "@studentide/sandbox";
import type { DesktopModule } from "../ipc";

function keyStore(userData: string): KeyStore {
  const path = join(userData, "device-key.bin");
  const enc = () => safeStorage.isEncryptionAvailable();
  return {
    load() {
      try {
        const raw = readFileSync(path);
        return raw[0] === 0x45 /* "E" */ ? Buffer.from(safeStorage.decryptString(raw.subarray(1)), "base64") : raw.subarray(1);
      } catch {
        return null;
      }
    },
    save(der) {
      const body = enc() ? Buffer.concat([Buffer.from("E"), safeStorage.encryptString(der.toString("base64"))]) : Buffer.concat([Buffer.from("P"), der]);
      writeFileSync(path, body, { mode: 0o600 });
    },
  };
}

/**
 * What the updater needs to find a safe moment to restart (modules/updates.ts):
 * which recorded sessions are still open and how many events wait for upload.
 * A session counts as open from its first batch until the renderer closes it;
 * one with no batch for OPEN_FOR_MS (left without closing) stops counting.
 */
const OPEN_FOR_MS = 10 * 60 * 1000;
const lastBatch = new Map<string, number>();
let current: Journal | undefined;
export const journalActivity = {
  openSessions(now = Date.now()): number {
    let n = 0;
    for (const [id, at] of lastBatch) { if (now - at < OPEN_FOR_MS) n++; else lastBatch.delete(id); }
    return n;
  },
  pending(): number { return current?.state().pending ?? 0; },
  online(): boolean { return current?.state().online ?? true; },
};

export const journalModule = (): DesktopModule => {
  let j: Journal | undefined;
  return {
    namespace: "journal",
    register(ctx) {
      const get = () => {
        if (j) return j;
        j = new Journal({
          dir: join(ctx.userData, "journal"),
          fetch: (path, init) => ctx.fetch(path, init as RequestInit),
          keys: keyStore(ctx.userData),
          appVersion: app.getVersion(),
          platform: process.platform,
          onState: (s) => ctx.emit("journal.state", s),
        });
        j.start();
        current = j;
        return j;
      };
      ctx.handle("journal.append", (sessionId: string, events: unknown[]) => {
        lastBatch.set(String(sessionId), Date.now());
        return get().append(String(sessionId), Array.isArray(events) ? events : []);
      });
      ctx.handle("journal.close", (sessionId: string) => { lastBatch.delete(String(sessionId)); return get().close(String(sessionId)); });
      ctx.handle("journal.state", () => get().state());
      // events left on disk from an earlier run (quit while offline, crash) go up straight away
      get();
    },
    dispose: () => j?.stop() ?? Promise.resolve(),
  };
};
