/** `studentDesktop.app`: the shell itself (owned by the shell thread). */

export interface AppInfo {
  version: string;        // desktop app version, e.g. "0.1.0"
  contract: number;       // CONTRACT_VERSION the shell speaks
  platform: "win32" | "darwin" | "linux" | string;
  arch: string;           // x64, arm64
  electron: string;
  chrome: string;         // Chromium version: the web app's timing source
  deviceId: string;       // SHA-256 of a random per-install id; never the machine's own ids
  portable: boolean;      // settings live next to the app (USB stick)
  server: string;         // origin the shell is locked to, e.g. https://studentide.hokora.xyz
}

export interface AppApi {
  info(): Promise<AppInfo>;
  /** Opens an http(s) link in the system browser (links off the server open there anyway). */
  openExternal(url: string): Promise<void>;
  /** Points the app at another server (an admin setting); the window reloads there. */
  setServer(origin: string): Promise<void>;
}

export interface AppEvents {
  /** the network went away or came back (navigator.onLine is not enough inside a lab network) */
  "app.online": { online: boolean };
}
