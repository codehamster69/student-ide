import { useEffect, useState } from "react";
import { AnimatePresence, LayoutGroup, MotionConfig, motion } from "motion/react";
import { Activity, ListChecks, LogOut, MessagesSquare, UsersRound } from "lucide-react";
import { authConfig, currentUser, signOut as endGoogleSession, type AuthConfig, type Me } from "../auth";
import { Button, Logo, cn, page, spring } from "../ui";
import { Labs } from "../teach/Labs";
import { LabEditor } from "../teach/LabEditor";
import { Users } from "../teach/Users";
import { LiveBoard } from "../compete/LiveBoard";
import { token } from "./api";
import { Gate } from "./Gate";
import { Overview } from "./Overview";
import { SessionView } from "./SessionView";

type Route =
  | { name: "overview" } | { name: "session"; id: string }
  | { name: "labs" } | { name: "lab"; id: string } | { name: "board"; id: string } | { name: "people" };

// Routes: #/review (overview), #/review/s/<session id>, #/teach (labs) and
// #/teach/l/<lab id>, #/teach/c/<lab id> (competition live board), #/teach/people (admins).
// One teacher area, one sign-in.
function route(): Route {
  if (location.hash.startsWith("#/teach/people")) return { name: "people" };
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
const ADMIN_TAB = { href: "#/teach/people", label: "People", icon: UsersRound, match: (r: Route) => r.name === "people" };

export function ReviewApp() {
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [student, setStudent] = useState<Me | null>(null); // signed in, but with a student account
  const [authed, setAuthed] = useState(false);
  const [r, setR] = useState(route);

  // Google mode: a teacher or admin session cookie; dev mode: the token in this tab.
  useEffect(() => {
    authConfig().then(async (c) => {
      const u = c.mode === "google" ? await currentUser() : null;
      setCfg(c);
      setMe(u && u.role !== "student" ? u : null);
      setStudent(u && u.role === "student" ? u : null);
      setAuthed(c.mode === "google" ? !!u && u.role !== "student" : !!token.get());
    });
  }, []);

  useEffect(() => {
    const on = () => setR(route());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const teaching = r.name === "labs" || r.name === "lab" || r.name === "board" || r.name === "people";
  const tabs = me?.role === "admin" ? [...TABS, ADMIN_TAB] : TABS;
  useEffect(() => { document.title = `${teaching ? "Labs" : "Review"} · Student IDE`; }, [teaching]);

  const signOut = () => {
    token.clear();
    if (cfg?.mode === "google") void endGoogleSession();
    setMe(null);
    setAuthed(false);
  };
  const key = !cfg ? "loading" : !authed ? "gate" : "id" in r ? `${r.name}-${r.id}` : r.name;

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
                    {tabs.map(({ href, label, icon: Icon, match }) => (
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
                  {me && <span className="hidden font-mono text-xs text-faint lg:inline">{me.email}</span>}
                  <LogOut className="size-3.5" /> {cfg?.mode === "google" ? "Sign out" : "Lock"}
                </Button>
              )}
            </div>
          </div>
        </header>
        <main className="relative z-10 flex-1">
          <AnimatePresence mode="wait">
            <motion.div key={key} variants={page} initial="initial" animate="animate" exit="exit">
              {!cfg ? null : !authed ? (
                <Gate cfg={cfg} signedInStudent={student} onDone={(u) => { setMe(u); setAuthed(true); }} />
              ) : r.name === "people" && me?.role === "admin" ? (
                <Users me={me.email} onAuthLost={signOut} />
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
