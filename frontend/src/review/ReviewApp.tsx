import { useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { LogOut, MessagesSquare } from "lucide-react";
import { Button, Logo, page } from "../ui";
import { token } from "./api";
import { Gate } from "./Gate";
import { Overview } from "./Overview";
import { SessionView } from "./SessionView";

// Routes: #/review (overview) and #/review/s/<session id>.
function route(): { name: "overview" } | { name: "session"; id: string } {
  const m = location.hash.match(/^#\/review\/s\/([0-9a-f]+)/);
  return m ? { name: "session", id: m[1] } : { name: "overview" };
}

export function ReviewApp() {
  const [authed, setAuthed] = useState(() => !!token.get());
  const [r, setR] = useState(route);

  useEffect(() => {
    document.title = "Review · Student IDE";
    const on = () => setR(route());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const signOut = () => { token.clear(); setAuthed(false); };
  const key = !authed ? "gate" : r.name === "session" ? `s-${r.id}` : "overview";

  return (
    <MotionConfig reducedMotion="user">
      <div className="relative flex min-h-full flex-col">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-dot-grid [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <header className="sticky top-0 z-30 border-b border-border/70 bg-bg/80 backdrop-blur-md">
          <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-4 px-5">
            <a href="#/review" className="rounded-lg"><Logo subtitle="Review timeline" /></a>
            <div className="hidden items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted shadow-sm md:flex">
              <MessagesSquare className="size-3.5 text-accent" />
              A highlighted moment starts a conversation, never a penalty.
            </div>
            <div className="flex min-w-24 justify-end">
              {authed && (
                <Button variant="ghost" size="sm" onClick={signOut}>
                  <LogOut className="size-3.5" /> Lock
                </Button>
              )}
            </div>
          </div>
        </header>
        <main className="relative z-10 flex-1">
          <AnimatePresence mode="wait">
            <motion.div key={key} variants={page} initial="initial" animate="animate" exit="exit">
              {!authed ? (
                <Gate onDone={() => setAuthed(true)} />
              ) : r.name === "session" ? (
                <SessionView id={r.id} onAuthLost={signOut} />
              ) : (
                <Overview onAuthLost={signOut} />
              )}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </MotionConfig>
  );
}
