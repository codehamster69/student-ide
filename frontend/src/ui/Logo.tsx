import { cn } from "./cn";

/**
 * Brand mark: a pen nib (the scribe) finishing a line of keystrokes, drawn as
 * dashes of different lengths like the gaps on the review replay. The nib's slit
 * doubles as a text caret. Same drawing in public/favicon.svg, the desktop
 * pages and the app icon (desktop/installer/packaging/build/icon.svg).
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7 shrink-0", className)} aria-hidden>
      <rect x="0.5" y="0.5" width="31" height="31" rx="8" className="fill-accent" />
      <g className="fill-accent-fg">
        <path
          fillRule="evenodd"
          transform="translate(15.2 21.8) rotate(40) scale(0.86) translate(-16 -24.5)"
          d="M11 6.5H21V11.5C21 15 18.9 18.6 16 24.5C13.1 18.6 11 15 11 11.5Z M14.4 10.6a1.6 1.6 0 1 0 3.2 0a1.6 1.6 0 1 0-3.2 0Z M15.45 12.6H16.55V22.2L16 23.3L15.45 22.2Z"
        />
        <rect x="5.2" y="20.8" width="3.2" height="2" rx="1" fillOpacity=".45" />
        <rect x="9.4" y="20.8" width="2" height="2" rx="1" fillOpacity=".7" />
        <rect x="12.4" y="20.8" width="2.4" height="2" rx="1" />
      </g>
    </svg>
  );
}

export function Logo({ className, subtitle }: { className?: string; subtitle?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark />
      <span className="grid leading-tight">
        <span className="text-[15px] font-semibold tracking-tight text-text">Scribelab</span>
        {subtitle && <span className="text-[11px] text-muted">{subtitle}</span>}
      </span>
    </span>
  );
}
