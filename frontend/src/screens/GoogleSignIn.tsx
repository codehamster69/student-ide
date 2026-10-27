import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { renderGoogleButton, signInWithGoogle, type AuthConfig, type Me } from "../auth";
import { Spinner } from "../ui";

/** Google's sign-in button, limited to the college domain, with errors shown inline. */
export function GoogleSignIn({ cfg, onDone }: { cfg: AuthConfig; onDone: (me: Me) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const done = useRef(onDone);
  done.current = onDone;

  useEffect(() => {
    if (!el.current) return;
    renderGoogleButton(el.current, cfg, async (credential) => {
      setBusy(true);
      setError("");
      try {
        done.current(await signInWithGoogle(credential));
      } catch (err) {
        setError((err as Error).message);
        setBusy(false);
      }
    }).catch((err) => setError((err as Error).message));
  }, [cfg]);

  return (
    <div className="grid gap-4">
      <div className="relative flex min-h-11 justify-center">
        <div ref={el} className={busy ? "pointer-events-none opacity-40" : ""} />
        {busy && <span className="absolute inset-0 grid place-items-center"><Spinner /></span>}
      </div>
      <AnimatePresence initial={false}>
        {error && (
          <motion.p key={error} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto", x: [0, -6, 6, -3, 0] }}
            exit={{ opacity: 0, height: 0 }} className="overflow-hidden rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}
