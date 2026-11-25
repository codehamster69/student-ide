/** The short notice shown over the editor (or desktop terminal) when a paste from outside Scribelab is blocked.
 * No motion: it sits over a recording editor, so it just appears and goes after a few seconds. */

import { CircleAlert, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { BLOCKED_NOTICE } from "../pasteguard";

const SHOW_MS = 6000;

export function usePasteNotice() {
  const [open, setOpen] = useState(false);
  const timer = useRef<number>();
  const show = useCallback(() => {
    setOpen(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setOpen(false), SHOW_MS);
  }, []);
  const hide = useCallback(() => { window.clearTimeout(timer.current); setOpen(false); }, []);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  return { open, show, hide };
}

export function PasteNotice({ open, hide }: { open: boolean; hide: () => void }) {
  if (!open) return null;
  return (
    <div role="status" aria-live="polite"
      className="absolute bottom-3 right-3 z-10 flex max-w-sm items-start gap-2 rounded-md border border-l-2 border-warn/50 border-l-warn bg-surface px-3 py-2 text-xs text-text shadow-md">
      <CircleAlert className="mt-px size-3.5 shrink-0 text-warn" aria-hidden />
      <p className="leading-relaxed">{BLOCKED_NOTICE}</p>
      <button onClick={hide} aria-label="Dismiss"
        className="-mr-1 shrink-0 rounded border border-transparent p-0.5 text-muted hover:border-border-strong hover:text-text">
        <X className="size-3.5" />
      </button>
    </div>
  );
}
