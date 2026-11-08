/**
 * `updates.*`: auto-update from the server's feed (/api/desktop/updates, which the
 * server fills from GitHub Releases; backend/studentide/desktop_updates.py).
 *
 * Rules, so an update never costs a student work:
 *  - check at start and every 4 hours; download quietly in the background;
 *  - never restart on its own: the new version installs when the app closes,
 *    or at once when the student presses "Restart to update";
 *  - the one exception is the minimum-version gate (main.ts): the app is unusable
 *    then anyway, so it restarts as soon as the download is done.
 * Windows (installed) and Linux AppImage update themselves. Unsigned macOS builds
 * and the portable .exe can't (Squirrel.Mac needs a signature; a portable exe has
 * no installer), so they get "manual": the newest version and a download link.
 */

import { app, net } from "electron";
import { autoUpdater } from "electron-updater";
import { compareVersions } from "../config";
import { fail, type DesktopModule, type ModuleContext } from "../ipc";
import type { Shell } from "../main";
import type { UpdateStatus } from "../../shared/api/updates";

const EVERY_MS = 4 * 60 * 60 * 1000;
const FIRST_MS = 20 * 1000;

export class Updater {
  status: UpdateStatus = { mode: "off", state: "idle", current: app.getVersion() };
  private ctx?: ModuleContext;
  private restartWhenReady = false;
  private timer?: NodeJS.Timeout;

  constructor(private s: Shell) {}

  /** Why this copy of the app can't replace itself, or "" when it can. */
  private manualReason(): string {
    if (this.s.config.portable) return "The portable app can't update itself: download the new version and replace it.";
    if (process.platform === "darwin") return "Until the Mac app is signed, updates are a download: open it and drag Student IDE to Applications again.";
    if (process.platform === "linux" && !process.env.APPIMAGE) return "Installed from a .deb package: download the new one, or update it with your package manager.";
    return "";
  }

  private set(patch: Partial<UpdateStatus>) {
    this.status = { ...this.status, ...patch };
    this.ctx?.emit("updates.status", this.status);
    this.onChange?.(this.status);
  }

  /** main.ts listens while the update page is showing. */
  onChange?: (s: UpdateStatus) => void;

  start(ctx: ModuleContext) {
    this.ctx = ctx;
    if (!app.isPackaged && process.env.STUDENTIDE_UPDATES_DEV !== "1") {
      this.set({ mode: "off", reason: "Development build." });
      return;
    }
    const reason = this.manualReason();
    this.set({ mode: reason ? "manual" : "auto", reason: reason || undefined });
    if (!reason) {
      autoUpdater.autoDownload = true;
      autoUpdater.autoInstallOnAppQuit = true;
      autoUpdater.allowPrerelease = false;
      autoUpdater.logger = null;
      autoUpdater.forceDevUpdateConfig = !app.isPackaged; // STUDENTIDE_UPDATES_DEV=1: try updates from a dev build
      autoUpdater.setFeedURL({ provider: "generic", url: `${ctx.server()}/api/desktop/updates`, useMultipleRangeRequest: false });
      autoUpdater.on("checking-for-update", () => this.set({ state: "checking" }));
      autoUpdater.on("update-available", (i) => this.set({ state: "available", latest: i.version }));
      autoUpdater.on("update-not-available", (i) => this.set({ state: "up-to-date", latest: i.version, checkedAt: Date.now() }));
      autoUpdater.on("download-progress", (p) => this.set({ state: "downloading", percent: Math.round(p.percent) }));
      autoUpdater.on("update-downloaded", (i) => {
        this.set({ state: "ready", latest: i.version, percent: 100, checkedAt: Date.now() });
        if (this.restartWhenReady) this.install();
      });
      autoUpdater.on("error", (e) => this.set({ state: "error", reason: plain(e), checkedAt: Date.now() }));
    }
    setTimeout(() => void this.check(), FIRST_MS);
    this.timer = setInterval(() => void this.check(), EVERY_MS);
  }

  async check(): Promise<UpdateStatus> {
    if (this.status.mode === "off" || !this.ctx) return this.status;
    if (this.status.state === "downloading" || this.status.state === "ready") return this.status;
    if (this.status.mode === "auto") {
      try { await autoUpdater.checkForUpdates(); } catch (e) { this.set({ state: "error", reason: plain(e), checkedAt: Date.now() }); }
      return this.status;
    }
    // manual: read the version from the feed and point at the installer for this machine
    this.set({ state: "checking" });
    try {
      const feed = process.platform === "linux" ? "latest-linux.yml" : "latest.yml";
      const r = await net.fetch(`${this.ctx.server()}/api/desktop/updates/${feed}`, { cache: "no-store" });
      if (r.status === 404) { this.set({ mode: "off", state: "idle", reason: "This server doesn't offer updates." }); return this.status; }
      if (!r.ok) throw new Error(`the server answered ${r.status}`);
      const latest = /^version:\s*['"]?([^'"\s]+)/m.exec(await r.text())?.[1];
      const os = process.platform === "win32" ? "windows" : process.platform === "darwin" ? "mac" : "linux";
      const newer = latest && compareVersions(latest, app.getVersion()) > 0;
      this.set({ state: newer ? "available" : "up-to-date", latest, checkedAt: Date.now(),
                 downloadUrl: newer ? `${this.ctx.server()}/api/desktop/download?os=${os}&arch=${process.arch === "arm64" ? "arm64" : "x64"}` : undefined });
    } catch (e) {
      this.set({ state: "error", reason: plain(e), checkedAt: Date.now() });
    }
    return this.status;
  }

  /** The update page (app too old): get the new version and restart into it as soon as it is here. */
  async forceUpdate(): Promise<void> {
    if (this.status.mode !== "auto") return;
    this.restartWhenReady = true;
    if (this.status.state === "ready") this.install();
    else await this.check();
  }

  install() {
    if (this.status.state !== "ready") fail({ code: "update_not_ready", title: "The update hasn't finished downloading yet." });
    setImmediate(() => autoUpdater.quitAndInstall(true, true)); // silent installer, open the app again after
  }

  dispose() { if (this.timer) clearInterval(this.timer); }
}

function plain(e: unknown): string {
  const m = String((e as Error)?.message ?? e);
  if (/ENOTFOUND|ECONNREFUSED|ETIMEDOUT|net::ERR/.test(m)) return "Couldn't reach the server to look for updates.";
  if (/404/.test(m)) return "This server doesn't offer updates yet.";
  return `Couldn't update: ${m.split("\n")[0].slice(0, 160)}`;
}

export const updatesModule = (s: Shell, updater: Updater): DesktopModule => ({
  namespace: "updates",
  register(ctx) {
    ctx.handle("updates.status", () => updater.status);
    ctx.handle("updates.check", () => updater.check());
    ctx.handle("updates.restart", () => updater.install());
    updater.start(ctx);
  },
  async dispose() { updater.dispose(); },
});
