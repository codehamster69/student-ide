import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { LogOut } from "lucide-react";
import { Button, Logo, Stepper, page } from "../ui";

const STEPS = ["Sign in", "Consent", "Choose task"];

/** Frame for the screens before a session: brand, progress, who is signed in. */
export function Shell({ step, studentId, onSignOut, children }: {
  step: number;
  studentId?: string;
  onSignOut?: () => void;
  children: ReactNode;
}) {
  return (
    <div className="relative flex min-h-full flex-col overflow-hidden">
      <div className="bg-dot-grid pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
      <div className="pointer-events-none absolute -top-40 left-1/2 h-80 w-[56rem] -translate-x-1/2 rounded-full bg-accent/10 blur-3xl" />
      <header className="relative z-10 flex h-16 items-center justify-between gap-4 px-6">
        <Logo subtitle="Lab code editor" />
        <Stepper steps={STEPS} current={step} />
        <div className="flex min-w-40 justify-end">
          {studentId && (
            <div className="flex items-center gap-1 rounded-full border border-border bg-surface py-1 pl-3 pr-1 shadow-sm">
              <span className="font-mono text-xs text-muted">{studentId}</span>
              {onSignOut && (
                <Button variant="ghost" size="icon" className="size-7 rounded-full" onClick={onSignOut} aria-label="Switch student">
                  <LogOut className="size-3.5" />
                </Button>
              )}
            </div>
          )}
        </div>
      </header>
      <main className="relative z-10 flex flex-1 items-start justify-center px-6 pb-16 pt-[6vh]">
        <AnimatePresence mode="wait">
          <motion.div key={step} variants={page} initial="initial" animate="animate" exit="exit" className="flex w-full justify-center">
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
      <footer className="relative z-10 pb-5 text-center text-xs text-faint">
        IIIT Surat · research study on how people write code
      </footer>
    </div>
  );
}
