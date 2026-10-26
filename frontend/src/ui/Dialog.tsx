import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { fade, pop } from "./motion";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  /** Buttons; the one marked data-autofocus gets focus on open. */
  actions: ReactNode;
}

export function Dialog({ open, onClose, title, description, icon, actions }: DialogProps) {
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const t = window.setTimeout(() => panel.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus(), 30);
    return () => { window.removeEventListener("keydown", onKey); window.clearTimeout(t); };
  }, [open, onClose]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 grid place-items-center p-4" initial="initial" animate="animate" exit="exit">
          <motion.div variants={fade} className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" onClick={onClose} />
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby="dialog-title"
            variants={pop}
            className="relative w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-lg"
          >
            <div className="flex gap-4">
              {icon && <div className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">{icon}</div>}
              <div className="grid gap-1.5">
                <h2 id="dialog-title" className="text-base font-semibold text-text">{title}</h2>
                {description && <div className="text-sm leading-relaxed text-muted">{description}</div>}
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">{actions}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
