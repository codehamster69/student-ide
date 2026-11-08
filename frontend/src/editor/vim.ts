// Vim key bindings for our CodeMirror editors, as a per-browser setting
// (plan §4.1). Students who like vim can stay in the editor, where every edit
// is recorded in full, instead of moving to vim in a terminal. Normal-mode keys
// are ordinary key events to the recorder and the edits they cause are ordinary
// edit events, so nothing in the event schema changes.

import { useEffect, useState } from "react";
import { Compartment, type Extension } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { vim } from "@replit/codemirror-vim";

const KEY = "studentide.vim";
const EVENT = "studentide:vim";

export function vimOn(): boolean {
  try { return localStorage.getItem(KEY) === "1"; } catch { return false; }
}

export function setVim(on: boolean): void {
  try { localStorage.setItem(KEY, on ? "1" : "0"); } catch { /* private window: this tab only */ }
  window.dispatchEvent(new CustomEvent(EVENT, { detail: on }));
}

/** The setting as React state; every editor and toggle on the page stays in step. */
export function useVimMode(): [boolean, (on: boolean) => void] {
  const [on, set] = useState(vimOn);
  useEffect(() => {
    const f = (e: Event) => set((e as CustomEvent<boolean>).detail);
    window.addEventListener(EVENT, f);
    return () => window.removeEventListener(EVENT, f);
  }, []);
  return [on, setVim];
}

/** One compartment per editor: put `vimCompartment.of(vimExtension(on))` in its extensions. */
export const newVimCompartment = () => new Compartment();

/** vim() must come before other keymaps, so put this first in the extension list. */
export const vimExtension = (on: boolean): Extension => (on ? vim({ status: true }) : []);

export function applyVim(view: EditorView | undefined, compartment: Compartment, on: boolean): void {
  view?.dispatch({ effects: compartment.reconfigure(vimExtension(on)) });
}
