import { useEffect, useState } from "react";
import { AnimatePresence, LayoutGroup, MotionConfig, motion } from "motion/react";
import { Activity, BookOpen, ListChecks, Eye, LogOut, MessagesSquare, Radio, Sparkles, UsersRound } from "lucide-react";
import { authConfig, currentUser, signOut as endGoogleSession, type AuthConfig, type Me } from "../auth";
import { Button, Logo, cn, page, spring } from "../ui";
import { Labs } from "../teach/Labs";
import { LabEditor } from "../teach/LabEditor";
import { Users } from "../teach/Users";
import { Subject, Subjects } from "../teach/Subjects";
import { Setup } from "../teach/Setup";
import { LiveBoard } from "../compete/LiveBoard";
import { Similar } from "../compete/Similar";
import { LiveClass, LiveLabs } from "../live/LiveClass";
import { LiveEditor } from "../live/LiveEditor";
import { token } from "./api";
import { Gate } from "./Gate";
import { LabSessions } from "./LabSessions";
import { Overview } from "./Overview";
import { SessionView } from "./SessionView";
import { areaOf, canonicalize, href, parseRoute, routeHash, type Route } from "../routes";

// One teacher area, one sign-in. Every page and its URL is listed in ../routes.ts.
const TABS = [
  { href: href.labs, label: "Labs", icon: ListChecks, match: (r: Route) => areaOf(r) === "teach" && !["subjects", "subject", "setup", "people"].includes(r.name) },
  { href: href.subjects, label: "Subjects", icon: BookOpen, match: (r: Route) => r.name === "subjects" || r.name === "subject" },
  { href: href.live, label: "Live", icon: Radio, match: (r: Route) => areaOf(r) === "live" },
  { href: href.review, label: "Review", icon: Activity, match: (r: Route) => areaOf(r) === "review" },
];
const ADMIN_TAB = { href: href.people, label: "People", icon: UsersRound, match: (r: Route) => r.name === "people" };

export function ReviewApp() {
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [student, setStudent] = useState<Me | null>(null); // signed in, but with a student account
  const [authed, setAuthed] = useState(false);
  const [r, setR] = useState(() => { canonicalize(); return parseRoute(); });

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
    const on = () => { canonicalize(); setR(parseRoute()); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  const teaching = areaOf(r) === "teach";
  const watching = areaOf(r) === "live";
  const tabs = me?.role === "admin" ? [...TABS, ADMIN_TAB] : TABS;
  useEffect(() => { document.title = `${watching ? "Live" : teaching ? "Labs" : "Review"} · Student IDE`; }, [teaching, watching]);

  const signOut = () => {
    token.clear();
    if (cfg?.mode === "google") void endGoogleSession();
    setMe(null);
    setAuthed(false);
  };
  const key = !cfg ? "loading" : !authed ? "gate" : r.name === "lab" ? `lab-${r.id}` : routeHash(r);

  return (
    <MotionConfig reducedMotion="user">
      <div className="relative flex min-h-full flex-col">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-dot-grid [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <header className="sticky top-0 z-30 border-b border-border/70 bg-bg/80 backdrop-blur-md">
          <div className="mx-auto flex h-14 max-w-[1440px] items-center justify-between gap-4 px-5">
            <div className="flex items-center gap-5">
              <a href={teaching ? href.labs : href.review} className="rounded-lg"><Logo subtitle={watching ? "Live class view" : teaching ? "Labs and questions" : "Review timeline"} /></a>
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
            <div className="flex min-w-24 items-center justify-end gap-1">
              {authed && (
                <a href={href.setup} title="Getting started: connect Roll Call, make a lab, attach class groups"
                  className="flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-medium text-muted transition-colors hover:bg-surface-2 hover:text-text">
                  <Sparkles className="size-3.5" /><span className="hidden lg:inline">Getting started</span>
                </a>
              )}
              {authed && (
                <a href={href.student} title="Open the student side under your own account; nothing you do there is study data"
                  className="flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-[13px] font-medium text-muted transition-colors hover:bg-surface-2 hover:text-text">
                  <Eye className="size-3.5" />View as student
                </a>
              )}
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
              ) : r.name === "live" ? (
                <LiveLabs onAuthLost={signOut} />
              ) : r.name === "live-lab" ? (
                <LiveClass id={r.id} onAuthLost={signOut} />
              ) : r.name === "live-session" ? (
                <LiveEditor id={r.id} onAuthLost={signOut} />
              ) : r.name === "session" ? (
                <SessionView id={r.id} onAuthLost={signOut} />
              ) : r.name === "similar" ? (
                <Similar id={r.id} onAuthLost={signOut} />
              ) : r.name === "board" ? (
                <LiveBoard id={r.id} onAuthLost={signOut} />
              ) : r.name === "lab" ? (
                <LabEditor id={r.id} view={r.view} onAuthLost={signOut} />
              ) : r.name === "subjects" ? (
                <Subjects onAuthLost={signOut} />
              ) : r.name === "subject" ? (
                <Subject slug={r.slug} onAuthLost={signOut} />
              ) : r.name === "setup" ? (
                <Setup me={me} onAuthLost={signOut} />
              ) : r.name === "labs" ? (
                <Labs onAuthLost={signOut} />
              ) : r.name === "review-lab" ? (
                <Overview labId={r.id} day={r.day} onAuthLost={signOut} />
              ) : r.name === "review-all" ? (
                <Overview onAuthLost={signOut} />
              ) : (
                <LabSessions onAuthLost={signOut} />
              )}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </MotionConfig>
  );
}
