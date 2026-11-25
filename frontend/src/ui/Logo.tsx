import { cn } from "./cn";

/**
 * Brand mark: a strip of typing-rhythm bars (one bar per gap between keys, as on the
 * review replay) ending in a text caret. It is the product's one signature motif.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7 shrink-0", className)} aria-hidden>
      <rect x="0.5" y="0.5" width="31" height="31" rx="8" className="fill-accent" />
      <g className="fill-accent-fg">
        <rect x="6" y="15" width="3" height="9" rx="1.5" />
        <rect x="11" y="10" width="3" height="14" rx="1.5" />
        <rect x="16" y="17.5" width="3" height="6.5" rx="1.5" />
        <rect x="21" y="12.5" width="3" height="11.5" rx="1.5" fillOpacity="0.55" />
      </g>
      <rect x="25.5" y="8" width="1.6" height="16" rx="0.8" className="fill-accent-fg" />
    </svg>
  );
}

export function Logo({ className, subtitle }: { className?: string; subtitle?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="grid leading-tight">
        <span className="text-[15px] font-semibold tracking-tight text-text">Student IDE</span>
        {subtitle && <span className="text-[11px] text-muted">{subtitle}</span>}
      </span>
    </span>
  );
}
