/**
 * `engine.*`: owned by the installer thread. Wire @studentide/installer here:
 * status() -> detectEngine(ctx.userData), setup() -> runSetup({ dataDir, onProgress: p => ctx.emit("engine.progress", p) }).
 */

import { notImplemented, type DesktopModule } from "../ipc";

export const engineModule = (): DesktopModule => ({
  namespace: "engine",
  register(ctx) {
    ctx.handle("engine.status", () => ({ state: "missing", engine: null }));
    ctx.handle("engine.setup", () => notImplemented("Setting up the lab engine"));
  },
});
