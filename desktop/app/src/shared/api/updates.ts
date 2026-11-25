/**
 * `studentDesktop.updates`: keeping the app up to date (src/main/modules/updates.ts).
 *
 * Updates are mandatory. Updates come from the server the app is locked to
 * (/api/desktop/updates, fed by GitHub Releases), and by default the server makes
 * the newest release the minimum version (backend/studentide/desktop.py). The app
 * downloads a new version quietly, then installs it at the first safe moment: no
 * lab, sitting or competition open and the event journal uploaded. Until then the
 * student finishes what is open; new work waits for the update. Windows (installed),
 * Linux AppImage and macOS (download-and-replace, modules/macupdate.ts) install by
 * themselves; the portable .exe, a .deb, or a Mac copy the account can't replace
 * get a blocking update page with a download link ("manual").
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
  /** the server no longer accepts this version: it updates at the next safe moment */
  required?: boolean;
  minVersion?: string;      // the oldest version the server accepts, when it sets one
  /** a lab or other recorded work is open, so the update waits for it */
  busy?: boolean;
}

export interface UpdatesApi {
  status(): Promise<UpdateStatus>;
  /** Looks for a new version now (it also does so at start and every 15 minutes). */
  check(): Promise<UpdateStatus>;
  /** Closes the app, installs the downloaded version and opens it again. Only when state is "ready". */
  restart(): Promise<void>;
  /** The web app says whether a lab, sitting or competition is open (the update waits until it isn't). */
  setBusy(busy: boolean): Promise<void>;
  /** "Update now", or the server refused new work (426): show the update page and install. */
  updateNow(): Promise<void>;
}

export interface UpdatesEvents {
  "updates.status": UpdateStatus;
}
