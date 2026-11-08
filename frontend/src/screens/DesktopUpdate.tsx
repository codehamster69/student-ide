// A quiet note in the desktop app when a new version is ready (or, for Mac and
// portable builds, ready to download). Never during an editor session: the
// session layer hides it, so nothing interrupts a lab. Absent in browsers.
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
  const show = st && !hidden && closed !== st.latest &&
    (st.state === "ready" || (st.mode === "manual" && st.state === "available" && st.downloadUrl));
  return (
    <AnimatePresence>
      {show && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0, transition: spring }} exit={{ opacity: 0, y: 12 }}
          role="status" className="fixed bottom-4 right-4 z-50 flex max-w-sm items-start gap-3 rounded-2xl border border-border bg-surface p-3.5 text-xs text-muted shadow-lg">
          <span className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
            {st.state === "ready" ? <RefreshCw className="size-3.5" /> : <Download className="size-3.5" />}
          </span>
          <div className="grid gap-1.5">
            <p><strong className="font-semibold text-text">Student IDE {st.latest} is {st.state === "ready" ? "ready" : "out"}.</strong>{" "}
              {st.state === "ready" ? "It installs by itself next time you close the app. Your work is saved either way." : st.reason}</p>
            {err && <p className="text-danger">{err}</p>}
            <div className="flex gap-2">
              {st.state === "ready" ? (
                <button className="h-7 rounded-full bg-accent px-3 font-medium text-accent-fg" onClick={() => desktop?.updates?.restart().catch((e) => setErr(desktopError(e).message))}>Restart now</button>
              ) : (
                <button className="h-7 rounded-full bg-accent px-3 font-medium text-accent-fg" onClick={() => desktop?.app.openExternal(st.downloadUrl!)}>Download</button>
              )}
              <button className="h-7 rounded-full px-3 font-medium text-text hover:bg-surface-2" onClick={() => setClosed(st.latest ?? "")}>Later</button>
            </div>
          </div>
          <button aria-label="Close" onClick={() => setClosed(st.latest ?? "")}><X className="size-3.5" /></button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
