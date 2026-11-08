/**
 * `studentDesktop.engine`: the local container engine (owned by the installer thread,
 * implemented with @studentide/installer in src/main/modules/engine.ts).
 */

export interface EngineInfo {
  kind: "wsl-podman" | "lima-podman" | "podman" | "docker";
  cli: string[];          // argv prefix, e.g. ["wsl.exe", "-d", "StudentIDE", "--", "podman"]
  dockerHost?: string;    // unix:// socket when reachable from the host
  env?: Record<string, string>; // extra environment the cli needs (LIMA_HOME, XDG_CONFIG_HOME, WSL_UTF8)
  bundled?: boolean;      // true when our installer set it up (false: Docker/Podman the user already had)
  version: string;
  installedAt: string;
}

export interface EngineStatus {
  state: "ready" | "missing" | "broken";
  engine: EngineInfo | null;
}

export interface SetupProgress {
  step: "check" | "engine" | "images" | "verify";
  percent: number;
  message: string;
}

export interface EngineApi {
  /** Fast: reads the saved engine.json and pings it. */
  status(): Promise<EngineStatus>;
  /** Installs or repairs the engine; progress arrives as "engine.progress". Rejects with a DesktopError (needsAdmin, needsReboot). */
  setup(opts?: { silent?: boolean; images?: string[] }): Promise<EngineInfo>;
}

export interface EngineEvents {
  "engine.progress": SetupProgress;
}
