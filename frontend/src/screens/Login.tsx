import { useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ArrowRight, CameraOff, Keyboard, MessagesSquare } from "lucide-react";
import { api } from "../api";
import type { AuthConfig, Me } from "../auth";
import { Button, Card, Field, Input, Spinner, TypingDemo, item, stagger } from "../ui";
import { GoogleSignIn } from "./GoogleSignIn";

const FACTS = [
  { icon: Keyboard, text: "Records typing rhythm, edits, pastes and runs" },
  { icon: CameraOff, text: "Never your webcam, microphone or screen" },
  { icon: MessagesSquare, text: "A flag only ever leads to a conversation" },
];

/** `cfg.mode` "google": the college Google account; "dev": a typed roll number (local work, staged sessions). */
export function Login({ cfg, onDone, onTeacher }: {
  cfg: AuthConfig;
  onDone: (studentId: string, consented: boolean, sandboxConsented?: boolean) => void;
  onTeacher?: (me: Me) => void;
}) {
  const [id, setId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api<{ student_id: string; consented: boolean; sandbox_consented?: boolean }>("/api/login", { student_id: id });
      onDone(r.student_id, r.consented, r.sandbox_consented);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return (
    <motion.div variants={stagger(0.08)} initial="initial" animate="animate" className="grid w-full max-w-5xl items-center gap-10 lg:grid-cols-[1.1fr_1fr]">
      <div className="hidden lg:block">
        <motion.p variants={item} className="mb-3 text-xs font-semibold uppercase tracking-[0.14em] text-accent">Programming lab</motion.p>
        <motion.h1 variants={item} className="mb-4 text-4xl font-semibold leading-[1.1] tracking-tight text-text">
          Write code the way<br />you always do.
        </motion.h1>
        <motion.p variants={item} className="mb-8 max-w-md text-[15px] leading-relaxed text-muted">
          This editor notices <em>how</em> code is written, not just what it says, and compares it only with your own past sessions.
        </motion.p>
        <motion.div variants={item}><TypingDemo /></motion.div>
      </div>

      <Card variants={item} className="mx-auto w-full max-w-md p-8">
        <h2 className="text-xl font-semibold tracking-tight text-text">Sign in</h2>
        {cfg.mode === "google" ? (
          <>
            <p className="mt-1 text-sm text-muted">Use your college Google account (<span className="font-mono text-xs">@{cfg.domain}</span>).</p>
            <div className="mt-6">
              <GoogleSignIn cfg={cfg} onDone={(me) => (me.role !== "student" && onTeacher ? onTeacher(me) : onDone(me.student_id, me.consented, me.sandbox_consented))} />
            </div>
          </>
        ) : (
          <>
        <p className="mt-1 text-sm text-muted">Use your roll number. No password needed in the lab.</p>
        <form onSubmit={submit} className="mt-6 grid gap-4">
          <Field label="Roll number">
            <Input
              autoFocus
              value={id}
              onChange={(e) => setId(e.target.value)}
              placeholder="e.g. PG25CS07"
              autoComplete="off"
              spellCheck={false}
              required
              maxLength={32}
              className="font-mono"
              aria-invalid={!!error}
            />
          </Field>
          <AnimatePresence initial={false}>
            {error && (
              <motion.p
                key={error}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto", x: [0, -6, 6, -3, 0] }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger"
                role="alert"
              >
                {error}
              </motion.p>
            )}
          </AnimatePresence>
          <Button type="submit" variant="primary" size="lg" disabled={busy || !id.trim()} className="group mt-1 w-full">
            {busy ? <Spinner /> : null}
            Continue
            {!busy && <ArrowRight className="size-4 transition-transform duration-200 group-hover:translate-x-0.5" />}
          </Button>
        </form>
          </>
        )}
        <ul className="mt-7 grid gap-2.5 border-t border-border pt-6">
          {FACTS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-3 text-[13px] text-muted">
              <span className="grid size-7 place-items-center rounded-lg bg-surface-2 text-text"><Icon className="size-3.5" /></span>
              {text}
            </li>
          ))}
        </ul>
      </Card>
    </motion.div>
  );
}
