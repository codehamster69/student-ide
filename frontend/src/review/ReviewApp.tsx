import { useEffect, useState } from "react";
import { AnimatePresence, LayoutGroup, MotionConfig, motion } from "motion/react";
import { Activity, ListChecks, LogOut, MessagesSquare } from "lucide-react";
import { Button, Logo, cn, page, spring } from "../ui";
import { Labs } from "../teach/Labs";
import { LabEditor } from "../teach/LabEditor";
import { LiveBoard } from "../compete/LiveBoard";
import { token } from "./api";
import { Gate } from "./Gate";
import { Overview } from "./Overview";
import { SessionView } from "./SessionView";

type Route =
  | { name: "overview" } | { name: "session"; id: string }
  | { name: "labs" } | { name: "lab"; id: string } | { name: "board"; id: string };

// Routes: #/review (overview), #/review/s/<session id>, #/teach (labs) and
// #/teach/l/<lab id>, #/teach/c/<lab id> (competition live board). One teacher area, one token.
function route(): Route {
  const s = location.hash.match(/^#\/review\/s\/([0-9a-f]+)/);
  if (s) return { name: "session", id: s[1] };
  const l = location.hash.match(/^#\/teach\/l\/([A-Za-z0-9_]+)/);
  if (l) return { name: "lab", id: l[1] };
  const c = location.hash.match(/^#\/teach\/c\/([A-Za-z0-9_]+)/);
  if (c) return { name: "board", id: c[1] };
  return location.hash.startsWith("#/teach") ? { name: "labs" } : { name: "overview" };
}

const TABS = [
  { href: "#/teach", label: "Labs", icon: ListChecks, match: (r: Route) => r.name === "labs" || r.name === "lab" || r.name === "board" },
  { href: "#/review", label: "Review", icon: Activity, match: (r: Route) => r.name === "overview" || r.name === "session" },
];

export function ReviewApp() {
  const [authed, setAuthed] = useState(() => !!token.get());
  const [r, setR] = useState(route);

  useEffect(() => {
    const on = () => setR(route());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const teaching = r.name === "labs" || r.name === "lab" || r.name === "board";
  useEffect(() => { document.title = `${teaching ? "Labs" : "Review"} · Student IDE`; }, [teaching]);

  const signOut = () => { token.clear(); setAuthed(false); };
  const key = !authed ? "gate" : "id" in r ? `${r.name}-${r.id}` : r.name;

  return (
    <MotionConfig reducedMotion="user">
      <div className="relative flex min-h-full flex-col">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-dot-grid [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <header className="sticky top-0 z-30 border-b border-border/70 bg-bg/80 backdrop-blur-md">
          <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-4 px-5">
            <div className="flex items-center gap-5">
              <a href={teaching ? "#/teach" : "#/review"} className="rounded-lg"><Logo subtitle={teaching ? "Labs and questions" : "Review timeline"} /></a>
              {authed && (
                <LayoutGroup id="teacher-nav">
                  <nav className="flex rounded-lg border border-border bg-surface p-0.5 shadow-sm">
                    {TABS.map(({ href, label, icon: Icon, match }) => (
                      <a key={href} href={href} aria-current={match(r) ? "page" : undefined}
                        className={cn("relative flex h-8 items-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-colors",
                          match(r) ? "text-text" : "text-muted hover:text-text")}>
                        {match(r) && <motion.span layoutId="nav-pill" transition={spring} className="absolute inset-0 rounded-md bg-surface-3" />}
                        <Icon className="relative size-3.5" /><span className="relative">{label}</span>
                      </a>
                    ))}
                  </nav>
                </LayoutGroup>
              )}
            </div>
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
              ) : r.name === "board" ? (
                <LiveBoard id={r.id} onAuthLost={signOut} />
              ) : r.name === "lab" ? (
                <LabEditor id={r.id} onAuthLost={signOut} />
              ) : r.name === "labs" ? (
                <Labs onAuthLost={signOut} />
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
