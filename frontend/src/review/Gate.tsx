import { useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, HeartHandshake, KeyRound, ShieldCheck, UserRound } from "lucide-react";
import { Button, Card, Field, Input, Spinner, item, stagger } from "../ui";
import { AuthError, get, token } from "./api";

const PRINCIPLES = [
  { icon: UserRound, text: "Each student is compared only with their own first four weeks." },
  { icon: HeartHandshake, text: "A highlighted moment is a reason to talk, never a verdict." },
  { icon: ShieldCheck, text: "No webcam, microphone or screen recording, ever." },
];

/** Asks for the research/admin token before any student data is shown. */
export function Gate({ onDone }: { onDone: () => void }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await get("/api/review/config", value.trim());
      token.set(value.trim());
      onDone();
    } catch (err) {
      setError(err instanceof AuthError ? "That token was not accepted." : (err as Error).message);
      setBusy(false);
    }
  };

  return (
    <motion.div variants={stagger(0.08)} initial="initial" animate="animate"
      className="mx-auto grid max-w-5xl items-center gap-10 px-6 pb-16 pt-[9vh] lg:grid-cols-[1.1fr_1fr]">
      <div>
        <motion.p variants={item} className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-accent">For teachers and interviewers</motion.p>
        <motion.h1 variants={item} className="mb-4 text-4xl font-semibold leading-[1.1] tracking-tight text-text">
          See how a session<br />was written, moment by moment.
        </motion.h1>
        <motion.p variants={item} className="mb-8 max-w-md text-[15px] leading-relaxed text-muted">
          The timeline shows where a student's habits drifted from their own baseline, with the code replayed at any point,
          so you can ask a good question rather than jump to a conclusion.
        </motion.p>
        <motion.ul variants={stagger(0.07, 0.2)} className="grid max-w-md gap-3">
          {PRINCIPLES.map(({ icon: Icon, text }) => (
            <motion.li key={text} variants={item} className="flex items-center gap-3 text-sm text-muted">
              <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-border bg-surface text-accent shadow-sm"><Icon className="size-4" /></span>
              {text}
            </motion.li>
          ))}
        </motion.ul>
      </div>

      <Card variants={item} className="w-full p-8">
        <span className="mb-5 grid size-11 place-items-center rounded-xl bg-accent-soft text-accent"><KeyRound className="size-5" /></span>
        <h2 className="text-xl font-semibold tracking-tight text-text">Teacher access</h2>
        <p className="mt-1 text-sm text-muted">Enter the research token set on the server (<code className="font-mono text-xs">STUDENTIDE_ADMIN_TOKEN</code>).</p>
        <form onSubmit={submit} className="mt-6 grid gap-4">
          <Field label="Access token">
            <Input type="password" autoFocus value={value} onChange={(e) => setValue(e.target.value)}
              autoComplete="off" spellCheck={false} required className="font-mono" aria-invalid={!!error} />
          </Field>
          <AnimatePresence initial={false}>
            {error && (
              <motion.p key={error} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto", x: [0, -6, 6, -3, 0] }}
                exit={{ opacity: 0, height: 0 }} className="overflow-hidden rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">
                {error}
              </motion.p>
            )}
          </AnimatePresence>
          <Button type="submit" variant="primary" size="lg" disabled={busy || !value.trim()} className="group w-full">
            {busy ? <Spinner /> : null}
            Continue
            {!busy && <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />}
          </Button>
        </form>
        <p className="mt-6 border-t border-border pt-5 text-xs leading-relaxed text-faint">
          The token stays in this browser tab only. Close the tab or press Lock to forget it.
        </p>
      </Card>
    </motion.div>
  );
}
