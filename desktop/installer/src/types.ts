/**
 * Shared types: what setup hands to the desktop app (EngineInfo, saved as
 * engine.json in the app's userData folder) and the progress events it emits.
 * This is the contract with desktop/app and the sandbox code; change it only
 * additively.
 */

export type EngineKind = 'wsl-podman' | 'lima-podman' | 'podman' | 'docker';

export interface EngineInfo {
  kind: EngineKind;
  /** argv prefix that runs the engine's Docker-compatible CLI, e.g. ["wsl.exe","-d","StudentIDE","--","sid-podman"]. */
  cli: string[];
  /** Environment the cli needs (e.g. LIMA_HOME). Merge over process.env. */
  env?: Record<string, string>;
  /** unix:// socket speaking the Docker API, when reachable from the host (macOS, Linux). Absent on Windows. */
  dockerHost?: string;
  /** True when we installed and manage this engine; false for a Docker/Podman the user already had. */
  bundled: boolean;
  version: string;
  installedAt: string;
}

export type Step = 'check' | 'engine' | 'images' | 'verify';

export interface Progress {
  step: Step;
  /** 0..100 within the step. */
  percent: number;
  message: string;
}

export interface ImageRef {
  /** Pinned by digest, e.g. ghcr.io/codehamster69/studentide-env-c@sha256:... */
  ref: string;
  subject?: string;
}

export interface CheckItem {
  id: string;
  ok: boolean;
  message: string;
  fix?: string;
}

export interface CheckResult {
  ok: boolean;
  checks: CheckItem[];
}

/** The setup check owned by the sandbox code; setup calls it last. */
export type SetupCheck = (engine: EngineInfo, images: ImageRef[]) => Promise<CheckResult>;
