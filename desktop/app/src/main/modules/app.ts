/** `app.*`: info about the shell, opening links outside, switching server. */

import { app, shell } from "electron";
import { CONTRACT_VERSION, type AppInfo } from "../../shared/contract";
import { normaliseOrigin } from "../config";
import { fail, type DesktopModule } from "../ipc";
import type { Shell } from "../main";

export const appModule = (s: Shell): DesktopModule => ({
  namespace: "app",
  register(ctx) {
    ctx.handle("app.info", (): AppInfo => ({
      version: app.getVersion(),
      contract: CONTRACT_VERSION,
      platform: process.platform,
      arch: process.arch,
      electron: process.versions.electron,
      chrome: process.versions.chrome,
      deviceId: s.config.deviceId(),
      portable: s.config.portable,
      server: ctx.server(),
    }));
    ctx.handle("app.openExternal", async (url: unknown) => {
      if (typeof url !== "string" || !/^https?:\/\//.test(url)) fail({ code: "bad_url", title: "Only web links can be opened." });
      await shell.openExternal(url as string);
    });
    ctx.handle("app.setServer", async (origin: unknown) => {
      const o = typeof origin === "string" ? normaliseOrigin(origin) : null;
      if (!o) fail({ code: "bad_url", title: "That is not a valid server address.", fix: "Use an https:// address." });
      s.config.save({ server: o! });
      s.load();
    });
  },
});
