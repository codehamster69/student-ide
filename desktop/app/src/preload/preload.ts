/**
 * Preload: builds `window.studentDesktop` from the method list main sends once.
 * It runs sandboxed, so it imports only `electron` (types from shared/ are erased).
 * Main exposes methods only to the server's own top-level page; anywhere else the
 * manifest is empty and the bridge is absent, so the web app behaves as in a browser.
 */

import { contextBridge, ipcRenderer } from "electron";
import type { DesktopError, Manifest } from "../shared/contract";

const PREFIX = "sid:";
const manifest = ipcRenderer.sendSync("sid:manifest") as Manifest;

type Reply = { ok: true; value: unknown } | { ok: false; error: DesktopError };

if (Object.keys(manifest.namespaces).length) {
  const listeners = new Map<string, Set<(data: unknown) => void>>();
  ipcRenderer.on("sid:event", (_e, msg: { name: string; data: unknown }) => {
    listeners.get(msg.name)?.forEach((cb) => { try { cb(msg.data); } catch (err) { console.error(err); } });
  });

  const bridge: Record<string, unknown> = {
    contract: manifest.contract,
    on(name: string, cb: (data: unknown) => void) {
      if (typeof cb !== "function") throw new TypeError("callback required");
      let set = listeners.get(name);
      if (!set) listeners.set(name, (set = new Set()));
      set.add(cb);
      return () => { set!.delete(cb); };
    },
  };
  for (const [ns, methods] of Object.entries(manifest.namespaces)) {
    const api: Record<string, (...args: unknown[]) => Promise<unknown>> = {};
    for (const m of methods) {
      api[m] = async (...args) => {
        const r = (await ipcRenderer.invoke(`${PREFIX}${ns}.${m}`, ...args)) as Reply;
        if (r.ok) return r.value;
        // a plain object, so the page sees code/title/detail/fix (an Error keeps only its message across contextBridge)
        throw { ...r.error, message: r.error.title };
      };
    }
    bridge[ns] = api;
  }
  contextBridge.exposeInMainWorld("studentDesktop", bridge);
}
