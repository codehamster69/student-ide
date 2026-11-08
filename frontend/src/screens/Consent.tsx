import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowRight, Ban, Box, ClipboardPaste, Eye, FileDiff, FolderSync, Keyboard, MonitorPlay, Network, Play, ShieldCheck, SquareTerminal, WifiOff } from "lucide-react";
import { api } from "../api";
import { authConfig, type LiveMode } from "../auth";
import { Button, Card, Checkbox, Spinner, cn, item, stagger } from "../ui";

const RECORDED = [
  { icon: Keyboard, text: "When each key is pressed and released (timing, and which key)" },
  { icon: FileDiff, text: "Every edit to your code" },
  { icon: ClipboardPaste, text: "Anything you paste, copy or cut in the editor" },
  { icon: Play, text: "Each time you run your program, with its output" },
  { icon: Eye, text: "When you switch away from the editor or this tab" },
];

// Consent v3 (db.SANDBOX_CONSENT_VERSION): asked once, before a student's first Sandbox Lab.
const SANDBOX = [
  { icon: Keyboard, text: "When each key is pressed in the lab's terminal, including in vim or nano (timing and which key, as in the editor)" },
  { icon: SquareTerminal, text: "Each command you run in the terminal, its folder, whether it worked, and the last lines of its output" },
  { icon: ClipboardPaste, text: "Anything you paste into the terminal" },
  { icon: FileDiff, text: "When a file in your lab folder changes outside the editor (a save in vim, cat > main.c), and what changed" },
  { icon: Network, text: "Packages you install, the names of websites the lab connects to (never what is sent), and programs that start listening on a port" },
  { icon: FolderSync, text: "A copy of your lab folder, so your work follows you to another computer and can be graded" },
];

// What a teacher can see live while a lab is running (see backend/studentide/live.py).
const LIVE: Record<Exclude<LiveMode, "off">, string> = {
  class: "During a lab your teacher can follow the class live: who is working, on which question, and your runs and checks (not your code). A notice in the editor tells you while they do.",
  editor: "During a lab your teacher can follow the class live and open a read-only view of your editor. The editor always tells you when they do, with their name.",
};

export function Consent({ studentId, onDone, scope = "web" }: { studentId: string; onDone: () => void; scope?: "web" | "sandbox" }) {
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [live, setLive] = useState<LiveMode>("editor");
  useEffect(() => { void authConfig().then((c) => setLive(c.live ?? "editor")); }, []);

  const start = async () => {
    setBusy(true);
    try {
      await api("/api/consent", { student_id: studentId, scope });
      onDone();
    } catch {
      setBusy(false);
    }
  };

  return (
    <Card variants={stagger(0.05)} initial="initial" animate="animate" className="w-full max-w-2xl overflow-hidden">
      <div className="p-8 pb-6">
        <motion.div variants={item} className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-accent-soft text-accent"><ShieldCheck className="size-5" /></span>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Before you start</h1>
        </motion.div>
        <motion.p variants={item} className="mt-2 text-[15px] leading-relaxed text-muted">
          This editor is part of a research study on how people write code. While you work it records:
        </motion.p>

        <ul className="mt-4 grid gap-1.5">
          {RECORDED.map(({ icon: Icon, text }) => (
            <motion.li key={text} variants={item} className="flex items-center gap-3 rounded-xl border border-border bg-surface-2/60 px-3 py-1.5 text-sm text-text">
              <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-surface text-accent shadow-sm"><Icon className="size-3.5" /></span>
              {text}
            </motion.li>
          ))}
        </ul>

        {scope === "sandbox" && (
          <motion.div variants={item} className="mt-5">
            <h2 className="flex items-center gap-2 text-base font-semibold text-text"><Box className="size-4 text-accent" />Sandbox Labs</h2>
            <p className="mt-1 text-sm leading-relaxed text-muted">
              In a Sandbox Lab your code runs in a Linux container on your own computer. While a lab is open, the app also records:
            </p>
            <ul className="mt-3 grid gap-1.5">
              {SANDBOX.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-3 rounded-xl border border-border bg-surface-2/60 px-3 py-1.5 text-sm text-text">
                  <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-surface text-accent shadow-sm"><Icon className="size-3.5" /></span>
                  {text}
                </li>
              ))}
            </ul>
            <p className="mt-3 flex gap-3 rounded-xl border border-border bg-surface-2/60 px-4 py-3 text-sm text-text">
              <WifiOff className="mt-0.5 size-4 shrink-0 text-accent" />
              If the connection drops, your work stays saved on this computer and you can keep going for 5 minutes. After that,
              editing pauses until the connection is back. A gap is never treated as a problem.
            </p>
          </motion.div>
        )}

        {live !== "off" && (
          <motion.div variants={item} className="mt-4 flex gap-3 rounded-xl border border-border bg-surface-2/60 px-4 py-3 text-sm text-text">
            <MonitorPlay className="mt-0.5 size-4 shrink-0 text-accent" />
            <p>{LIVE[live]}{scope === "sandbox" && live === "editor" ? " In a Sandbox Lab that view shows your terminal commands too." : ""} Nothing from a live view is ever used to mark your work.</p>
          </motion.div>
        )}

        <motion.div variants={item} className="mt-4 flex gap-3 rounded-xl bg-success-soft px-4 py-3 text-sm text-text">
          <Ban className="mt-0.5 size-4 shrink-0 text-success" />
          <p>It does <strong className="font-semibold">not</strong> use your webcam or microphone and does not record your screen or other apps.
            {scope === "sandbox" && " In a Sandbox Lab it sees nothing outside the lab's folder and container: not your other files, and no keys typed outside the app's window."}</p>
        </motion.div>

        <motion.p variants={item} className="mt-4 text-sm leading-relaxed text-muted">
          Your typing patterns are compared only with your own earlier sessions. If something looks unusual, the only
          consequence is a conversation with your instructor, never an automatic penalty. Raw keystroke data is deleted
          once summary statistics have been computed: when your four-week baseline is built, and never kept longer than
          28 days.{scope === "sandbox" && " Terminal typing is compared only with your own earlier sessions, like editor typing, and it counts toward lab attendance like editor typing."}
        </motion.p>
      </div>

      <motion.div variants={item} className="flex flex-wrap items-center justify-between gap-4 border-t border-border bg-surface-2/60 px-8 py-4">
        <label className={cn("flex cursor-pointer items-center gap-3 text-sm font-medium transition-colors", agreed ? "text-text" : "text-muted")}>
          <Checkbox checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
          I have read this and agree to take part.
        </label>
        <Button variant="primary" size="lg" disabled={!agreed || busy} onClick={start} className="group">
          {busy && <Spinner />}
          Start
          {!busy && <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />}
        </Button>
      </motion.div>
    </Card>
  );
}
