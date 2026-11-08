/**
 * IPC plumbing: modules register "<ns>.<method>" handlers here, and only the web app
 * served from the configured server origin may call them. Failures travel as a
 * DesktopError inside the reply (Electron would keep only an Error's message).
 */

import { ipcMain, type IpcMainInvokeEvent, type WebContents } from "electron";
import { CHANNEL_PREFIX, CONTRACT_VERSION, EVENT_CHANNEL, MANIFEST_CHANNEL, type DesktopError, type DesktopEvents, type Manifest } from "../shared/contract";

export type Handler = (...args: any[]) => unknown | Promise<unknown>;
export type Reply = { ok: true; value: unknown } | { ok: false; error: DesktopError };

export class Failure extends Error {
  constructor(public readonly info: DesktopError) { super(info.title); }
}

export const fail = (info: DesktopError): never => { throw new Failure(info); };

export function notImplemented(what: string): never {
  return fail({ code: "not_implemented", title: `${what} is not in this version of the app yet.`, fix: "Update the app." });
}

export interface ModuleContext {
  handle(name: string, fn: Handler): void;
  emit<K extends keyof DesktopEvents>(name: K, data: DesktopEvents[K]): void;
  /** origin the app is locked to, e.g. https://studentide.hokora.xyz */
  server(): string;
  /** fetch to the server with the app's signed-in cookie jar */
  fetch(path: string, init?: RequestInit): Promise<Response>;
  userData: string;
}

export interface DesktopModule {
  namespace: string;
  register(ctx: ModuleContext): void;
}

export class Registry {
  private methods = new Map<string, Handler>();
  private targets = new Set<WebContents>();

  constructor(private allowed: () => string) {
    ipcMain.on(MANIFEST_CHANNEL, (e) => {
      e.returnValue = this.trusted(e.senderFrame?.url) ? this.manifest() : { contract: CONTRACT_VERSION, namespaces: {} };
    });
  }

  manifest(): Manifest {
    const namespaces: Record<string, string[]> = {};
    for (const name of this.methods.keys()) {
      const [ns, method] = name.split(".");
      (namespaces[ns] ??= []).push(method);
    }
    return { contract: CONTRACT_VERSION, namespaces };
  }

  /** Only top-level pages on the server origin get the bridge; iframes and other sites never do. */
  trusted(url: string | undefined): boolean {
    if (!url) return false;
    try { return new URL(url).origin === this.allowed(); } catch { return false; }
  }

  handle(name: string, fn: Handler) {
    if (!/^[a-z]+\.[a-zA-Z]+$/.test(name)) throw new Error(`bad method name ${name}`);
    if (this.methods.has(name)) throw new Error(`${name} registered twice`);
    this.methods.set(name, fn);
    ipcMain.handle(CHANNEL_PREFIX + name, async (e: IpcMainInvokeEvent, ...args: unknown[]): Promise<Reply> => {
      const frame = e.senderFrame;
      if (!frame || frame.parent || !this.trusted(frame.url)) {
        return { ok: false, error: { code: "forbidden", title: "This page may not use the desktop app." } };
      }
      try {
        return { ok: true, value: await fn(...args) };
      } catch (err) {
        if (err instanceof Failure) return { ok: false, error: err.info };
        console.error(`[ipc] ${name} failed`, err);
        return { ok: false, error: { code: "internal", title: "Something went wrong in the desktop app.", detail: String((err as Error)?.message ?? err) } };
      }
    });
  }

  attach(wc: WebContents) {
    this.targets.add(wc);
    wc.once("destroyed", () => this.targets.delete(wc));
  }

  emit(name: string, data: unknown) {
    for (const wc of this.targets) {
      if (!wc.isDestroyed() && this.trusted(wc.getURL())) wc.send(EVENT_CHANNEL, { name, data });
    }
  }
}
