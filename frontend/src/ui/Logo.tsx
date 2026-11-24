import { cn } from "./cn";

/**
 * Brand mark ("Acid nib"): a lime pen nib (the scribe) with a pink sparkle on near-black,
 * with a faint lime rim so the tile still reads on dark backgrounds. Fixed colours on
 * purpose, the same in light and dark. Same drawing in public/favicon.svg, the desktop
 * pages and the app icon (desktop/installer/packaging/build/icon.svg).
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7 shrink-0", className)} aria-hidden>
      <rect width="32" height="32" rx="9" fill="#0B0B0F" />
      <rect x="0.4" y="0.4" width="31.2" height="31.2" rx="8.6" fill="none" stroke="#C6F432" strokeOpacity=".45" strokeWidth=".8" />
      <path fill="#C6F432" fillRule="evenodd" transform="rotate(-18 15 17)" d="M9.5 6.5H20.5V11.5C20.5 15.5 18 19.5 15 27C12 19.5 9.5 15.5 9.5 11.5Z M13.3 11.3a1.7 1.7 0 1 0 3.4 0a1.7 1.7 0 1 0-3.4 0Z M14.4 13.4H15.6V22.5L15 23.8L14.4 22.5Z" />
      <path fill="#FF5CA8" d="M24.5 4.5Q25 8 28 8.5Q25 9 24.5 12.5Q24 9 21 8.5Q24 8 24.5 4.5Z" />
    </svg>
  );
}

/** Wordmark: lowercase, heavy, tight; "lab" in the brand lime (token `brand`, darker on light). */
export function Logo({ className, subtitle }: { className?: string; subtitle?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="grid leading-tight">
        <span className="text-[17px] font-black tracking-[-0.04em] text-text">
          scribe<span className="text-brand">lab</span>
        </span>
        {subtitle && <span className="text-[11px] text-muted">{subtitle}</span>}
      </span>
    </span>
  );
}
