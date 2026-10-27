import { useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import type { Task } from "./api";
import { authConfig, currentUser, signOut as endGoogleSession, type AuthConfig } from "./auth";
import { startSession, type LiveSession } from "./editor/session";
import { page } from "./ui";
import { Shell } from "./screens/Shell";
import { Login } from "./screens/Login";
import { Consent } from "./screens/Consent";
import { Tasks } from "./screens/Tasks";
import { Workspace, type SessionSummary } from "./screens/Workspace";
import { Saved } from "./screens/Saved";
import { Arena } from "./compete/Arena";

type Screen =
  | { name: "loading" }
  | { name: "login" }
  | { name: "consent"; studentId: string }
  | { name: "tasks"; studentId: string }
  | { name: "arena"; studentId: string; labId: string }
  | { name: "session"; studentId: string; task: Task; session: LiveSession; arena?: string }
  | { name: "saved"; studentId: string; summary: SessionSummary };

export function App() {
  const [screen, setScreen] = useState<Screen>({ name: "loading" });
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  const signedIn = (studentId: string, consented: boolean) =>
    setScreen(consented ? { name: "tasks", studentId } : { name: "consent", studentId });
  const signOut = () => {
    if (cfg?.mode === "google") void endGoogleSession();
    setScreen({ name: "login" });
  };

  // With Google sign-in the session cookie survives a reload, so pick up where the student was.
  useEffect(() => {
    authConfig().then(async (c) => {
      setCfg(c);
      const me = c.mode === "google" ? await currentUser() : null;
      if (me && me.role === "student") signedIn(me.student_id, me.consented);
      else setScreen({ name: "login" });
    });
  }, []);

  let content;
  switch (screen.name) {
    case "loading":
      content = <Shell step={0}>{null}</Shell>;
      break;
    case "login":
      content = (
        <Shell step={0}>
          <Login cfg={cfg!} onDone={signedIn} onTeacher={() => { location.hash = "#/teach"; }} />
        </Shell>
      );
      break;
    case "consent":
      content = (
        <Shell step={1} studentId={screen.studentId} onSignOut={signOut}>
          <Consent studentId={screen.studentId} onDone={() => setScreen({ name: "tasks", studentId: screen.studentId })} />
        </Shell>
      );
      break;
    case "tasks":
      content = (
        <Shell step={2} studentId={screen.studentId} onSignOut={signOut}>
          <Tasks
            studentId={screen.studentId}
            onPick={async (task) => {
              const session = await startSession(screen.studentId, task);
              setScreen({ name: "session", studentId: screen.studentId, task, session });
            }}
            onCompetition={(labId) => setScreen({ name: "arena", studentId: screen.studentId, labId })}
          />
        </Shell>
      );
      break;
    case "arena":
      content = (
        <Shell step={2} studentId={screen.studentId} onSignOut={signOut}>
          <Arena
            studentId={screen.studentId}
            labId={screen.labId}
            onBack={() => setScreen({ name: "tasks", studentId: screen.studentId })}
            onPick={async (task) => {
              const session = await startSession(screen.studentId, task);
              setScreen({ name: "session", studentId: screen.studentId, task, session, arena: screen.labId });
            }}
          />
        </Shell>
      );
      break;
    case "session":
      content = (
        <Workspace
          studentId={screen.studentId}
          task={screen.task}
          session={screen.session}
          onFinished={(summary) => setScreen(screen.arena
            ? { name: "arena", studentId: screen.studentId, labId: screen.arena }
            : { name: "saved", studentId: screen.studentId, summary })}
        />
      );
      break;
    case "saved":
      content = (
        <Shell step={3} studentId={screen.studentId} onSignOut={signOut}>
          <Saved summary={screen.summary} onAnother={() => setScreen({ name: "tasks", studentId: screen.studentId })} />
        </Shell>
      );
      break;
  }

  // Sign-in screens share one Shell so the stepper animates between them; the
  // editor gets its own full-screen layer.
  const layer = screen.name === "session" ? `session-${screen.session.id}` : screen.name === "arena" ? `arena-${screen.labId}` : "shell";
  return (
    <MotionConfig reducedMotion="user">
      <AnimatePresence mode="wait">
        <motion.div key={layer} variants={page} initial="initial" animate="animate" exit="exit" className="h-full">
          {content}
        </motion.div>
      </AnimatePresence>
    </MotionConfig>
  );
}
