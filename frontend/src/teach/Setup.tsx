import { useCallback, useEffect, useState, type ReactNode } from "react";
import { motion } from "motion/react";
import { ArrowRight, Check, ClipboardCheck, Eye, ListChecks, Lock, PlugZap, Radio, Users } from "lucide-react";
import { Card, cn, item, stagger } from "../ui";
import type { Me } from "../auth";
import { AuthError, get } from "../review/api";
import { href } from "../routes";
import type { LabRow } from "./api";
import { AllRegisters, ConnectRollCall } from "./Attendance";
import type { Connection, LabAttendanceSummary } from "./attendanceApi";

/**
 * #/teach/setup: Getting started for a new faculty member. Each step is ticked
 * from what already exists, so it doubles as a checklist to come back to.
 */
export function Setup({ me, onAuthLost }: { me: Me | null; onAuthLost: () => void }) {
  const [labs, setLabs] = useState<LabRow[] | null>(null);
  const [att, setAtt] = useState<LabAttendanceSummary>({});
  const [conn, setConn] = useState<Connection | null>(null);
  const fail = useCallback((e: unknown) => { if (e instanceof AuthError) onAuthLost(); }, [onAuthLost]);
  useEffect(() => {
    get<LabRow[]>("/api/teach/labs").then(setLabs, fail);
    get<LabAttendanceSummary>("/api/teach/attendance/labs").then(setAtt, fail);
  }, [fail]);

  const first = labs?.[0];
  const withClasses = labs?.find((l) => att[l.id]?.classes.length);
  const steps: { title: string; text: ReactNode; done: boolean; icon: typeof Users; link?: [string, string]; body?: ReactNode }[] = [
    {
      title: "Set up Roll Call", icon: PlugZap, done: !!conn?.connected,
      text: "Optional, but it's what lets a lab mark attendance. One press makes your own register; Open Roll Call then signs you in there, on any device.",
      body: <ConnectRollCall onAuthLost={onAuthLost} onChange={setConn} />,
    },
    {
      title: "Create a lab", icon: ListChecks, done: !!labs?.length,
      text: "A lab is one sitting: a few questions for one class. Give it a subject so it's filed with the right course.",
      link: first ? [href.lab(first.id), `Open ${first.title}`] : [href.labs, "New lab"],
    },
    {
      title: "Add questions", icon: ListChecks, done: !!labs?.some((l) => l.n_questions > 0),
      text: "Write your own or pick from the bundled sets (C fundamentals, Codeforces, MBPP). Tests are optional in labs.",
      link: first ? [href.lab(first.id), "Add questions"] : undefined,
    },
    {
      title: "Attach class groups", icon: ClipboardCheck, done: !!withClasses,
      text: "In the lab, under Class groups and attendance: tick your Roll Call groups or create one. Their students join the lab's roster.",
      link: first ? [href.lab(first.id), "Attach"] : undefined,
    },
    {
      title: "Try it as a student", icon: Eye, done: false,
      text: "View as student opens your labs exactly as students see them. Nothing you do there is study data or attendance.",
      link: [href.student, "View as student"],
    },
    {
      title: "Run the class, then close the lab", icon: Radio, done: Object.values(att).some((a) => a.days_sent > 0),
      text: "Open the lab when class starts and watch it live. Closing it sends attendance to Roll Call; you can preview and adjust first.",
      link: withClasses ? [href.labAttendance(withClasses.id), "Preview attendance"] : [href.live, "Live view"],
    },
  ];

  return (
    <motion.div variants={stagger(0.05)} initial="initial" animate="animate" className="mx-auto max-w-[1100px] px-5 pb-20 pt-8">
      <motion.div variants={item} className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-text">Getting started{me?.name ? `, ${me.name.split(" ")[0]}` : ""}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">From nothing to your first lab with attendance in about ten minutes. Steps tick themselves as you go.</p>
      </motion.div>
      <div className="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
        <motion.ol variants={stagger(0.04, 0.05)} className="grid gap-3">
          {steps.map((s, i) => (
            <motion.li key={s.title} variants={item}>
              <Card className="flex gap-4 p-5">
                <span className={cn("grid size-9 shrink-0 place-items-center rounded-xl text-sm font-semibold",
                  s.done ? "bg-success-soft text-success" : "bg-accent-soft text-accent")}>
                  {s.done ? <Check className="size-4" /> : i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className={cn("text-[15px] font-semibold", s.done ? "text-muted" : "text-text")}>{s.title}</h2>
                  <p className="mt-0.5 text-[13px] text-muted">{s.text}</p>
                  {s.body && <div className="mt-3">{s.body}</div>}
                  {s.link && (
                    <a href={s.link[0]} className="mt-2 inline-flex items-center gap-1 text-[13px] font-medium text-accent hover:underline">
                      {s.link[1]} <ArrowRight className="size-3.5" />
                    </a>
                  )}
                </div>
              </Card>
            </motion.li>
          ))}
        </motion.ol>
        <motion.aside variants={item} className="grid gap-4 lg:sticky lg:top-20">
          <Card className="p-5 text-[13px]">
            <h2 className="text-sm font-semibold text-text">Who is marked present</h2>
            <p className="mt-1.5 text-muted">
              For each lab day, a student counts as present with at least <strong className="text-text">10 active minutes</strong> (minutes in which they typed,
              ran or checked code) and <strong className="text-text">40 typed characters</strong>. Pastes don't count as typing. Each lab can change this, and you
              can override anyone before sending.
            </p>
            <p className="mt-2 text-muted">The learning lab and View as student never count. Attendance never looks at the review timeline's highlighted moments.</p>
          </Card>
          <Card className="p-5 text-[13px]">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold text-text"><Lock className="size-3.5" /> Students and their ids</h2>
            <p className="mt-1.5 text-muted">
              Students sign in with their college Google account; their id is the part before the @ (for example <span className="font-mono">UG23CS001</span>).
              Roll Call rosters must use the same prefix and digits so each student lands in their own group.
            </p>
          </Card>
          <Card className="p-5 text-[13px]">
            <h2 className="text-sm font-semibold text-text">Where things are</h2>
            <ul className="mt-1.5 grid gap-1 text-muted">
              <li><a className="text-accent hover:underline" href={href.labs}>Labs</a>: make and run labs and competitions</li>
              <li><a className="text-accent hover:underline" href={href.subjects}>Subjects</a>: labs by course, with their class groups</li>
              <li><a className="text-accent hover:underline" href={href.live}>Live</a>: watch an open lab</li>
              <li><a className="text-accent hover:underline" href={href.review}>Review</a>: timelines after class</li>
            </ul>
          </Card>
        </motion.aside>
      </div>
      <motion.div variants={item} className="mt-6"><AllRegisters onAuthLost={onAuthLost} /></motion.div>
    </motion.div>
  );
}
