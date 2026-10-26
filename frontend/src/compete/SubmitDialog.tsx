import { motion } from "motion/react";
import { CheckCircle2, CircleX, EyeOff, FlaskConical, PartyPopper } from "lucide-react";
import { Button, Dialog, cn, spring } from "../ui";
import type { SubmitResult } from "./api";
import { Ticker } from "./Leaderboard";

/** Test results after Submit: each test ticks in one after another, then the new standing. */
export function SubmitDialog({ verdict, onClose, onLeave }: {
  verdict: SubmitResult | { error: string } | null;
  onClose: () => void;
  onLeave: () => void;
}) {
  const failed = verdict && "error" in verdict;
  const r = verdict && !("error" in verdict) ? verdict : null;
  const solved = !!r && r.passed === r.total;

  return (
    <Dialog
      open={!!verdict}
      onClose={onClose}
      icon={solved ? <PartyPopper className="size-5" /> : <FlaskConical className="size-5" />}
      title={failed ? "Could not submit" : solved ? "All tests passed!" : `${r?.passed ?? 0} of ${r?.total ?? 0} tests passed`}
      description={failed ? (verdict as { error: string }).error : r && (
        <div className="grid gap-3">
          <ol className="grid max-h-[50vh] gap-1 overflow-y-auto">
            {r.results.map((t, i) => (
              <motion.li key={t.name + i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
                transition={{ ...spring, delay: 0.08 * i }}
                className={cn("flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded-lg px-2.5 py-1.5 text-[13px]", t.passed ? "bg-success-soft" : "bg-danger-soft")}>
                {t.passed ? <CheckCircle2 className="size-4 text-success" /> : <CircleX className="size-4 text-danger" />}
                <span className="flex-1 text-text">{t.name}</span>
                {t.hidden && <span className="flex items-center gap-1 text-[11px] text-muted"><EyeOff className="size-3" />hidden</span>}
                {!t.passed && t.error_type && <span className="font-mono text-[11px] text-danger">{t.error_type}</span>}
                {!t.passed && !t.hidden && !t.error_type && t.expected !== undefined && (
                  <span className="basis-full font-mono text-[11px] text-muted">
                    expected <span className="text-text">{clip(t.expected)}</span>, got <span className="text-danger">{clip(t.stdout ?? "")}</span>
                  </span>
                )}
              </motion.li>
            ))}
          </ol>
          {r.standing && (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1, transition: { delay: 0.1 * r.results.length + 0.1 } }}
              className="text-sm text-muted">
              You are <strong className="text-text">#{r.standing.rank}</strong> of {r.standing.of} with{" "}
              <strong className="text-text"><Ticker value={r.standing.points} /></strong> points.
              {!solved && " Fix the failing tests and submit again; only your best submission counts."}
            </motion.p>
          )}
        </div>
      )}
      actions={
        <>
          <Button onClick={onLeave}>Back to board</Button>
          <Button variant="primary" onClick={onClose} data-autofocus>{solved ? "Keep coding" : "Fix and retry"}</Button>
        </>
      }
    />
  );
}

const clip = (s: string) => {
  const one = s.trim().replace(/\n/g, " ⏎ ");
  return one.length > 60 ? one.slice(0, 60) + "…" : one || "(nothing)";
};
