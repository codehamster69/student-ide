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
        return j;
      };
      ctx.handle("journal.append", (sessionId: string, events: unknown[]) => get().append(String(sessionId), Array.isArray(events) ? events : []));
      ctx.handle("journal.close", (sessionId: string) => get().close(String(sessionId)));
      ctx.handle("journal.state", () => get().state());
      // events left on disk from an earlier run (quit while offline, crash) go up straight away
      get();
    },
    dispose: () => j?.stop() ?? Promise.resolve(),
  };
};
