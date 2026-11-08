/**
 * Student IDE desktop shell: one locked-down window on the Student IDE server.
 *
 * The window shows the server's own web app, so labs, sittings, competitions, the
 * learning lab, live view, review, attendance and View as student all work exactly
 * as on the web, and keystrokes are timed by the same Chromium. The shell adds:
 * browser sign-in, the `window.studentDesktop` bridge (src/shared/contract.ts) for
 * local features, a minimum-version gate, and an offline page. Navigation is locked
 * to the server origin; other links open in the system browser; camera, microphone,
 * screen and location permissions are always refused.
 */

import { app, BrowserWindow, Menu, nativeTheme, net, session, shell, type MenuItemConstructorOptions, type WebContents } from "electron";
import { join } from "node:path";
import { compareVersions, Config, setupPaths } from "./config";
import { Registry } from "./ipc";
import { modules } from "./modules";

export interface Shell {
  config: Config;
  load(): void;
  focus(): void;
}

const portable = setupPaths();
const devtools = !app.isPackaged || process.env.STUDENTIDE_DEVTOOLS === "1";
const STATIC = join(__dirname, "..", "..", "static");

// --no-sandbox only for CI running as root (e2e/smoke.mjs); windows still get sandbox: true
if (!process.argv.includes("--no-sandbox")) app.enableSandbox();
if (!app.requestSingleInstanceLock()) app.quit();

let win: BrowserWindow | null = null;
let config: Config;
let registry: Registry;

const server = () => config.server();
const sameOrigin = (url: string) => { try { return new URL(url).origin === server(); } catch { return false; } };
const openOutside = (url: string) => { if (/^https?:\/\//.test(url)) shell.openExternal(url).catch(() => undefined); };

const prefs = () => ({
  preload: join(__dirname, "..", "preload", "preload.js"),
  sandbox: true,
  contextIsolation: true,
  nodeIntegration: false,
  webviewTag: false,
  spellcheck: false,
  devTools: devtools,
});

/** Applied to every window and frame the app ever creates. */
function harden(wc: WebContents) {
  registry.attach(wc);
  const guard = (e: { preventDefault(): void }, url: string) => {
    if (sameOrigin(url) || url.startsWith("file:") && wc.getURL().startsWith("file:")) return;
    e.preventDefault();
    openOutside(url);
  };
  wc.on("will-navigate", guard);
  wc.on("will-redirect", guard);
  wc.on("will-attach-webview", (e) => e.preventDefault());
  wc.setWindowOpenHandler(({ url }) => {
    if (sameOrigin(url)) return { action: "allow", overrideBrowserWindowOptions: { webPreferences: prefs(), autoHideMenuBar: true } };
    openOutside(url);
    return { action: "deny" };
  });
}

function staticPage(name: string, params: Record<string, string>) {
  win?.loadFile(join(STATIC, name), { query: { server: server(), ...params } }).catch(() => undefined);
}

/** Loads the web app, unless the server says this app is too old. */
async function load() {
  if (!win) return;
  try {
    const r = await net.fetch(`${server()}/api/desktop/config`, { cache: "no-store" });
    if (r.ok) {
      const cfg = (await r.json()) as { min_version?: string | null; download_url?: string | null };
      if (cfg.min_version && compareVersions(app.getVersion(), cfg.min_version) < 0) {
        staticPage("update.html", { version: app.getVersion(), min: cfg.min_version, download: cfg.download_url ?? "" });
        return;
      }
    }
  } catch { /* offline: the load below fails and shows the offline page */ }
  win.loadURL(server()).catch(() => undefined);
}

function createWindow() {
  win = new BrowserWindow({
    width: 1320, height: 860, minWidth: 900, minHeight: 600, show: false, title: "Student IDE",
    backgroundColor: nativeTheme.shouldUseDarkColors ? "#111113" : "#f7f7f8",
    autoHideMenuBar: true,
    webPreferences: prefs(),
  });
  win.once("ready-to-show", () => win?.show());
  win.on("closed", () => { win = null; });
  win.webContents.on("did-fail-load", (_e, code, desc, url, isMain) => {
    // -3 = aborted (a navigation replaced this one)
    if (isMain && code !== -3 && sameOrigin(url)) staticPage("offline.html", { reason: desc });
  });
  void load();
}

function menu() {
  const mac = process.platform === "darwin";
  const template: MenuItemConstructorOptions[] = [
    ...(mac ? [{ role: "appMenu" as const }] : []),
    { role: "editMenu" },
    { label: "View", submenu: [
      { role: "reload" }, { type: "separator" },
      { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" }, { type: "separator" }, { role: "togglefullscreen" },
      ...(devtools ? [{ role: "toggleDevTools" as const }] : []),
    ] },
    { role: "windowMenu" },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

const shellApi: Shell = {
  get config() { return config; },
  load: () => { void load(); },
  focus: () => { if (win) { if (win.isMinimized()) win.restore(); win.show(); win.focus(); } },
};

app.on("second-instance", () => shellApi.focus());
app.on("web-contents-created", (_e, wc) => harden(wc));
app.on("window-all-closed", () => app.quit());

app.whenReady().then(() => {
  config = new Config(portable);
  registry = new Registry(server);
  const ctx = {
    handle: registry.handle.bind(registry),
    emit: registry.emit.bind(registry),
    server,
    fetch: (path: string, init?: RequestInit) => session.defaultSession.fetch(server() + path, { credentials: "include", ...init }),
    userData: app.getPath("userData"),
  };
  const mods = modules(shellApi);
  for (const m of mods) m.register(ctx as never);
  let disposed = false;
  app.on("will-quit", (e) => {
    if (disposed) return;
    e.preventDefault(); // let modules stop lab instances and flush uploads first (at most 10 s)
    disposed = true;
    const done = Promise.all(mods.map((m) => m.dispose?.().catch(() => {})));
    Promise.race([done, new Promise((r) => setTimeout(r, 10_000))]).finally(() => app.quit());
  });

  const ses = session.defaultSession;
  ses.setUserAgent(`${ses.getUserAgent()} StudentIDE-Desktop/${app.getVersion()}`);
  // the web app needs none of these; the consent promise is no webcam, microphone or screen
  ses.setPermissionRequestHandler((wc, permission, cb) => cb(permission === "clipboard-sanitized-write" && sameOrigin(wc.getURL())));
  ses.setPermissionCheckHandler((_wc, permission, origin) => permission === "clipboard-sanitized-write" && sameOrigin(origin));
  ses.setDisplayMediaRequestHandler((_req, cb) => cb({}));

  let online = net.isOnline();
  setInterval(() => {
    const now = net.isOnline();
    if (now !== online) registry.emit("app.online", { online: (online = now) });
  }, 3000);

  menu();
  createWindow();
  app.on("activate", () => { if (!win) createWindow(); });
});
