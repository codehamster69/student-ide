// Small pieces shared by the review screens.

import { useEffect, useRef } from "react";
import { animate, motion, useInView } from "motion/react";
import { cn, ease } from "../ui";
import type { Channel } from "./api";

export const CH_COLOR: Record<Channel, string> = { identity: "var(--ch-identity)", process: "var(--ch-process)" };
export const CH_TEXT: Record<Channel, string> = { identity: "Typing rhythm", process: "Way of working" };

/** A number that counts up when it first appears. */
export function CountUp({ to, className }: { to: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  useEffect(() => {
    if (!inView || !ref.current) return;
    const el = ref.current;
    const c = animate(0, to, { duration: 0.9, ease: ease.out, onUpdate: (v) => { el.textContent = String(Math.round(v)); } });
    return () => c.stop();
  }, [inView, to]);
  return <span ref={ref} className={cn("tabular-nums", className)}>0</span>;
}

/** Channel swatch + name, so identity never rests on colour alone. */
export function ChannelTag({ channel, className }: { channel: Channel; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium text-text", className)}>
      <span className="size-2 rounded-full" style={{ background: CH_COLOR[channel] }} />
      {CH_TEXT[channel]}
    </span>
  );
}

/**
 * Both channels' accumulated evidence (CUSUM / threshold) as two thin lines,
 * with the threshold drawn at 1. Lines draw themselves in on mount.
 */
export function Spark({ spark, className }: { spark: Partial<Record<Channel, number[]>>; className?: string }) {
  const W = 160, H = 36, top = 1.4;
  const y = (v: number) => H - 2 - (Math.min(v, top) / top) * (H - 4);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={cn("h-9 w-40", className)} preserveAspectRatio="none" aria-hidden>
      <line x1={0} x2={W} y1={y(1)} y2={y(1)} stroke="var(--border-strong)" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
      {(Object.keys(spark) as Channel[]).map((ch, k) => {
        const pts = spark[ch]!;
        if (pts.length < 2) return null;
        const d = pts.map((v, i) => `${i ? "L" : "M"}${(i / (pts.length - 1)) * W},${y(v)}`).join("");
        return (
          <motion.path key={ch} d={d} fill="none" stroke={CH_COLOR[ch]} strokeWidth={1.75} strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
            initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 0.9, delay: 0.15 + k * 0.12, ease: ease.out }} />
        );
      })}
    </svg>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn("relative overflow-hidden rounded-lg bg-surface-2", className)}>
      <div className="absolute inset-0 animate-shimmer bg-gradient-to-r from-transparent via-surface-3/80 to-transparent" />
    </div>
  );
}
