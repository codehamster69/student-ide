import type { ReactNode } from "react";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { GraduationCap, LayoutGrid, LogOut } from "lucide-react";
import { Button, Logo, Stepper, cn, page, spring } from "../ui";
import { MyAttendanceButton } from "./MyAttendance";

const STEPS = ["Sign in", "Consent", "Choose task"];

export type StudentTab = "home" | "learn";
const TABS: { id: StudentTab; label: string; icon: typeof LayoutGrid }[] = [
  { id: "home", label: "My labs", icon: LayoutGrid },
  { id: "learn", label: "Learning lab", icon: GraduationCap },
];

/**
 * Frame for every student screen outside the editor. Before a student is in
 * (sign-in, consent) it shows the steps; after that it becomes the student's
 * app bar: their labs, the learning lab, attendance and who is signed in.
 */
export function Shell({ step, studentId, onSignOut, tab, onTab, children }: {
  step: number;
  studentId?: string;
  onSignOut?: () => void;
  /** Signed in: which top-bar tab is current, and how to switch. */
  tab?: StudentTab;
  onTab?: (t: StudentTab) => void;
  children: ReactNode;
}) {
  const inside = step >= 2 && !!onTab;
  return (
    <div className="relative flex min-h-full flex-col">
      {step === 0 && <div className="bg-dot-grid pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_20%,transparent_70%)]" />}
      <header className={cn("relative z-20 flex h-14 shrink-0 items-center gap-4 px-4 sm:px-6", inside && "sticky top-0 border-b border-border bg-bg/85 backdrop-blur-md")}>
        <Logo subtitle={inside ? undefined : "Lab code editor"} />
        {inside ? (
          <LayoutGroup id="student-nav">
            <nav aria-label="Main" className="flex items-center gap-0.5 sm:ml-4">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button key={id} type="button" onClick={() => onTab!(id)} aria-current={tab === id ? "page" : undefined}
                  className={cn("relative flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[13.5px] font-medium transition-colors",
                    tab === id ? "text-text" : "text-muted hover:text-text")}>
                  {tab === id && <motion.span layoutId="student-tab" transition={spring} className="absolute inset-0 rounded-md border border-border-strong" />}
                  <Icon className={cn("relative size-4", tab === id ? "text-cta" : "text-faint")} />
                  <span className="relative hidden sm:inline">{label}</span>
                </button>
              ))}
            </nav>
          </LayoutGroup>
        ) : (
          <div className="flex flex-1 justify-center"><Stepper steps={STEPS} current={step} /></div>
        )}
        <div className="ml-auto flex min-w-0 items-center justify-end gap-1">
          {studentId && step >= 2 && studentId !== "STAFF_PREVIEW" && <MyAttendanceButton studentId={studentId} />}
          {studentId && (
            <div className="flex items-center gap-1 rounded-full border border-border py-0.5 pl-3 pr-0.5 shadow-sm">
              <span className="truncate font-mono text-xs text-muted">{studentId}</span>
              {onSignOut && (
                <Button variant="ghost" size="icon" className="size-7 rounded-full" onClick={onSignOut} aria-label="Sign out" title="Sign out">
                  <LogOut className="size-3.5" />
                </Button>
              )}
            </div>
          )}
        </div>
      </header>
      <main className={cn("relative z-10 flex flex-1 justify-center px-4 pb-16 sm:px-6", inside ? "items-start pt-8" : "items-start pt-[6vh]")}>
        <AnimatePresence mode="wait">
          <motion.div key={inside ? `tab-${tab}-${step}` : step} variants={page} initial="initial" animate="animate" exit="exit" className="flex w-full justify-center">
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
      <footer className="relative z-10 pb-5 text-center text-xs text-faint">
        IIIT Surat, a research study on how people write code
      </footer>
    </div>
  );
}
