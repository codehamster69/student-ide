import { cn } from "./cn";

interface RhythmBarsProps {
  /** Intervals in ms, oldest first. Only the last `slots` are drawn. */
  intervals: number[];
  slots?: number;
  /** Interval drawn at full height; longer ones are clipped. */
  maxMs?: number;
  /** Intervals at or above this count as pauses and are drawn muted. */
  pauseMs?: number;
  className?: string;
}

/**
 * Keystroke-rhythm strip: one bar per interval between key presses. Used on
 * the sign-in screen and meant for the teacher timeline. Heights change via
 * transform only, so redraws stay cheap.
 */
export function RhythmBars({ intervals, slots = 40, maxMs = 600, pauseMs = 400, className }: RhythmBarsProps) {
  const shown = intervals.slice(-slots);
  const pad = slots - shown.length;
  return (
    <div className={cn("flex h-12 items-end gap-[3px]", className)} aria-hidden>
      {Array.from({ length: slots }, (_, i) => {
        const ms = i < pad ? 0 : shown[i - pad];
        const h = Math.min(ms, maxMs) / maxMs;
        return (
          <span
            key={i}
            className={cn(
              "h-full flex-1 origin-bottom rounded-full transition-transform duration-300 ease-out",
              ms >= pauseMs ? "bg-faint/50" : "bg-accent",
            )}
            style={{ transform: `scaleY(${Math.max(h, ms ? 0.06 : 0.02)})`, opacity: ms ? 0.35 + 0.65 * (i / slots) : 0.25 }}
          />
        );
      })}
    </div>
  );
}
