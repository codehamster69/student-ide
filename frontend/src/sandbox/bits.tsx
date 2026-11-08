// Shared pieces of the Sandbox Labs pages: a CodeMirror file editor, the
// preview terminal (xterm.js over a WebSocket), base icons and badges.
import { useEffect, useRef } from "react";
import { basicSetup } from "codemirror";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { indentUnit } from "@codemirror/language";
import { python } from "@codemirror/lang-python";
import { cpp } from "@codemirror/lang-cpp";
import { java } from "@codemirror/lang-java";
import { javascript } from "@codemirror/lang-javascript";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { Binary, Coffee, Database, Globe, SquareTerminal, Braces, type LucideIcon } from "lucide-react";
import { Badge } from "../ui";
import { editorTheme } from "../editor/theme";
import { BUILD, type Base, type BuildStatus, type Network } from "./api";

export const BASE_ICON: Record<Base, LucideIcon> = {
  "c-cpp": Binary, python: Braces, java: Coffee, linux: SquareTerminal, "web-node": Globe, databases: Database,
};

export function BuildBadge({ status }: { status: BuildStatus }) {
  return <Badge tone={BUILD[status].tone}>{BUILD[status].label}</Badge>;
}

export function NetworkBadge({ network }: { network: Network }) {
  const label = { open: "Open internet", registries: "Registries only", off: "No network" }[network];
  return <Badge tone={network === "open" ? "warn" : "neutral"}>{label}</Badge>;
}

function languageFor(path: string) {
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "py") return python();
  if (["c", "h", "cpp", "cc", "hpp", "cxx"].includes(ext)) return cpp();
  if (ext === "java") return java();
  if (["js", "mjs", "ts", "tsx", "jsx", "json"].includes(ext)) return javascript({ typescript: ext.startsWith("ts") });
  return [];
}

/** One file in CodeMirror. Remounts per `path` (key it by path); edits go to onChange. */
export function FileEditor({ path, value, onChange, readOnly = false, extensions = [] }: {
  path: string; value: string; onChange?: (v: string) => void; readOnly?: boolean;
  /** e.g. the recorder's captureExtension (student Sandbox labs in the desktop app) */
  extensions?: Extension[];
}) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const cb = useRef(onChange);
  cb.current = onChange;

  useEffect(() => {
    view.current = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: value,
        extensions: [basicSetup, languageFor(path), editorTheme, indentUnit.of("    "),
          EditorState.readOnly.of(readOnly), EditorView.theme({ "&": { fontSize: "13px", height: "100%" } }),
          EditorView.updateListener.of((u) => { if (u.docChanged) cb.current?.(u.state.doc.toString()); }), ...extensions],
      }),
    });
    return () => view.current?.destroy();
    // created once per file; the parent keys this by path
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {  // a value from outside (e.g. reloaded from the instance)
    const v = view.current;
    // origin "reload": the file changed on disk (terminal, vim, a compiler); the detector skips it like "reset"
    if (v && v.state.doc.toString() !== value) v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value }, userEvent: "reload" });
  }, [value]);

  return <div ref={host} className="h-full min-h-0 overflow-hidden [&_.cm-editor]:h-full [&_.cm-scroller]:font-mono" />;
}

/** A shell in the preview instance. The server speaks JSON in ({type: input|resize}) and text out. */
export function PreviewTerminal({ url, onClosed }: { url: string; onClosed?: () => void }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const css = getComputedStyle(document.documentElement);
    const term = new XTerm({
      fontFamily: css.getPropertyValue("--font-mono") || "monospace", fontSize: 13, cursorBlink: true,
      theme: { background: css.getPropertyValue("--console").trim() || "#111", foreground: css.getPropertyValue("--console-text").trim() || "#eee" },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(host.current!);
    const ws = new WebSocket(url.replace(/^http/, "ws"));
    const resize = () => {
      try { fit.fit(); } catch { /* hidden */ }
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
    };
    ws.onopen = resize;
    ws.onmessage = (e) => term.write(typeof e.data === "string" ? e.data : "");
    ws.onclose = (e) => { term.write(`\r\n\x1b[2m[terminal closed${e.reason ? `: ${e.reason}` : ""}]\x1b[0m\r\n`); onClosed?.(); };
    const sub = term.onData((data) => ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify({ type: "input", data })));
    const ro = new ResizeObserver(resize);
    ro.observe(host.current!);
    return () => { ro.disconnect(); sub.dispose(); ws.close(); term.dispose(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);
  return <div ref={host} className="h-full min-h-0 overflow-hidden rounded-lg bg-console p-2" />;
}

export const mb = (n: number | null | undefined) => (n == null ? "?" : n >= 1000 ? `${(n / 1000).toFixed(1)} GB` : `${n} MB`);
