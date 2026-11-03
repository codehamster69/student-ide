import { useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "motion/react";
import { ArrowLeft, Eye } from "lucide-react";
import { setPreviewToken, type Lab, type LearnTrack, type Task } from "./api";
import { authConfig, currentUser, signOut as endGoogleSession, type AuthConfig } from "./auth";
import { newSittingId, startSession, type LiveSession } from "./editor/session";
import { page, spring } from "./ui";
import { Shell } from "./screens/Shell";
import { Login } from "./screens/Login";
import { Consent } from "./screens/Consent";
import { Tasks } from "./screens/Tasks";
import { Workspace, type SessionSummary } from "./screens/Workspace";
import { Saved } from "./screens/Saved";
import { Arena } from "./compete/Arena";
import { Learn } from "./learn/Learn";
import { href } from "./routes";

type Screen =
  | { name: "loading" }
  | { name: "login" }
  | { name: "consent"; studentId: string }
  | { name: "tasks"; studentId: string }
  | { name: "arena"; studentId: string; labId: string }
  | { name: "learn"; studentId: string }
  // One practice task or competition question, a whole lab sitting (tasks = its questions),
  // or a learning-lab track (tasks = its lessons; back to the learning lab when done).
  | { name: "session"; studentId: string; tasks: Task[]; start: number; session: LiveSession; sitting?: string; arena?: string; learn?: boolean }
  | { name: "saved"; studentId: string; summary: SessionSummary };

/** The teacher area's dev-mode token (review/api.ts), read here so the student bundle stays small. */
const teacherToken = () => { try { return sessionStorage.getItem("studentide.review.token") ?? ""; } catch { return ""; } };

export function App() {
  const [screen, setScreen] = useState<Screen>({ name: "loading" });
  const [cfg, setCfg] = useState<AuthConfig | null>(null);
  // "View as student" (#/student from the teacher area): a teacher or admin under their own staff id
  const [preview, setPreview] = useState(false);
  const signedIn = (studentId: string, consented: boolean) =>
    setScreen(consented ? { name: "tasks", studentId } : { name: "consent", studentId });
  const signOut = () => {
    if (preview) {
      location.hash = href.labs;
      return;
    }
    if (cfg?.mode === "google") void endGoogleSession();
    setScreen({ name: "login" });
  };

  // With Google sign-in the session cookie survives a reload, so pick up where the student was.
  useEffect(() => {
    authConfig().then(async (c) => {
      setCfg(c);
      const me = c.mode === "google" ? await currentUser() : null;
      const wantsPreview = location.hash.startsWith("#/student");
      if (me && me.role === "student") signedIn(me.student_id, me.consented);
      // staff skip consent: nothing they do here is study data (the server files it as a preview)
      else if (wantsPreview && me) { setPreview(true); setScreen({ name: "tasks", studentId: me.student_id }); }
      else if (wantsPreview && c.mode === "dev" && teacherToken()) {
        setPreviewToken(teacherToken());
        setPreview(true);
        setScreen({ name: "tasks", studentId: "STAFF_PREVIEW" });
      } else setScreen({ name: "login" });
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
          <Login cfg={cfg!} onDone={signedIn} onTeacher={() => { location.hash = href.labs; }} />
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
            onLearn={() => setScreen({ name: "learn", studentId: screen.studentId })}
          />
        </Shell>
      );
      break;
    case "learn":
      content = (
        <Shell step={2} studentId={screen.studentId} onSignOut={signOut}>
          <Learn
            studentId={screen.studentId}
            onBack={() => setScreen({ name: "tasks", studentId: screen.studentId })}
            onOpen={async (track: LearnTrack, start: number) => {
              const session = await startSession(screen.studentId, track.lessons[start]);
              setScreen({ name: "session", studentId: screen.studentId, tasks: track.lessons, start, session, learn: true });
            }}
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
            : screen.learn ? { name: "learn", studentId: screen.studentId }
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
      {preview && <PreviewBar />}
    </MotionConfig>
  );
}

/** Always on screen in "View as student", so a teacher never mistakes it for a student's account. */
function PreviewBar() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0, transition: { delay: 0.3, ...spring } }}
      role="status"
      className="fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-full border border-warn/40 bg-surface py-1.5 pl-3.5 pr-1.5 text-xs text-muted shadow-lg"
    >
      <Eye className="size-3.5 text-warn" />
      <span><strong className="font-semibold text-text">Student view.</strong> Your labs as students see them. Nothing here counts as student data.</span>
      <a href={href.labs} className="flex h-7 items-center gap-1 rounded-full bg-surface-3 px-2.5 font-medium text-text hover:bg-surface-2">
        <ArrowLeft className="size-3.5" />Back to Teach
      </a>
    </motion.div>
  );
}
