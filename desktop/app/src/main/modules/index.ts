/** Every namespace module, in one list. Each thread adds or edits only its own line. */

import type { DesktopModule } from "../ipc";
import type { Shell } from "../main";
import { appModule } from "./app";
import { authModule } from "./auth";
import { engineModule } from "./engine";
import { sandboxModule } from "./sandbox";
import { updatesModule, type Updater } from "./updates";
import { journalModule } from "./journal";

export const modules = (s: Shell, updater: Updater): DesktopModule[] => [
  appModule(s),
  authModule(s),
  engineModule(), // installer thread
  sandboxModule(), // sandbox thread (sandbox.* and terminal.*)
  updatesModule(s, updater), // auto-update (updates.*)
  journalModule(), // monitoring thread (event journal, signed batches)
];
