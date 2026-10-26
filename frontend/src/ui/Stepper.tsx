import { motion } from "motion/react";
import { Check } from "lucide-react";
import { cn } from "./cn";
import { spring } from "./motion";

/** Horizontal step indicator; the active pill slides between steps. */
export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="flex items-center gap-1 rounded-full border border-border bg-surface/80 p-1 shadow-sm backdrop-blur">
      {steps.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={label} className="relative">
            {active && (
              <motion.span layoutId="stepper-active" transition={spring} className="absolute inset-0 rounded-full bg-accent-soft" />
            )}
            <span className={cn(
              "relative flex h-7 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-colors duration-200",
              active ? "text-accent" : done ? "text-text" : "text-faint",
            )}>
              <span className={cn(
                "grid size-4 place-items-center rounded-full text-[10px] transition-colors duration-200",
                done ? "bg-success text-white" : active ? "bg-accent text-accent-fg" : "bg-surface-3 text-muted",
              )}>
                {done ? <Check className="size-2.5" strokeWidth={3.5} /> : i + 1}
              </span>
              <span className="hidden sm:inline">{label}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
