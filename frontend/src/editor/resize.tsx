import { useCallback, useRef, useState } from "react";
import { cn } from "../ui";

/**
 * A pane size the student can drag, remembered in this browser. `null` means
 * "the layout's default" until the student first drags it (double-click the
 * handle to go back to that).
 */
export function usePaneSize(key: string): [number | null, (px: number | null) => void] {
  const storage = `studentide.pane.${key}`;
  const [size, setSize] = useState<number | null>(() => {
    try {
      const v = Number(localStorage.getItem(storage));
      return v > 0 ? v : null;
    } catch { return null; } // private mode
  });
  const set = useCallback((px: number | null) => {
    setSize(px);
    try {
      if (px === null) localStorage.removeItem(storage);
      else localStorage.setItem(storage, String(Math.round(px)));
    } catch { /* private mode */ }
  }, [storage]);
  return [size, set];
}

/**
 * A drag handle between two panes. `measure` turns the pointer position into
 * the new size (and clamps it); arrow keys move it 16 px at a time.
 */
export function ResizeHandle({ orientation, label, size, measure, onResize, onDragging, className }: {
  /** "vertical": a bar between side-by-side panes (drag left/right) */
  orientation: "vertical" | "horizontal";
  label: string;
  /** current size in px, for keyboard steps */
  size: () => number;
  measure: (e: { clientX: number; clientY: number }) => number;
  onResize: (px: number | null) => void;
  onDragging?: (on: boolean) => void;
  className?: string;
}) {
  const dragging = useRef(false);
  const vertical = orientation === "vertical";
  return (
    <div
      role="separator"
      aria-orientation={vertical ? "vertical" : "horizontal"}
      aria-label={label}
      tabIndex={0}
      title={`${label}: drag to resize, double-click to reset`}
      onPointerDown={(e) => {
        e.preventDefault();
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
        dragging.current = true;
        onDragging?.(true);
        document.body.style.cursor = vertical ? "col-resize" : "row-resize";
      }}
      onPointerMove={(e) => { if (dragging.current) onResize(measure(e)); }}
      onPointerUp={(e) => {
        dragging.current = false;
        onDragging?.(false);
        document.body.style.cursor = "";
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      }}
      onDoubleClick={() => onResize(null)}
      onKeyDown={(e) => {
        const grow = vertical ? e.key === "ArrowRight" : e.key === "ArrowUp";
        const shrink = vertical ? e.key === "ArrowLeft" : e.key === "ArrowDown";
        if (grow || shrink) {
          e.preventDefault();
          onResize(size() + (grow ? 16 : -16));
        }
      }}
      className={cn(
        "group z-20 shrink-0 touch-none outline-none",
        vertical ? "w-1.5 cursor-col-resize" : "h-1.5 cursor-row-resize",
        className,
      )}
    >
      <span className={cn("absolute rounded-full bg-transparent transition-colors group-hover:bg-accent/50 group-focus-visible:bg-accent group-active:bg-accent",
        vertical ? "inset-y-0 left-1/2 w-0.5 -translate-x-1/2" : "inset-x-0 top-1/2 h-0.5 -translate-y-1/2")} />
    </div>
  );
}

export const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
