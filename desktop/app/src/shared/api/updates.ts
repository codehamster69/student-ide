/**
 * `studentDesktop.updates`: keeping the app up to date (src/main/modules/updates.ts).
 *
 * Updates come from the server the app is locked to (/api/desktop/updates, fed by
 * GitHub Releases). The app downloads a new version quietly and installs it the
 * next time it closes, so a lab is never interrupted. Unsigned macOS builds and
 * the portable .exe can't replace themselves: there the state is "manual" and
 * the web app offers the download link instead.
 */

export interface UpdateStatus {
  /** auto: downloads and installs by itself; manual: a link to download; off: not available here */
  mode: "auto" | "manual" | "off";
  state: "idle" | "checking" | "available" | "downloading" | "ready" | "up-to-date" | "error";
  current: string;          // this app's version
  latest?: string;          // newest version the server offers, once known
  percent?: number;         // while downloading
  downloadUrl?: string;     // manual mode: the installer for this machine
  reason?: string;          // why off or manual, or what went wrong, in plain words
  checkedAt?: number;       // ms since epoch
}

export interface UpdatesApi {
  status(): Promise<UpdateStatus>;
  /** Looks for a new version now (it also does so at start and every few hours). */
  check(): Promise<UpdateStatus>;
  /** Closes the app, installs the downloaded version and opens it again. Only when state is "ready". */
  restart(): Promise<void>;
}

export interface UpdatesEvents {
  "updates.status": UpdateStatus;
}
