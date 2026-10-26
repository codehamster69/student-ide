// Turns editor and browser activity into recorder events.

import { Transaction, type Extension } from "@codemirror/state";
import { EditorView, ViewPlugin } from "@codemirror/view";
import type { Recorder } from "./recorder";

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

function keyData(e: KeyboardEvent, action: "down" | "up") {
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

function clipboard(rec: Recorder, action: "paste" | "copy" | "cut", text: string, ts: number) {
  rec.log("clipboard", {
    action,
    length: text.length,
    lines: lineCount(text),
    text: text.slice(0, MAX_CLIPBOARD),
    truncated: text.length > MAX_CLIPBOARD,
  }, ts);
}

/** CodeMirror extension that records keys, edits, clipboard, cursor and focus. */
export function captureExtension(rec: Recorder): Extension {
  let lastCursor = 0;
  let pendingCursor: number | undefined;

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
        origin: tr.annotation(Transaction.userEvent) ?? "unknown",
        changes,
        len_before: tr.startState.doc.length,
        len_after: tr.newDoc.length,
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
    const down = (e: KeyboardEvent) => rec.log("key", keyData(e, "down"), e.timeStamp);
    const up = (e: KeyboardEvent) => rec.log("key", keyData(e, "up"), e.timeStamp);
    view.dom.addEventListener("keydown", down, true);
    view.dom.addEventListener("keyup", up, true);
    return {
      destroy() {
        view.dom.removeEventListener("keydown", down, true);
        view.dom.removeEventListener("keyup", up, true);
      },
    };
  });

  const dom = EditorView.domEventHandlers({
    paste(e) { clipboard(rec, "paste", e.clipboardData?.getData("text/plain") ?? "", e.timeStamp); },
    copy(e, view) { clipboard(rec, "copy", selectedText(view), e.timeStamp); },
    cut(e, view) { clipboard(rec, "cut", selectedText(view), e.timeStamp); },
    focus(e) { rec.log("focus", { target: "editor", state: "in" }, e.timeStamp); },
    blur(e) { rec.log("focus", { target: "editor", state: "out" }, e.timeStamp); },
  });

  return [updates, keys, dom];
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
