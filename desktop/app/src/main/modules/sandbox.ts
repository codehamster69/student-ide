/**
 * `sandbox.*` and `terminal.*`: the local sandbox runtime (@studentide/sandbox,
 * docs/sandbox-runtime.md). The engine is the one the installer saved in
 * <userData>/engine.json; without it every call explains that it is missing.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { registerSandboxIpc, type EngineInfo } from "@studentide/sandbox";
import { fail, type DesktopModule } from "../ipc";

function savedEngine(userData: string): EngineInfo | null {
  try {
    const e = JSON.parse(readFileSync(join(userData, "engine.json"), "utf8"));
    return Array.isArray(e?.cli) && e.cli.length ? (e as EngineInfo) : null;
  } catch {
    return null;
  }
}

export const sandboxModule = (): DesktopModule => {
  let shutdown: (() => Promise<void>) | undefined;
  return {
    namespace: "sandbox",
    register(ctx) {
      // re-read on each first use, so an engine set up after launch is picked up
      shutdown = registerSandboxIpc(ctx, { engine: () => savedEngine(ctx.userData), fail }).shutdown;
    },
    dispose: () => shutdown?.() ?? Promise.resolve(),
  };
};
