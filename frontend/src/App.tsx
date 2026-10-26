import { useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import type { Task } from "./api";
import { startSession, type LiveSession } from "./editor/session";
import { page } from "./ui";
import { Shell } from "./screens/Shell";
import { Login } from "./screens/Login";
import { Consent } from "./screens/Consent";
import { Tasks } from "./screens/Tasks";
import { Workspace, type SessionSummary } from "./screens/Workspace";
import { Saved } from "./screens/Saved";

type Screen =
  | { name: "login" }
  | { name: "consent"; studentId: string }
  | { name: "tasks"; studentId: string }
  | { name: "session"; studentId: string; task: Task; session: LiveSession }
  | { name: "saved"; studentId: string; summary: SessionSummary };

export function App() {
  const [screen, setScreen] = useState<Screen>({ name: "login" });
  const signOut = () => setScreen({ name: "login" });

  let content;
  switch (screen.name) {
    case "login":
      content = (
        <Shell step={0}>
          <Login onDone={(studentId, consented) => setScreen(consented ? { name: "tasks", studentId } : { name: "consent", studentId })} />
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
          onFinished={(summary) => setScreen({ name: "saved", studentId: screen.studentId, summary })}
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
  const layer = screen.name === "session" ? `session-${screen.session.id}` : "shell";
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
