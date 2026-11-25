// Paste guard: in study contexts students may paste only what they copied inside Scribelab.
//
// Rohan's rule (2026-11-25): copying and pasting your own code around the IDE is normal editing,
// even across question tabs of a sitting; pasting text copied from another page or app (an LLM, a
// website) is blocked with a short notice, and the attempt is logged as a clipboard event
// {blocked: true}. The guard never reads the system clipboard on its own: it only remembers what was
// copied, cut or dragged while a guarded editor is on screen (a short hash in localStorage, so it
// survives a reload and works across tabs of this site) and compares a paste against that list and
// against the student's own open documents.
//
// Sources of an allowed paste, logged on the clipboard event as `source`:
//   "editor"   copied from a guarded code editor (or the desktop terminal),
//   "page"     copied from read-only text on a guarded screen (question statement, output),
//   "document" the text already exists in one of the student's open documents.
// Copies from form fields (stdin box, search) never count, so text pasted into them can't be laundered.
// Not covered: text typed in by a browser extension or IME, which the detector still sees as typing.

const STORE = "scribelab.copies";
const MAX_ENTRIES = 100;
const TTL_MS = 24 * 3600_000;

export type PasteSource = "editor" | "page" | "document" | "external";

/** Clipboard text compared the way different platforms hand it back (CRLF, nbsp, trailing spaces). */
export function normalize(text: string): string {
  return text.replace(/\r\n?/g, "\n").replace(/ /g, " ").replace(/[ \t]+$/gm, "").trim();
}

/** cyrb53: a fast 53-bit string hash. Matching only, not security. */
export function hash(s: string): string {
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 2654435761);
    h2 = Math.imul(h2 ^ c, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
}

type Entry = { h: string; src: "editor" | "page"; at: number };
let memory: Entry[] = []; // fallback when localStorage is blocked

function load(): Entry[] {
  try {
    const raw = localStorage.getItem(STORE);
    if (raw) memory = (JSON.parse(raw) as Entry[]).filter((e) => e && typeof e.h === "string");
  } catch { /* private mode: keep memory */ }
  const cutoff = Date.now() - TTL_MS;
  return (memory = memory.filter((e) => e.at >= cutoff));
}

function save(list: Entry[]) {
  memory = list.slice(-MAX_ENTRIES);
  try { localStorage.setItem(STORE, JSON.stringify(memory)); } catch { /* memory only */ }
}

/** Remember text copied inside Scribelab. */
export function remember(text: string, src: "editor" | "page") {
  const n = normalize(text);
  if (!n) return;
  const h = hash(n);
  save([...load().filter((e) => e.h !== h), { h, src, at: Date.now() }]);
}

/** Where pasted text came from; "external" means it should be blocked. */
export function classify(text: string, ownText: () => string[] = () => []): PasteSource {
  const n = normalize(text);
  if (!n) return "document"; // whitespace only: nothing to block
  const hit = load().find((e) => e.h === hash(n));
  if (hit) return hit.src;
  if (ownText().some((d) => normalize(d).includes(n))) return "document";
  return "external";
}

export function forget() {
  memory = [];
  try { localStorage.removeItem(STORE); } catch { /* nothing */ }
}

// ---- page-wide copy/drag tracking, on while at least one guarded editor is mounted ----

let users = 0;
let dragInside = false;

function isFormField(el: Element | null): boolean {
  if (!el) return false;
  if (el.closest(".cm-editor, .xterm")) return false; // CodeMirror's and xterm's own inputs are editors
  return !!el.closest("input, textarea, select, [contenteditable=''], [contenteditable='true']");
}

function sourceOf(e: Event): "editor" | "page" | null {
  const t = e.target instanceof Element ? e.target : (e.target as Node | null)?.parentElement ?? null;
  if (t?.closest(".cm-editor, .xterm")) return "editor";
  if (isFormField(t) || isFormField(document.activeElement)) return null;
  return "page";
}

// Bubble phase on document: CodeMirror/xterm have already put their text on clipboardData.
function onCopy(e: ClipboardEvent) {
  const src = sourceOf(e);
  if (!src) return;
  const text = e.clipboardData?.getData("text/plain") || window.getSelection()?.toString() || "";
  remember(text, src);
}

function onDragStart(e: DragEvent) {
  const src = sourceOf(e);
  dragInside = !!src;
  if (!src) return;
  const text = e.dataTransfer?.getData("text/plain") || window.getSelection()?.toString() || "";
  remember(text, src);
}

function onDragEnd() {
  // drop fires before dragend, so the flag is still set while the editor handles the drop
  setTimeout(() => { dragInside = false; }, 0);
}

/** Did the drag being dropped start on this page (outside a form field)? */
export function dragStartedInside(): boolean {
  return dragInside;
}

/** Start page-wide tracking; returns the matching release. Reference-counted. */
export function track(): () => void {
  if (users++ === 0) {
    document.addEventListener("copy", onCopy);
    document.addEventListener("cut", onCopy);
    document.addEventListener("dragstart", onDragStart);
    document.addEventListener("dragend", onDragEnd);
  }
  let released = false;
  return () => {
    if (released) return;
    released = true;
    if (--users === 0) {
      document.removeEventListener("copy", onCopy);
      document.removeEventListener("cut", onCopy);
      document.removeEventListener("dragstart", onDragStart);
      document.removeEventListener("dragend", onDragEnd);
      dragInside = false;
    }
  };
}

/** The notice students see, one wording everywhere (editor, desktop terminal). */
export const BLOCKED_NOTICE =
  "Pasting from outside Scribelab is turned off here. Copy and paste within your own code still works.";
