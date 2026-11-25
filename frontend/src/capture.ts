// Turns editor and browser activity into recorder events.

import { Transaction, type Extension } from "@codemirror/state";
import { EditorView, ViewPlugin } from "@codemirror/view";
import type { Recorder } from "./recorder";
import { classify, dragStartedInside, track, type PasteSource } from "./pasteguard";

const MAX_CLIPBOARD = 20_000;
const CURSOR_THROTTLE_MS = 100;
export const SNAPSHOT_EVERY_MS = 30_000;

const NAV_KEYS = new Set([
  "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown",
]);
const MODIFIERS = new Set(["Shift", "Control", "Alt", "Meta", "CapsLock", "AltGraph", "OS"]);

/** Coarse key class, so features can group keys without parsing `code`. */
export function keyClass(e: KeyboardEvent): string {
  const k = e.key;
  if (MODIFIERS.has(k)) return "modifier";
  if (k === " ") return "space";
  if (k === "Enter") return "enter";
  if (k === "Tab") return "tab";
  if (k === "Backspace") return "backspace";
  if (k === "Delete") return "delete";
  if (NAV_KEYS.has(k)) return "nav";
  if (k.length === 1) {
    if (/\p{L}/u.test(k)) return "letter";
    if (/\p{N}/u.test(k)) return "digit";
    return "punct";
  }
  return "other";
}

export function keyData(e: KeyboardEvent, action: "down" | "up") {
  return {
    action,
    code: (e.code || e.key || "Unidentified").slice(0, 32),
    cls: keyClass(e),
    repeat: e.repeat,
    shift: e.shiftKey, ctrl: e.ctrlKey, alt: e.altKey, meta: e.metaKey,
  };
}

function lineCount(s: string): number {
  return s ? s.split("\n").length : 0;
}

type ClipAction = "paste" | "copy" | "cut" | "drop";

function clipboard(rec: Recorder, action: ClipAction, text: string, ts: number,
  extra: { source?: PasteSource; blocked?: boolean } = {}) {
  rec.log("clipboard", {
    action,
    length: text.length,
    lines: lineCount(text),
    text: text.slice(0, MAX_CLIPBOARD),
    truncated: text.length > MAX_CLIPBOARD,
    ...extra,
  }, ts);
}

/** Study screens pass this to block pastes and drops from outside Scribelab (see pasteguard.ts). */
export type PasteGuard = {
  /** called after an outside paste or drop was blocked, to show the notice */
  onBlocked: (kind: "paste" | "drop") => void;
  /** the student's other open documents (other questions of the sitting); the current one is always included */
  ownText?: () => string[];
};

/** CodeMirror extension that records keys, edits, clipboard, cursor and focus.
 * `path`: the file of a multi-file desktop workspace (schema v2 key/edit `path`).
 * `guard`: block outside pastes (study contexts); allowed in-IDE pastes and drops are logged
 * with edit origin "input.paste.internal" / "input.drop.internal" (schema v4). */
export function captureExtension(rec: Recorder, opts: { path?: string; guard?: PasteGuard } = {}): Extension {
  const at = opts.path ? { path: opts.path } : {};
  const guard = opts.guard;
  let lastCursor = 0;
  let pendingCursor: number | undefined;
  /** the next input.paste / input.drop transaction comes from inside the IDE */
  let internal: "paste" | "drop" | null = null;
  const markInternal = (kind: "paste" | "drop") => {
    internal = kind;
    setTimeout(() => { internal = null; }, 0); // CodeMirror dispatches synchronously; dropped files are blocked anyway
  };
  const originOf = (tr: Transaction): string => {
    const o = tr.annotation(Transaction.userEvent) ?? "unknown";
    if (internal && o === `input.${internal}`) return `${o}.internal`;
    return o;
  };

  const logCursor = (view: EditorView) => {
    const sel = view.state.selection.main;
    rec.log("cursor", { anchor: sel.anchor, head: sel.head, line: view.state.doc.lineAt(sel.head).number });
    lastCursor = performance.now();
  };

  const updates = EditorView.updateListener.of((u) => {
    for (const tr of u.transactions) {
      if (!tr.docChanged) continue;
      const changes: [number, number, string][] = [];
      tr.changes.iterChanges((fromA, toA, _fromB, _toB, inserted) => {
        changes.push([fromA, toA, inserted.toString()]);
      });
      rec.log("edit", {
        origin: originOf(tr),
        changes,
        len_before: tr.startState.doc.length,
        len_after: tr.newDoc.length,
        ...at,
      });
    }
    if (u.selectionSet && !u.docChanged) {
      const wait = CURSOR_THROTTLE_MS - (performance.now() - lastCursor);
      if (wait <= 0) logCursor(u.view);
      else if (pendingCursor === undefined) {
        pendingCursor = window.setTimeout(() => { pendingCursor = undefined; logCursor(u.view); }, wait);
      }
    }
  });

  // Capture-phase listeners so we see keys even when CodeMirror handles them.
  const keys = ViewPlugin.define((view) => {
    const down = (e: KeyboardEvent) => rec.log("key", { ...keyData(e, "down"), ...at }, e.timeStamp);
    const up = (e: KeyboardEvent) => rec.log("key", { ...keyData(e, "up"), ...at }, e.timeStamp);
    view.dom.addEventListener("keydown", down, true);
    view.dom.addEventListener("keyup", up, true);
    return {
      destroy() {
        view.dom.removeEventListener("keydown", down, true);
        view.dom.removeEventListener("keyup", up, true);
      },
    };
  });

  const own = (view: EditorView) => [view.state.doc.toString(), ...(guard?.ownText?.() ?? [])];

  const dom = EditorView.domEventHandlers({
    paste(e, view) {
      const text = e.clipboardData?.getData("text/plain") ?? "";
      if (!guard) { clipboard(rec, "paste", text, e.timeStamp); return false; }
      const source = classify(text, () => own(view));
      const blocked = source === "external";
      clipboard(rec, "paste", text, e.timeStamp, { source, blocked });
      if (!blocked) { markInternal("paste"); return false; }
      e.preventDefault();
      guard.onBlocked("paste");
      return true;
    },
    drop(e, view) {
      if (!guard) return false;
      const text = e.dataTransfer?.getData("text/plain") ?? "";
      const files = (e.dataTransfer?.files?.length ?? 0) > 0;
      const source: PasteSource = dragStartedInside() && !files ? (classify(text, () => own(view)) === "page" ? "page" : "editor")
        : "external";
      const blocked = source === "external";
      clipboard(rec, "drop", text, e.timeStamp, { source, blocked });
      if (!blocked) { markInternal("drop"); return false; }
      e.preventDefault();
      guard.onBlocked("drop");
      return true;
    },
    copy(e, view) { clipboard(rec, "copy", selectedText(view), e.timeStamp); },
    cut(e, view) { clipboard(rec, "cut", selectedText(view), e.timeStamp); },
    focus(e) { rec.log("focus", { target: "editor", state: "in" }, e.timeStamp); },
    blur(e) { rec.log("focus", { target: "editor", state: "out" }, e.timeStamp); },
  });

  // While a guarded editor is mounted, copies anywhere on the page are remembered (pasteguard.track).
  const tracking = guard ? [ViewPlugin.define(() => ({ destroy: track() }))] : [];

  return [updates, keys, dom, tracking];
}

function selectedText(view: EditorView): string {
  return view.state.selection.ranges.map((r) => view.state.sliceDoc(r.from, r.to)).join("\n");
}

/** Window focus and tab visibility; returns a function that removes the listeners. */
export function captureWindow(rec: Recorder): () => void {
  const on = (e: Event) => rec.log("focus", { target: "window", state: "in" }, e.timeStamp);
  const off = (e: Event) => rec.log("focus", { target: "window", state: "out" }, e.timeStamp);
  const vis = (e: Event) =>
    rec.log("focus", { target: "page", state: document.visibilityState === "visible" ? "in" : "out" }, e.timeStamp);
  window.addEventListener("focus", on);
  window.addEventListener("blur", off);
  document.addEventListener("visibilitychange", vis);
  return () => {
    window.removeEventListener("focus", on);
    window.removeEventListener("blur", off);
    document.removeEventListener("visibilitychange", vis);
  };
}
