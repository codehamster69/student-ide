import { motion } from "motion/react";
import { ArrowRight } from "lucide-react";
import { Button, Card, ease, item, stagger } from "../ui";
import type { SessionSummary } from "./Workspace";

/** Check mark that draws itself. */
function DrawnCheck() {
  return (
    <motion.svg viewBox="0 0 52 52" className="size-16" initial="initial" animate="animate">
      <motion.circle
        cx="26" cy="26" r="24" fill="none" stroke="var(--success)" strokeWidth="2.5"
        variants={{ initial: { pathLength: 0, opacity: 0 }, animate: { pathLength: 1, opacity: 1, transition: { duration: 0.6, ease: ease.out } } }}
      />
      <motion.path
        d="M15 27l7 7 15-16" fill="none" stroke="var(--success)" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"
        variants={{ initial: { pathLength: 0 }, animate: { pathLength: 1, transition: { delay: 0.45, duration: 0.4, ease: ease.out } } }}
      />
    </motion.svg>
  );
}

export function Saved({ summary, onAnother }: { summary: SessionSummary; onAnother: () => void }) {
  const mins = Math.max(1, Math.round(summary.minutes));
  return (
    <Card variants={stagger(0.08, 0.2)} initial="initial" animate="animate" className="w-full max-w-md p-10 text-center">
      <div className="mb-5 flex justify-center"><DrawnCheck /></div>
      <motion.h1 variants={item} className="text-2xl font-semibold tracking-tight text-text">Session saved</motion.h1>
      <motion.p variants={item} className="mt-2 text-sm leading-relaxed text-muted">
        Thank you. You can close this tab or start another task.
      </motion.p>
      <motion.div variants={item} className="mx-auto mt-6 grid max-w-xs grid-cols-2 divide-x divide-border rounded-xl border border-border bg-surface-2/60 py-3">
        <div><div className="text-lg font-semibold text-text">{mins}</div><div className="text-xs text-muted">{mins === 1 ? "minute" : "minutes"}</div></div>
        <div><div className="text-lg font-semibold text-text">{summary.runs}</div><div className="text-xs text-muted">{summary.runs === 1 ? "run" : "runs"}</div></div>
      </motion.div>
      <motion.div variants={item} className="mt-7">
        <Button variant="primary" size="lg" onClick={onAnother} className="group">
          Another task
          <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />
        </Button>
      </motion.div>
    </Card>
  );
}
