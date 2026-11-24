import { useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { Activity, BookOpen, Boxes, ListChecks, Eye, LogOut, MessagesSquare, Radio, Sparkles, Trophy, UsersRound } from "lucide-react";
import { authConfig, currentUser, signOut as endGoogleSession, type AuthConfig, type Me } from "../auth";
import { AppShell, Button, CommandPalette, Logo, SearchButton, page, useCommandPalette, type Command, type NavSection } from "../ui";
import type { LabRow } from "../teach/api";
import type { SubjectRow } from "../sandbox/api";
import { Labs } from "../teach/Labs";
import { LabEditor } from "../teach/LabEditor";
import { Users } from "../teach/Users";
import { Subject, Subjects } from "../teach/Subjects";
import { Setup } from "../teach/Setup";
import { OpenRollCall } from "../teach/Attendance";
import { LiveBoard } from "../compete/LiveBoard";
import { Similar } from "../compete/Similar";
import { LiveClass, LiveLabs } from "../live/LiveClass";
import { LiveEditor } from "../live/LiveEditor";
import { SandboxHome, SandboxSubject } from "../sandbox/Subjects";
import { SandboxLabEditor } from "../sandbox/LabEditor";
import { SandboxLibrary } from "../sandbox/Library";
import { SandboxPreview } from "../sandbox/Preview";
import { get, token } from "./api";
import { Gate } from "./Gate";
import { LabSessions } from "./LabSessions";
import { Overview } from "./Overview";
import { SessionView } from "./SessionView";
import { areaOf, canonicalize, href, parseRoute, routeHash, trail, type Route } from "../routes";

// One teacher area, one sign-in. Every page and its URL is listed in ../routes.ts.
const SECTIONS = (admin: boolean, r: Route): NavSection[] => [
  { items: [
    { href: href.labs, label: "Labs", icon: ListChecks, active: areaOf(r) === "teach" && !["subjects", "subject", "setup", "people"].includes(r.name) },
    { href: href.sandbox, label: "Sandbox Labs", icon: Boxes, active: areaOf(r) === "sandbox" },
    { href: href.subjects, label: "Subjects", icon: BookOpen, active: r.name === "subjects" || r.name === "subject" },
  ] },
  { title: "In class", items: [
    { href: href.live, label: "Live", icon: Radio, active: areaOf(r) === "live" },
    { href: href.review, label: "Review", icon: Activity, active: areaOf(r) === "review" },
  ] },
  { title: "Workspace", items: [
    // Roll Call, class groups, keys (and for admins every teacher's register)
    { href: href.setup, label: "Getting started", icon: Sparkles, active: r.name === "setup" },
    ...(admin ? [{ href: href.people, label: "People", icon: UsersRound, active: r.name === "people" }] : []),
    { href: href.student, label: "View as student", icon: Eye, title: "Open the student side under your own account; nothing you do there is study data" },
  ] },
];

const PAGES: Command[] = [
  { id: "p-labs", label: "Labs", group: "Pages", href: href.labs, icon: ListChecks, keywords: "questions competitions" },
  { id: "p-sbx", label: "Sandbox Labs", group: "Pages", href: href.sandbox, icon: Boxes, keywords: "linux terminal desktop" },
  { id: "p-lib", label: "Sandbox library", group: "Pages", href: href.sbxLibrary, icon: Boxes, keywords: "shared labs" },
  { id: "p-subj", label: "Subjects and rosters", group: "Pages", href: href.subjects, icon: BookOpen },
  { id: "p-live", label: "Live class view", group: "Pages", href: href.live, icon: Radio },
  { id: "p-rev", label: "Review: lab sessions", group: "Pages", href: href.review, icon: Activity, keywords: "timeline flags" },
  { id: "p-all", label: "Review: every session", group: "Pages", href: href.reviewAll, icon: Activity },
  { id: "p-setup", label: "Getting started", group: "Pages", href: href.setup, icon: Sparkles, keywords: "roll call attendance class groups setup" },
  { id: "p-stu", label: "View as student", group: "Pages", href: href.student, icon: Eye, keywords: "preview" },
];

async function loadCommands(): Promise<Command[]> {
  const [labs, subjects] = await Promise.all([
    get<LabRow[]>("/api/teach/labs").catch(() => [] as LabRow[]),
    get<SubjectRow[]>("/api/sandbox/subjects").catch(() => [] as SubjectRow[]),
  ]);
  return [
    ...labs.map((l) => ({ id: `l-${l.id}`, label: l.title, group: "Labs", href: href.lab(l.id), icon: l.kind === "competition" ? Trophy : ListChecks,
      hint: [l.kind === "competition" ? "Competition" : "Lab", l.subject, l.status].filter(Boolean).join(","), keywords: l.subject })),
    ...labs.filter((l) => l.status === "open").map((l) => ({ id: `lv-${l.id}`, label: `Watch ${l.title}`, group: "Live now", href: href.liveLab(l.id), icon: Radio })),
    ...labs.map((l) => ({ id: `r-${l.id}`, label: `Review ${l.title}`, group: "Review", href: href.reviewLab(l.id), icon: Activity })),
    ...subjects.map((s) => ({ id: `s-${s.id}`, label: s.title, group: "Sandbox subjects", href: href.sbxSubject(s.id), icon: Boxes, hint: [s.code, s.semester].filter(Boolean).join(",") })),
  ];
}

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
  const palette = useCommandPalette();
  useEffect(() => { document.title = `${watching ? "Live" : teaching ? "Labs" : "Review"} · Student IDE`; }, [teaching, watching]);

  const signOut = () => {
    token.clear();
    if (cfg?.mode === "google") void endGoogleSession();
    setMe(null);
    setAuthed(false);
  };
  const key = !cfg ? "loading" : !authed ? "gate" : r.name === "lab" ? `lab-${r.id}` : routeHash(r);

  const pageEl = !cfg ? null : !authed ? null : r.name === "people" && me?.role === "admin" ? (
    <Users me={me.email} onAuthLost={signOut} />
  ) : r.name === "sbx-subjects" ? (
    <SandboxHome onAuthLost={signOut} />
  ) : r.name === "sbx-subject" ? (
    <SandboxSubject id={r.id} onAuthLost={signOut} />
  ) : r.name === "sbx-lab" ? (
    <SandboxLabEditor id={r.id} onAuthLost={signOut} />
  ) : r.name === "sbx-library" ? (
    <SandboxLibrary onAuthLost={signOut} />
  ) : r.name === "sbx-preview" ? (
    <SandboxPreview id={r.id} onAuthLost={signOut} />
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
  );

  const animated = (
    <AnimatePresence mode="wait">
      <motion.div key={key} variants={page} initial="initial" animate="animate" exit="exit">
        {!cfg ? null : !authed ? <Gate cfg={cfg} signedInStudent={student} onDone={(u) => { setMe(u); setAuthed(true); }} /> : pageEl}
      </motion.div>
    </AnimatePresence>
  );

  // signed out: the gate on its own, no navigation
  if (!cfg || !authed) {
    return (
      <MotionConfig reducedMotion="user">
        <div className="flex min-h-full flex-col">
          <header className="flex h-14 items-center px-5"><Logo subtitle="Teacher area" /></header>
          <main className="flex-1">{animated}</main>
        </div>
      </MotionConfig>
    );
  }

  return (
    <MotionConfig reducedMotion="user">
      <AppShell
        home={href.labs}
        subtitle="Teacher area"
        nav={SECTIONS(me?.role === "admin", r)}
        trail={trail(r)}
        actions={<>
          <SearchButton onClick={() => palette.setOpen(true)} />
          <HeaderRollCall />
        </>}
        footer={<>
          <p className="flex gap-2 px-2 pb-2.5 text-[11.5px] leading-snug text-faint">
            <MessagesSquare className="mt-px size-3.5 shrink-0" />A highlighted moment starts a conversation, never a penalty.
          </p>
          <div className="flex items-center gap-2 rounded-md px-2 py-1">
            <span className="grid size-7 shrink-0 place-items-center rounded-full text-[11px] font-semibold uppercase text-muted">
              {(me?.email ?? "T").slice(0, 1)}
            </span>
            <span className="min-w-0 flex-1 truncate text-[12.5px] text-muted" title={me?.email}>{me?.email ?? "Teacher (token)"}</span>
            <Button variant="ghost" size="icon" onClick={signOut} aria-label={cfg?.mode === "google" ? "Sign out" : "Lock"} title={cfg?.mode === "google" ? "Sign out" : "Lock"}>
              <LogOut className="size-4" />
            </Button>
          </div>
        </>}
      >
        {animated}
      </AppShell>
      <CommandPalette open={palette.open} onClose={() => palette.setOpen(false)} commands={PAGES} load={loadCommands} />
    </MotionConfig>
  );
}

/** Header shortcut to the teacher's Roll Call, signed in (makes their key on first use). */
function HeaderRollCall() {
  return (
    <span className="hidden md:inline-flex" title="Your attendance register, signed in">
      <OpenRollCall onAuthLost={() => location.reload()} variant="ghost" label="Roll Call" className="text-muted" />
    </span>
  );
}
