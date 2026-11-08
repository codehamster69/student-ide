/**
 * Public API of @studentide/installer, used by desktop/app's main process:
 * detectEngine() at start, runSetup() from the setup window, removeEngine()
 * on uninstall or reset. See docs/desktop-installer.md.
 */
export { defaultAssets, runSetup, detectEngine, removeEngine, existingEngine, engineAlive, ENGINE_FILE } from './setup';
export type { SetupOptions, SetupResult } from './setup';
export { SetupError } from './errors';
export type { SetupErrorCode, SetupErrorInfo } from './errors';
export { loadImageList, pullImages } from './images';
export type { EngineInfo, EngineKind, ImageRef, Progress, Step, CheckItem, CheckResult, SetupCheck } from './types';
