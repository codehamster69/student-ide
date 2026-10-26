import { useState } from "react";
import { motion } from "motion/react";
import { ArrowRight, Ban, ClipboardPaste, Eye, FileDiff, Keyboard, Play, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { Button, Card, Checkbox, Spinner, cn, item, stagger } from "../ui";

const RECORDED = [
  { icon: Keyboard, text: "When each key is pressed and released (timing, and which key)" },
  { icon: FileDiff, text: "Every edit to your code" },
  { icon: ClipboardPaste, text: "Anything you paste, copy or cut in the editor" },
  { icon: Play, text: "Each time you run your program, with its output" },
  { icon: Eye, text: "When you switch away from the editor or this tab" },
];

export function Consent({ studentId, onDone }: { studentId: string; onDone: () => void }) {
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);

  const start = async () => {
    setBusy(true);
    try {
      await api("/api/consent", { student_id: studentId });
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

        <motion.div variants={item} className="mt-4 flex gap-3 rounded-xl bg-success-soft px-4 py-3 text-sm text-text">
          <Ban className="mt-0.5 size-4 shrink-0 text-success" />
          <p>It does <strong className="font-semibold">not</strong> use your webcam or microphone and does not record your screen or other apps.</p>
        </motion.div>

        <motion.p variants={item} className="mt-4 text-sm leading-relaxed text-muted">
          Your typing patterns are compared only with your own earlier sessions. If something looks unusual, the only
          consequence is a conversation with your instructor, never an automatic penalty. Raw keystroke data is deleted
          once summary statistics have been computed.
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
