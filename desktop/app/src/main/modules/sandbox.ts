/** `sandbox.*` and `terminal.*`: owned by the sandbox thread. Wire createSandbox from @studentide/sandbox here. */

import { notImplemented, type DesktopModule } from "../ipc";

const SANDBOX = ["setupCheck", "openLab", "stop", "reset", "listFiles", "readFile", "writeFile", "run"];
const TERMINAL = ["open", "write", "resize", "close"];

export const sandboxModule = (): DesktopModule => ({
  namespace: "sandbox",
  register(ctx) {
    for (const m of SANDBOX) ctx.handle(`sandbox.${m}`, () => notImplemented("Sandbox labs"));
    for (const m of TERMINAL) ctx.handle(`terminal.${m}`, () => notImplemented("The lab terminal"));
  },
});
