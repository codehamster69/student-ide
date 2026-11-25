// The desktop app's update card. Updates are mandatory (desktop/app/src/main/modules/updates.ts):
// once the server needs a newer version the card can't be closed and "Update now"
// takes the app to its update page; otherwise the app updates by itself when idle.
// A plain note when a new version is merely ready. Never during an editor session:
// the session layer hides it, so nothing interrupts a lab. Absent in browsers.
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Download, RefreshCw, X } from "lucide-react";
import { desktop, desktopError } from "../desktop";
import type { UpdateStatus } from "../../../desktop/app/src/shared/contract";
import { spring } from "../ui";

export function DesktopUpdate({ hidden }: { hidden: boolean }) {
  const [st, setSt] = useState<UpdateStatus | null>(null);
  const [closed, setClosed] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => {
    const u = desktop?.updates;
    if (!u || !desktop) return;
    u.status().then(setSt, () => {});
    return desktop.on("updates.status", setSt);
  }, []);
  const required = Boolean(st?.required);
  const show = st && !hidden && (required || (closed !== st.latest &&
    (st.state === "ready" || (st.mode === "manual" && st.state === "available" && st.downloadUrl))));
  const updateNow = () => desktop?.updates?.updateNow?.().catch((e) => setErr(desktopError(e).message));
  return (
    <AnimatePresence>
      {show && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0, transition: spring }} exit={{ opacity: 0, y: 12 }}
          role="status" className="fixed bottom-4 right-4 z-50 flex max-w-sm items-start gap-3 rounded-xl border border-border bg-surface p-3.5 text-xs text-muted shadow-lg">
          <span className="grid size-7 shrink-0 place-items-center rounded-full border border-cta/40 text-cta">
            {st.state === "ready" ? <RefreshCw className="size-3.5" /> : <Download className="size-3.5" />}
          </span>
          <div className="grid gap-1.5">
            {required ? (
              <p><strong className="font-semibold text-text">Update required.</strong>{" "}
                Scribelab {st.minVersion ?? st.latest} is out and every copy needs it before new work starts.
                {st.state === "downloading" ? ` Downloading… ${st.percent ?? 0}%.` : ""} Your work is saved either way.</p>
            ) : (
              <p><strong className="font-semibold text-text">Scribelab {st.latest} is {st.state === "ready" ? "ready" : "out"}.</strong>{" "}
                {st.state === "ready" ? "It installs by itself when you're not in a lab. Your work is saved either way." : st.reason}</p>
            )}
            {err && <p className="text-danger">{err}</p>}
            <div className="flex gap-2">
              {required ? (
                <button className="h-7 rounded-full border border-transparent px-3 font-semibold text-cta transition-[border-color,transform,box-shadow] hover:border-cta hover:shadow-[var(--button-glow)] hover:-translate-y-px focus-visible:border-cta" onClick={updateNow}>Update now</button>
              ) : st.state === "ready" ? (
                <button className="h-7 rounded-full border border-transparent px-3 font-semibold text-cta transition-[border-color,transform,box-shadow] hover:border-cta hover:shadow-[var(--button-glow)] hover:-translate-y-px focus-visible:border-cta" onClick={() => desktop?.updates?.restart().catch((e) => setErr(desktopError(e).message))}>Restart now</button>
              ) : (
                <button className="h-7 rounded-full border border-transparent px-3 font-semibold text-cta transition-[border-color,transform,box-shadow] hover:border-cta hover:shadow-[var(--button-glow)] hover:-translate-y-px focus-visible:border-cta" onClick={() => desktop?.app.openExternal(st.downloadUrl!)}>Download</button>
              )}
              {!required && <button className="h-7 rounded-full border border-transparent px-3 font-medium text-text transition-[border-color] hover:border-border-strong" onClick={() => setClosed(st.latest ?? "")}>Later</button>}
            </div>
          </div>
          {!required && <button aria-label="Close" onClick={() => setClosed(st.latest ?? "")}><X className="size-3.5" /></button>}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Tells the desktop app a lab, sitting or competition is open, so a mandatory update waits for it. */
export function DesktopBusy({ busy }: { busy: boolean }) {
  useEffect(() => {
    void desktop?.updates?.setBusy?.(busy).catch(() => {});
  }, [busy]);
  useEffect(() => () => { void desktop?.updates?.setBusy?.(false).catch(() => {}); }, []);
  return null;
}
