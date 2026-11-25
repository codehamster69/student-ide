/**
 * `updates.*`: mandatory auto-update from the server's feed (/api/desktop/updates,
 * which the server fills from GitHub Releases; backend/studentide/desktop_updates.py).
 *
 * Every version the server no longer accepts must go (Rohan: no student stays on an
 * old version). By default the server makes the newest release the minimum
 * (backend/studentide/desktop.py, VersionPolicy). Rules, so an update never costs
 * a student work:
 *  - check at start and every 15 minutes; download quietly in the background;
 *  - never restart while a lab, sitting or competition is open (the web app says so
 *    with setBusy, and the journal knows which recorded sessions are open), nor while
 *    recorded events still wait to upload;
 *  - at the first safe moment after that (the person idle for 2 minutes, the window
 *    hidden, "Update now", or the server refusing new work with 426) the app shows the
 *    update page (main.ts), installs and opens again on the page it was on;
 *  - while it waits, the server lets the old version finish open work but not start
 *    new work, so nobody begins a lab on an old version.
 * Windows (installed) and Linux AppImage use electron-updater. macOS is unsigned, so
 * Squirrel.Mac can't be used: it downloads the .dmg and swaps the bundle itself
 * (macupdate.ts). The portable .exe, a .deb and a Mac copy the account can't replace
 * are "manual": the update page blocks the app and offers the download.
 */

import { app, net, powerMonitor } from "electron";
import { autoUpdater } from "electron-updater";
import { compareVersions } from "../config";
import { fail, type DesktopModule, type ModuleContext } from "../ipc";
import type { Shell } from "../main";
import type { UpdateStatus } from "../../shared/api/updates";
import { journalActivity } from "./journal";
import { macBlocker, macDownload, macInstall, macRelease } from "./macupdate";

const EVERY_MS = 15 * 60 * 1000;
const FIRST_MS = 20 * 1000;
const SAFE_TICK_MS = 30 * 1000;
const IDLE_S = 120;

export class Updater {
  status: UpdateStatus = { mode: "off", state: "idle", current: app.getVersion() };
  private ctx?: ModuleContext;
  private restartWhenReady = false;
  private timers: NodeJS.Timeout[] = [];
  private mac = false;      // macOS bundle swap instead of electron-updater
  private macDmg = "";
  private rendererBusy = false;
  /** main.ts sets this while the update page is showing, so it is shown once. */
  gated = false;

  constructor(private s: Shell) {}

  /** Why this copy of the app can't replace itself, or "" when it can. */
  private manualReason(): string {
    if (this.s.config.portable) return "The portable app can't update itself: download the new version and replace it.";
    if (process.platform === "darwin") return macBlocker();
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
    this.mac = process.platform === "darwin" && !reason;
    this.set({ mode: reason ? "manual" : "auto", reason: reason || undefined });
    if (!reason && !this.mac) {
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
      autoUpdater.on("update-downloaded", (i) => this.downloaded(i.version));
      autoUpdater.on("error", (e) => this.set({ state: "error", reason: plain(e), checkedAt: Date.now() }));
    }
    this.timers.push(setTimeout(() => void this.check(), FIRST_MS));
    this.timers.push(setInterval(() => void this.check(), EVERY_MS));
    this.timers.push(setInterval(() => this.atSafeMoment(), SAFE_TICK_MS));
  }

  private downloaded(version: string) {
    this.set({ state: "ready", latest: version, percent: 100, checkedAt: Date.now() });
    if (this.restartWhenReady) this.install();
    else this.atSafeMoment();
  }

  /** Is the server still accepting this version? Read from /api/desktop/config. */
  private async policy() {
    if (!this.ctx) return;
    try {
      const r = await net.fetch(`${this.ctx.server()}/api/desktop/config`, { cache: "no-store" });
      if (!r.ok) return;
      const cfg = (await r.json()) as { min_version?: string | null };
      const min = cfg.min_version ?? undefined;
      this.set({ minVersion: min, required: Boolean(min && compareVersions(app.getVersion(), min) < 0) });
    } catch { /* offline: keep what we knew */ }
  }

  async check(): Promise<UpdateStatus> {
    if (this.status.mode === "off" || !this.ctx) return this.status;
    await this.policy();
    if (this.status.state === "downloading" || this.status.state === "ready") { this.atSafeMoment(); return this.status; }
    if (this.status.mode === "auto" && !this.mac) {
      try { await autoUpdater.checkForUpdates(); } catch (e) { this.set({ state: "error", reason: plain(e), checkedAt: Date.now() }); }
    } else if (this.mac) {
      await this.checkMac();
    } else {
      await this.checkManual();
    }
    this.atSafeMoment();
    return this.status;
  }

  private async checkMac() {
    const server = this.ctx!.server();
    this.set({ state: "checking" });
    try {
      const rel = await macRelease(server);
      if (!rel) { this.set({ state: "up-to-date", checkedAt: Date.now() }); return; }
      if (compareVersions(rel.version, app.getVersion()) <= 0) { this.set({ state: "up-to-date", latest: rel.version, checkedAt: Date.now() }); return; }
      this.set({ state: "downloading", latest: rel.version, percent: 0 });
      this.macDmg = await macDownload(server, rel, (percent) => this.set({ state: "downloading", percent }));
      this.downloaded(rel.version);
    } catch (e) {
      this.set({ state: "error", reason: plain(e), checkedAt: Date.now() });
    }
  }

  // manual: read the version from the feed and point at the installer for this machine
  private async checkManual() {
    const server = this.ctx!.server();
    this.set({ state: "checking" });
    try {
      const feed = process.platform === "linux" ? "latest-linux.yml" : "latest.yml";
      const r = await net.fetch(`${server}/api/desktop/updates/${feed}`, { cache: "no-store" });
      if (r.status === 404) { this.set({ mode: "off", state: "idle", reason: "This server doesn't offer updates." }); return; }
      if (!r.ok) throw new Error(`the server answered ${r.status}`);
      const latest = /^version:\s*['"]?([^'"\s]+)/m.exec(await r.text())?.[1];
      const newer = latest && compareVersions(latest, app.getVersion()) > 0;
      this.set({ state: newer ? "available" : "up-to-date", latest, checkedAt: Date.now(),
                 downloadUrl: newer ? downloadUrl(server) : undefined });
    } catch (e) {
      this.set({ state: "error", reason: plain(e), checkedAt: Date.now() });
    }
  }

  /** Open recorded work, or events not yet on the server (while online). */
  private busy(): boolean {
    return this.rendererBusy || journalActivity.openSessions() > 0 || (journalActivity.online() && journalActivity.pending() > 0);
  }

  setBusy(busy: boolean) {
    this.rendererBusy = busy;
    this.set({ busy: this.busy() });
    this.atSafeMoment();
  }

  /** Shows the update page once the update is required and nothing is open. */
  private atSafeMoment() {
    const busy = this.busy();
    if (busy !== Boolean(this.status.busy)) this.set({ busy });
    if (!this.status.required || this.gated || busy || this.status.mode === "off") return;
    if (this.s.windowShown() && powerMonitor.getSystemIdleTime() < IDLE_S) return; // don't pull the page from under someone
    this.s.load(); // main.ts: the update page, which calls forceUpdate()
  }

  /** "Update now" or a 426 from the server: the update page now, unless work is open. */
  updateNow() {
    if (this.busy()) fail({ code: "update_busy", title: "Finish and close the open lab first; the update starts right after." });
    if (this.status.required) { this.s.load(); return; }
    if (this.status.state === "ready") this.install();
    else void this.check();
  }

  /** The update page (app too old): get the new version and restart into it as soon as it is here. */
  async forceUpdate(): Promise<void> {
    if (this.status.mode !== "auto") return;
    this.restartWhenReady = true;
    if (this.status.state === "ready") this.install();
    else if (this.status.state !== "downloading") await this.check();
  }

  install() {
    if (this.status.state !== "ready") fail({ code: "update_not_ready", title: "The update hasn't finished downloading yet." });
    this.s.rememberPage();
    if (this.mac) setImmediate(() => macInstall(this.macDmg));
    else setImmediate(() => autoUpdater.quitAndInstall(true, true)); // silent installer, open the app again after
  }

  dispose() { for (const t of this.timers) clearInterval(t); }
}

export function downloadUrl(server: string): string {
  const os = process.platform === "win32" ? "windows" : process.platform === "darwin" ? "mac" : "linux";
  return `${server}/api/desktop/download?os=${os}&arch=${process.arch === "arm64" ? "arm64" : "x64"}`;
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
    ctx.handle("updates.setBusy", (busy: unknown) => updater.setBusy(Boolean(busy)));
    ctx.handle("updates.updateNow", () => updater.updateNow());
    updater.start(ctx);
  },
  async dispose() { updater.dispose(); },
});
