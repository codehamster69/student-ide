import { useEffect, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, animate, motion, useMotionValue, useTransform } from "motion/react";
import { ArrowDown, ArrowUp, Award, Bug, Crown, Medal, Sparkles, Timer, Zap } from "lucide-react";
import { cn, duration, ease, spring } from "../ui";
import { clock, secondsLeft, type BadgeInfo, type BoardRow, type CompSettings } from "./api";

const MEDAL = [
  "bg-gold-soft text-gold ring-gold/30",
  "bg-silver-soft text-silver ring-silver/30",
  "bg-bronze-soft text-bronze ring-bronze/30",
];

/** A number that counts up to its new value instead of jumping. */
export function Ticker({ value, className }: { value: number; className?: string }) {
  const mv = useMotionValue(value);
  const text = useTransform(mv, (v) => Math.round(v).toLocaleString());
  useEffect(() => {
    const c = animate(mv, value, { duration: 0.8, ease: ease.out });
    return () => c.stop();
  }, [mv, value]);
  return <motion.span className={cn("tabular-nums", className)}>{text}</motion.span>;
}

/** Medals only go to someone who has scored: at 0 points nobody is "first". */
export function RankMark({ rank, points = 1, className }: { rank: number; points?: number; className?: string }) {
  const medal = rank <= 3 && points > 0;
  return (
    <span className={cn(
      "grid size-8 shrink-0 place-items-center rounded-full text-[13px] font-semibold tabular-nums ring-1",
      medal ? MEDAL[rank - 1] : "bg-surface-2 text-muted ring-border",
      className,
    )}>
      {rank === 1 && medal ? <Crown className="size-4" /> : rank}
    </span>
  );
}

const BADGE_ICON: Record<string, typeof Award> = { first_solve: Zap, clean_sweep: Sparkles, comeback: Bug };

export function BadgeChip({ b }: { b: BadgeInfo }) {
  const Icon = BADGE_ICON[b.id] ?? (b.id.startsWith("fastest") ? Timer : Award);
  return (
    <motion.span initial={{ opacity: 0, scale: 0.7 }} animate={{ opacity: 1, scale: 1 }} transition={spring}
      className="inline-flex h-5 items-center gap-1 rounded-full bg-accent-soft px-2 text-[11px] font-medium text-accent">
      <Icon className="size-3" />{b.label}
    </motion.span>
  );
}

/**
 * Live ranking. Rows glide to their new place (layout animation) when the
 * order changes, points count up, and a small arrow shows who just moved.
 */
export function Leaderboard({ rows, nQuestions, size = "md", showIds = false, empty }: {
  rows: BoardRow[];
  nQuestions: number;
  size?: "md" | "lg";
  showIds?: boolean;
  empty?: string;
}) {
  const prev = useRef(new Map<string, number>());
  const [moves, setMoves] = useState(new Map<string, number>());
  useEffect(() => {
    const m = new Map<string, number>();
    rows.forEach((r) => {
      const before = prev.current.get(r.handle);
      if (before !== undefined && before !== r.rank) m.set(r.handle, before - r.rank);
    });
    prev.current = new Map(rows.map((r) => [r.handle, r.rank]));
    if (m.size) {
      setMoves(m);
      const t = window.setTimeout(() => setMoves(new Map()), 2600);
      return () => window.clearTimeout(t);
    }
  }, [rows]);

  if (!rows.length) {
    return <p className="px-5 py-10 text-center text-sm text-muted">{empty ?? "No scores yet."}</p>;
  }
  const big = size === "lg";
  return (
    <LayoutGroup>
      <motion.ol layout className="grid gap-1.5">
        <AnimatePresence initial={false}>
          {rows.map((r) => {
            const moved = moves.get(r.handle);
            return (
              <motion.li key={r.handle} layout="position" transition={spring}
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                className={cn(
                  "relative flex items-center gap-3 rounded-xl border px-3",
                  big ? "py-3" : "py-2",
                  r.me ? "border-accent/50 bg-accent-soft/60" : "border-border bg-surface",
                  r.rank === 1 && r.points > 0 && !r.me && "border-gold/40",
                )}>
                <RankMark rank={r.rank} points={r.points} className={big ? "size-10 text-base" : undefined} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <strong className={cn("truncate font-semibold text-text", big ? "text-lg" : "text-sm")}>{r.handle}</strong>
                    {r.me && <span className="rounded-full bg-accent px-1.5 text-[10px] font-semibold uppercase tracking-wide text-accent-fg">You</span>}
                    {showIds && r.student_id && r.student_id !== r.handle && (
                      <span className="font-mono text-[11px] text-faint">{r.student_id}</span>
                    )}
                    <AnimatePresence>
                      {moved !== undefined && (
                        <motion.span initial={{ opacity: 0, y: moved > 0 ? 6 : -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                          className={cn("inline-flex items-center text-[11px] font-semibold", moved > 0 ? "text-success" : "text-faint")}>
                          {moved > 0 ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />}{Math.abs(moved)}
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </span>
                  {r.badges.length > 0 && <span className="mt-1 flex flex-wrap gap-1">{r.badges.map((b) => <BadgeChip key={b.id} b={b} />)}</span>}
                </span>
                <SolvedDots solved={r.solved} n={nQuestions} />
                <span className={cn("w-16 text-right font-semibold text-text", big ? "text-2xl" : "text-base")}>
                  <Ticker value={r.points} />
                </span>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </motion.ol>
    </LayoutGroup>
  );
}

function SolvedDots({ solved, n }: { solved: number; n: number }) {
  if (n > 8) return <span className="text-xs tabular-nums text-muted">{solved}/{n} solved</span>;
  return (
    <span className="hidden items-center gap-1 sm:flex" title={`${solved} of ${n} solved`}>
      {Array.from({ length: n }, (_, i) => (
        <motion.span key={i} animate={{ scale: i < solved ? 1 : 0.8 }} transition={spring}
          className={cn("size-2 rounded-full", i < solved ? "bg-success" : "bg-surface-3")} />
      ))}
    </span>
  );
}

/** Ticking clock; amber in the last minute. Untimed competitions show "No clock". */
export function Countdown({ comp, offset, className }: { comp: Pick<CompSettings, "ends_at" | "state">; offset: number; className?: string }) {
  const [, tick] = useState(0);
  useEffect(() => {
    if (comp.state !== "live") return;
    const t = window.setInterval(() => tick((n) => n + 1), 250);
    return () => window.clearInterval(t);
  }, [comp.state]);
  const left = secondsLeft(comp, offset);
  const urgent = left !== null && left < 60 && comp.state === "live";
  return (
    <span className={cn("inline-flex items-center gap-1.5 font-mono font-semibold tabular-nums", urgent ? "text-warn" : "text-text", className)}
      role="timer" aria-live="off">
      <Timer className={cn("size-[0.9em]", urgent && "animate-pulse")} />
      {comp.state === "ended" ? "Time's up" : left === null ? "No clock" : clock(left)}
    </span>
  );
}

/** Top three on rising steps, for the end of a competition. */
export function Podium({ rows }: { rows: BoardRow[] }) {
  const order = [1, 0, 2].map((i) => rows[i]).filter((r) => r && r.points > 0);
  const height = ["h-28", "h-20", "h-14"];
  return (
    <div className="flex items-end justify-center gap-3 pt-4">
      {order.map((r) => (
        <motion.div key={r.handle} className="flex w-32 flex-col items-center gap-2"
          initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 + (3 - r.rank) * 0.25, duration: duration.slow, ease: ease.out }}>
          {r.rank === 1 ? <Crown className="size-6 text-gold" /> : <Medal className={cn("size-5", r.rank === 2 ? "text-silver" : "text-bronze")} />}
          <strong className="max-w-full truncate text-sm font-semibold text-text">{r.handle}</strong>
          <span className="text-xs tabular-nums text-muted">{r.points} pts</span>
          <motion.div initial={{ scaleY: 0 }} animate={{ scaleY: 1 }} style={{ originY: 1 }}
            transition={{ delay: 0.35 + (3 - r.rank) * 0.25, duration: duration.slow, ease: ease.out }}
            className={cn("grid w-full place-items-center rounded-t-xl text-2xl font-bold ring-1", height[r.rank - 1], MEDAL[r.rank - 1])}>
            {r.rank}
          </motion.div>
        </motion.div>
      ))}
    </div>
  );
}
