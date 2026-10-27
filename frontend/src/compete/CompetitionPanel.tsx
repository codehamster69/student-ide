import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertTriangle, CheckCircle2, MonitorPlay, Play, Square, Trophy } from "lucide-react";
import { Badge, Button, Card, Dialog, Input, LiveDot, Spinner, cn } from "../ui";
import { AuthError, get, send } from "../review/api";
import { BOARD_MODES, type BoardMode, type CompState, type TeacherComp } from "./api";
import { Countdown } from "./Leaderboard";

const STATE: Record<CompState, { label: string; tone: "neutral" | "accent" | "success" | "warn" }> = {
  draft: { label: "Draft", tone: "neutral" },
  waiting: { label: "Lobby open", tone: "accent" },
  live: { label: "Live", tone: "success" },
  ended: { label: "Ended", tone: "warn" },
  closed: { label: "Closed", tone: "neutral" },
};

/** Sidebar card on a competition's lab page: clock, what students see, start and end. */
export function CompetitionPanel({ labId, version, onChanged, onAuthLost }: {
  labId: string;
  /** bumps whenever the lab page saved something (questions, roster, status) */
  version: unknown;
  onChanged: () => void;
  onAuthLost: () => void;
}) {
  const [c, setC] = useState<TeacherComp | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const [minutes, setMinutes] = useState("");

  const take = useCallback((next: TeacherComp) => {
    setC(next);
    setOffset(next.now - Date.now() / 1000);
    setMinutes(next.duration_min ? String(next.duration_min) : "");
  }, []);
  const fail = useCallback((e: unknown) => (e instanceof AuthError ? onAuthLost() : setError((e as Error).message)), [onAuthLost]);

  useEffect(() => { get<TeacherComp>(`/api/teach/competitions/${labId}`).then(take, fail); }, [labId, version, take, fail]);
  useEffect(() => {
    if (c?.state !== "live") return;
    const t = window.setInterval(() => get<TeacherComp>(`/api/teach/competitions/${labId}`).then(setC, () => {}), 5000);
    return () => window.clearInterval(t);
  }, [labId, c?.state]);

  const act = async (method: string, path: string, body?: unknown) => {
    setBusy(true);
    setError("");
    try {
      take(await send<TeacherComp>(method, `/api/teach/competitions/${labId}${path}`, body));
      onChanged();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  if (!c) return <Card className="p-5"><Spinner /></Card>;
  const untested = c.questions.filter((q) => q.n_tests === 0);
  const started = c.started_at !== null;
  const ready = c.questions.length > 0 && untested.length === 0;

  return (
    <Card className="relative overflow-clip border-gold/30 p-5">
      <div className="pointer-events-none absolute -right-12 -top-12 size-36 rounded-full bg-gold/10 blur-2xl" />
      <div className="relative flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text"><Trophy className="size-4 text-gold" /> Competition</h2>
        <Badge tone={STATE[c.state].tone}>{c.state === "live" && <LiveDot tone="success" />}{STATE[c.state].label}</Badge>
      </div>

      {started && (
        <div className="relative mt-4 flex items-center justify-between rounded-xl bg-surface-2 px-4 py-3">
          <Countdown comp={c} offset={offset} className="text-2xl" />
          <span className="text-xs text-muted">{c.board.length} on the board</span>
        </div>
      )}
      {started && (
        <a href={`#/teach/c/${labId}`} className="relative mt-3 grid gap-1 rounded-xl border border-border px-3 py-2.5 transition-colors hover:bg-surface-2"
          title="Open the full leaderboard">
          {c.handing_in && <p className="flex items-center gap-2 text-xs text-muted"><Spinner className="size-3" /> Grading the code students had open…</p>}
          {c.board.slice(0, 5).map((r) => (
            <p key={r.handle} className="flex items-center gap-2 text-xs">
              <span className="w-6 font-mono text-faint">#{r.rank}</span>
              <span className="flex-1 truncate text-text">{r.handle}</span>
              <span className="font-semibold tabular-nums text-text">{r.points}</span>
            </p>
          ))}
          {!c.board.length && <p className="text-xs text-muted">Nobody on the board yet.</p>}
          {c.board.length > 5 && <p className="text-xs text-faint">and {c.board.length - 5} more</p>}
        </a>
      )}

      <div className="relative mt-4 grid gap-3">
        <label className="flex items-center justify-between gap-3 text-[13px]">
          <span className="font-medium text-text">Clock</span>
          <span className="flex items-center gap-2">
            <Input type="number" min={0} max={600} value={minutes} disabled={started || busy} placeholder="none"
              onChange={(e) => setMinutes(e.target.value)}
              onBlur={() => Number(minutes || 0) !== (c.duration_min ?? 0) && void act("PATCH", "", { duration_min: Number(minutes || 0) })}
              className="h-8 w-20 text-right tabular-nums" aria-label="Clock in minutes" />
            <span className="text-muted">min</span>
          </span>
        </label>
        <div className="grid gap-1.5">
          <span className="text-[13px] font-medium text-text">Students see</span>
          <div className="flex rounded-lg border border-border bg-surface p-0.5">
            {(Object.keys(BOARD_MODES) as BoardMode[]).map((m) => (
              <button key={m} onClick={() => m !== c.board_mode && void act("PATCH", "", { board: m })} disabled={busy}
                className={cn("h-7 flex-1 rounded-md text-xs font-medium transition-colors",
                  c.board_mode === m ? "bg-surface-3 text-text" : "text-muted hover:text-text")}>
                {BOARD_MODES[m].label}
              </button>
            ))}
          </div>
          <span className="text-xs text-muted">{BOARD_MODES[c.board_mode].about}</span>
        </div>
      </div>

      <div className="relative mt-4 grid gap-1.5 border-t border-border pt-4">
        <span className="text-[13px] font-medium text-text">Test cases</span>
        {c.questions.length === 0 && <p className="text-xs text-muted">Add questions on the left first.</p>}
        {c.questions.map((q, i) => (
          <p key={q.id} className="flex items-center gap-2 text-xs">
            {q.n_tests ? <CheckCircle2 className="size-3.5 text-success" /> : <AlertTriangle className="size-3.5 text-warn" />}
            <span className="font-mono text-faint">Q{i + 1}</span>
            <span className="flex-1 truncate text-text">{q.title}</span>
            <span className={q.n_tests ? "text-muted" : "text-warn"}>{q.n_tests ? `${q.n_tests} test${q.n_tests === 1 ? "" : "s"}` : "needs tests"}</span>
          </p>
        ))}
        <p className="mt-1 text-xs text-faint">Competitions always check correctness: each submission is scored on these tests.</p>
      </div>

      <AnimatePresence>
        {error && (
          <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
            className="relative mt-3 overflow-hidden rounded-lg bg-danger-soft px-3 py-2 text-xs text-danger" role="alert">{error}</motion.p>
        )}
      </AnimatePresence>

      <div className="relative mt-4 grid gap-2">
        {!started && (
          <Button variant="primary" onClick={() => void act("POST", "/start")} disabled={busy || !ready}
            title={ready ? "Opens the lab and starts the clock" : "Every question needs at least one test"}>
            {busy ? <Spinner /> : <Play className="size-4 fill-current" />} Start the clock
          </Button>
        )}
        {c.state === "live" && (
          <Button onClick={() => setConfirmEnd(true)} disabled={busy}><Square className="size-3.5 fill-current" /> End now</Button>
        )}
        <a href={`#/teach/c/${labId}`}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-surface text-sm font-medium text-text shadow-sm transition-colors hover:bg-surface-2">
          <MonitorPlay className="size-4" /> Open leaderboard
        </a>
        {!started && <p className="text-xs text-muted">Tip: set the lab to Open first so students can wait in the lobby and pick their board names.</p>}
      </div>

      <Dialog open={confirmEnd} onClose={() => setConfirmEnd(false)} icon={<Square className="size-4" />}
        title="End the competition now?" description="Submissions stop and the board freezes. Students see the final standings."
        actions={<>
          <Button onClick={() => setConfirmEnd(false)} data-autofocus>Keep going</Button>
          <Button variant="primary" onClick={() => { setConfirmEnd(false); void act("POST", "/end"); }}>End now</Button>
        </>} />
    </Card>
  );
}
