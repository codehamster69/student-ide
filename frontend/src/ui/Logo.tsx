import { cn } from "./cn";

/** Brand mark: a keycap with a text caret. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7", className)} aria-hidden>
      <defs>
        <linearGradient id="sid-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="30" height="30" rx="8" fill="url(#sid-g)" />
      <rect x="5.5" y="5" width="21" height="19" rx="4.5" fill="white" fillOpacity="0.16" />
      <path d="M11 11.5l4 3.5-4 3.5" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <rect x="17" y="17" width="5" height="2.2" rx="1.1" fill="white" />
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
