import { useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import type { Lab, Task } from "./api";
import { authConfig, currentUser, signOut as endGoogleSession, type AuthConfig } from "./auth";
import { newSittingId, startSession, type LiveSession } from "./editor/session";
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
  // One practice task or competition question, or a whole lab sitting (tasks = its questions).
  | { name: "session"; studentId: string; tasks: Task[]; start: number; session: LiveSession; sitting?: string; arena?: string }
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
              setScreen({ name: "session", studentId: screen.studentId, tasks: [task], start: 0, session });
            }}
            onOpenLab={async (lab: Lab, start: number) => {
              const sitting = newSittingId();
              const session = await startSession(screen.studentId, lab.questions[start], sitting);
              setScreen({ name: "session", studentId: screen.studentId, tasks: lab.questions, start, session, sitting });
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
              setScreen({ name: "session", studentId: screen.studentId, tasks: [task], start: 0, session, arena: screen.labId });
            }}
          />
        </Shell>
      );
      break;
    case "session":
      content = (
        <Workspace
          studentId={screen.studentId}
          tasks={screen.tasks}
          start={screen.start}
          session={screen.session}
          openSession={(task, language) => startSession(screen.studentId, task, screen.sitting, language)}
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
