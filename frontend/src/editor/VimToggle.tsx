// The editor's Vim mode switch for a toolbar or status bar (see vim.ts).
import { cn } from "../ui";

export function VimToggle({ on, onChange, className }: { on: boolean; onChange: (on: boolean) => void; className?: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} onClick={() => onChange(!on)}
      title={on ? "Vim keys are on: Esc for normal mode, i to type. Click to turn off." : "Use Vim key bindings in this editor"}
      className={cn("inline-flex h-7 items-center gap-1.5 rounded-md px-2 font-mono text-[11px] font-medium transition-colors",
        on ? "bg-accent-soft text-accent" : "text-muted hover:bg-surface-2 hover:text-text", className)}>
      <span className={cn("relative h-3.5 w-6 rounded-full transition-colors", on ? "bg-accent" : "bg-surface-3")}>
        <span className={cn("absolute top-0.5 size-2.5 rounded-full bg-surface shadow-sm transition-all", on ? "left-3" : "left-0.5")} />
      </span>
      Vim
    </button>
  );
}
