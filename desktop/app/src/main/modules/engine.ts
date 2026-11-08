/**
 * `engine.*`: the local container engine, implemented with @studentide/installer
 * (desktop/installer). status() reads engine.json and pings it; setup() runs the
 * one-click setup and streams progress as "engine.progress". A restart that
 * Windows needs relaunches the app with --resume-setup; status() then reports
 * "missing" again and the setup screen simply carries on.
 */

import path from "node:path";
import fs from "node:fs";
import { detectEngine, engineAlive, loadImageList, runSetup, SetupError, type ImageRef } from "@studentide/installer";
import { setupCheck } from "@studentide/sandbox";
import { fail, type DesktopModule } from "../ipc";

/** Images every machine needs (e.g. the sandbox proxy), shipped next to the app by electron-builder. */
function bundledImages(): ImageRef[] {
  const file = path.join(process.resourcesPath ?? "", "sandbox", "images.json");
  return fs.existsSync(file) ? loadImageList(file) : [];
}

export const engineModule = (): DesktopModule => ({
  namespace: "engine",
  register(ctx) {
    let running: Promise<unknown> | null = null;

    ctx.handle("engine.status", async () => {
      const engine = detectEngine(ctx.userData);
      if (!engine) return { state: "missing", engine: null };
      return { state: (await engineAlive(engine)) ? "ready" : "broken", engine };
    });

    ctx.handle("engine.setup", async (opts?: { silent?: boolean; images?: string[] }) => {
      if (running) return running; // a second click joins the setup already running
      const images = [...bundledImages(), ...(opts?.images ?? []).filter((r) => typeof r === "string").map((ref) => ({ ref }))];
      running = runSetup({
        dataDir: ctx.userData,
        images,
        silent: !!opts?.silent,
        // the full Lab doctor (desktop/sandbox), tried with the first image to pull
        check: (engine, imgs) => setupCheck(engine, { dataDir: ctx.userData, image: imgs[0]?.ref }),
        onProgress: (p) => ctx.emit("engine.progress", p),
      })
        .then((res) => res.engine)
        .catch((e: unknown) => {
          if (!(e instanceof SetupError)) throw e;
          return fail({
            code: e.code.toLowerCase(),
            title: e.title,
            detail: e.log ? `${e.detail}\n\n${e.log}` : e.detail,
            fix: e.fix,
            needsAdmin: e.needsAdmin,
            needsReboot: e.needsReboot,
          });
        })
        .finally(() => (running = null));
      return running;
    });
  },
});
