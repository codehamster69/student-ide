import { useId } from "react";
import { cn } from "./cn";

/** Brand gradient (violet, pink, orange), shared by the mark and the wordmark's "lab". */
export const BRAND_GRADIENT = "linear-gradient(90deg, #7C3AED, #EC4899, #FB923C)";

/**
 * Brand mark ("Squiggle"): a hand-drawn "s" (the scribe's stroke) with a yellow text caret,
 * on a sunset gradient. Fixed colours on purpose, so it looks the same in light and dark.
 * Same drawing in public/favicon.svg, the desktop pages and the app icon
 * (desktop/installer/packaging/build/icon.svg).
 */
export function LogoMark({ className }: { className?: string }) {
  const id = `brand-${useId().replace(/:/g, "")}`;
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7 shrink-0", className)} aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7C3AED" />
          <stop offset=".55" stopColor="#EC4899" />
          <stop offset="1" stopColor="#FB923C" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${id})`} />
      <path d="M20.6 10.4C18.6 8.2 11.2 8.4 11.2 12.4C11.2 16.6 20.8 15.4 20.8 19.8C20.8 24 13.2 24.4 10.6 21.6" fill="none" stroke="#fff" strokeWidth="4.2" strokeLinecap="round" />
      <rect x="23.2" y="18.4" width="2.8" height="7" rx="1.4" fill="#FDE047" />
    </svg>
  );
}

export function Logo({ className, subtitle }: { className?: string; subtitle?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="grid leading-tight">
        <span className="text-[17px] font-extrabold tracking-[-0.03em] text-text">
          scribe<span className="bg-clip-text text-transparent" style={{ backgroundImage: BRAND_GRADIENT }}>lab</span>
        </span>
        {subtitle && <span className="text-[11px] text-muted">{subtitle}</span>}
      </span>
    </span>
  );
}
