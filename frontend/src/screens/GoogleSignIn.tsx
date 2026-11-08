import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ExternalLink } from "lucide-react";
import { currentUser, renderGoogleButton, signInWithGoogle, type AuthConfig, type Me } from "../auth";
import { desktop, desktopError } from "../desktop";
import { Button, Spinner } from "../ui";

/** Google's sign-in button, limited to the college domain, with errors shown inline.
 * In the desktop app Google refuses embedded sign-in, so it signs in through the system browser instead. */
export function GoogleSignIn({ cfg, onDone }: { cfg: AuthConfig; onDone: (me: Me) => void }) {
  return desktop ? <BrowserSignIn onDone={onDone} /> : <GoogleButton cfg={cfg} onDone={onDone} />;
}

function BrowserSignIn({ onDone }: { onDone: (me: Me) => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    setError("");
    try {
      await desktop!.auth.signIn();
      const me = await currentUser();
      if (!me) throw new Error("Signed in, but the server did not recognise the session. Try again.");
      onDone(me);
    } catch (err) {
      setError(desktopError(err).message);
      setBusy(false);
    }
  };
  return (
    <div className="grid gap-3">
      <Button variant="primary" size="lg" onClick={go} disabled={busy} className="w-full">
        {busy ? <Spinner /> : <ExternalLink className="size-4" />}
        {busy ? "Finish signing in in your browser…" : "Sign in with your browser"}
      </Button>
      <p className="text-center text-xs text-muted">Your browser opens Google sign-in; then come back here.</p>
      <ErrorNote error={error} />
    </div>
  );
}

function ErrorNote({ error }: { error: string }) {
  return (
    <AnimatePresence initial={false}>
      {error && (
        <motion.p key={error} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto", x: [0, -6, 6, -3, 0] }}
          exit={{ opacity: 0, height: 0 }} className="overflow-hidden rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">
          {error}
        </motion.p>
      )}
    </AnimatePresence>
  );
}

function GoogleButton({ cfg, onDone }: { cfg: AuthConfig; onDone: (me: Me) => void }) {
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
      <ErrorNote error={error} />
    </div>
  );
}
