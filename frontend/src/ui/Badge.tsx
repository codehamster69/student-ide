import type { ReactNode } from "react";
import { cn } from "./cn";

export type Tone = "neutral" | "accent" | "success" | "warn" | "danger";

const tones: Record<Tone, string> = {
  neutral: "bg-surface-2 text-muted border-border",
  accent: "bg-accent-soft text-accent border-transparent",
  success: "bg-success-soft text-success border-transparent",
  warn: "bg-warn-soft text-warn border-transparent",
  danger: "bg-danger-soft text-danger border-transparent",
};

export function Badge({ tone = "neutral", className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return (
    <span className={cn("inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium", tones[tone], className)}>
      {children}
    </span>
  );
}

/** A dot that radiates a soft ring (CSS only, runs on the compositor). */
export function LiveDot({ tone = "success", live = true }: { tone?: Tone; live?: boolean }) {
  const color = { neutral: "bg-faint", accent: "bg-accent", success: "bg-success", warn: "bg-warn", danger: "bg-danger" }[tone];
  return (
    <span className="relative inline-flex size-2">
      {live && <span className={cn("absolute inset-0 rounded-full animate-pulse-ring", color)} />}
      <span className={cn("relative inline-flex size-2 rounded-full", color)} />
    </span>
  );
}

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd className={cn(
      "inline-flex h-5 min-w-5 items-center justify-center rounded border border-current/20 px-1 font-sans text-[11px] font-medium opacity-80",
      className,
    )}>
      {children}
    </kbd>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={cn("size-4 animate-spin", className)} fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
