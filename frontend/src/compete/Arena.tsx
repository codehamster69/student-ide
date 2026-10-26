import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowUpRight, CheckCircle2, CircleDot, FlaskConical, Trophy, Users } from "lucide-react";
import { api } from "../api";
import { Badge, Button, Card, Input, LiveDot, Spinner, cn, item, pop, spring, stagger } from "../ui";
import { POINTS, type ArenaQuestion, type ArenaView } from "./api";
import { BadgeChip, Countdown, Leaderboard, Podium, RankMark, Ticker } from "./Leaderboard";

const POLL_MS = 3000;

/** The student's competition screen: lobby, then questions with a live board, then the podium. */
export function Arena({ studentId, labId, onPick, onBack }: {
  studentId: string;
  labId: string;
  onPick: (q: ArenaQuestion) => Promise<void>;
  onBack: () => void;
}) {
  const [view, setView] = useState<ArenaView | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [opening, setOpening] = useState<string | null>(null);
  const alive = useRef(true);

  const load = useCallback(async () => {
    try {
      const v = await api<ArenaView>(`/api/competitions/${labId}?student_id=${encodeURIComponent(studentId)}`);
      if (!alive.current) return;
      setOffset(v.now - Date.now() / 1000);
      setView(v);
      setError("");
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    }
  }, [labId, studentId]);

  useEffect(() => {
    alive.current = true;
    void load();
    const t = window.setInterval(() => void load(), POLL_MS);
    return () => { alive.current = false; window.clearInterval(t); };
  }, [load]);

  const pick = async (q: ArenaQuestion) => {
    if (opening) return;
    setOpening(q.id);
    try {
      await onPick(q);
    } catch (e) {
      setError((e as Error).message);
      setOpening(null);
      void load();
    }
  };

  if (!view) {
    return (
      <div className="flex w-full max-w-5xl justify-center pt-10 text-muted">
        {error ? <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p> : <Spinner className="size-5" />}
      </div>
    );
  }

  const nQ = view.questions.length;
  return (
    <motion.div variants={stagger(0.06)} initial="initial" animate="animate" className="w-full max-w-5xl">
      <motion.button variants={item} onClick={onBack} className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted hover:text-text">
        <ArrowLeft className="size-4" /> Your labs
      </motion.button>

      <motion.div variants={item} className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-gold">
            <Trophy className="size-3.5" /> Class competition
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text">{view.title}</h1>
          {view.description && <p className="mt-1 max-w-2xl text-sm text-muted">{view.description}</p>}
        </div>
        {view.state !== "waiting" && (
          <Card className="flex items-center gap-3 px-4 py-2.5 shadow-sm">
            {view.state === "live" && <LiveDot tone="success" />}
            <Countdown comp={view} offset={offset} className="text-xl" />
          </Card>
        )}
      </motion.div>

      {error && <p className="mt-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>}

      <AnimatePresence mode="wait">
        <motion.div key={view.state} variants={pop} initial="initial" animate="animate" exit="exit" className="mt-6">
          {view.state === "waiting" ? (
            <Lobby view={view} studentId={studentId} onJoined={setView} />
          ) : (
            <div className="grid items-start gap-6 lg:grid-cols-[1fr_380px]">
              <section className="grid gap-4">
                {view.state === "ended" && view.board.length > 0 && (
                  <Card className="px-5 pb-5 pt-4">
                    <h2 className="text-center text-sm font-semibold text-text">Final standings</h2>
                    <Podium rows={view.board} />
                  </Card>
                )}
                {view.me && <MyStanding me={view.me} nQ={nQ} ended={view.state === "ended"} />}
                <div className="grid gap-2.5">
                  {view.questions.map((q, i) => (
                    <QuestionRow key={q.id} q={q} i={i} live={view.state === "live"} opening={opening} onPick={() => void pick(q)} />
                  ))}
                </div>
                <Rules />
              </section>
              <aside className="lg:sticky lg:top-6">
                <Card className="p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-text">Leaderboard</h2>
                    <span className="flex items-center gap-1 text-xs text-muted"><Users className="size-3.5" />{view.n_players}</span>
                  </div>
                  <Leaderboard rows={view.board} nQuestions={nQ}
                    empty={view.board_mode === "hidden" ? "The board is revealed when time is up. Your own score is on the left." : "No scores yet. Be the first!"} />
                  {view.board_mode === "top" && view.n_players > view.board.length && (
                    <p className="mt-3 text-center text-xs text-faint">Showing the top {view.board.length} of {view.n_players}.</p>
                  )}
                </Card>
              </aside>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}

function Lobby({ view, studentId, onJoined }: { view: ArenaView; studentId: string; onJoined: (v: ArenaView) => void }) {
  const mine = view.me?.handle;
  const [handle, setHandle] = useState(mine && mine !== studentId ? mine : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const join = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onJoined(await api<ArenaView>(`/api/competitions/${view.lab_id}/join`, { student_id: studentId, handle }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_1fr]">
      <Card className="relative overflow-hidden p-6">
        <div className="pointer-events-none absolute -right-10 -top-10 size-40 rounded-full bg-gold/10 blur-2xl" />
        <motion.span animate={{ rotate: [0, -8, 8, 0] }} transition={{ duration: 1.6, repeat: Infinity, repeatDelay: 2.4 }}
          className="grid size-12 place-items-center rounded-2xl bg-gold-soft text-gold"><Trophy className="size-6" /></motion.span>
        <h2 className="mt-4 text-lg font-semibold text-text">{view.joined ? "You're in" : "Join the competition"}</h2>
        <p className="mt-1 text-sm text-muted">
          Pick the name the class will see on the board, or leave it empty to use your roll number. Questions appear when your teacher starts the clock
          {view.duration_min ? ` (${view.duration_min} minutes)` : ""}.
        </p>
        <form onSubmit={join} className="mt-5 flex gap-2">
          <Input value={handle} onChange={(e) => setHandle(e.target.value)} maxLength={24} placeholder={studentId} aria-label="Name on the board" />
          <Button type="submit" variant="primary" className="h-11" disabled={busy}>
            {busy && <Spinner />} {view.joined ? "Update" : "Join"}
          </Button>
        </form>
        {error && <p className="mt-2 text-sm text-danger">{error}</p>}
        <p className="mt-5 flex items-center gap-2 text-sm text-muted"><LiveDot tone="accent" /> Waiting for your teacher to start…</p>
      </Card>
      <Card className="p-6">
        <h2 className="flex items-center justify-between text-sm font-semibold text-text">
          Here so far <span className="text-xs font-normal tabular-nums text-muted">{view.lobby.length}</span>
        </h2>
        <div className="mt-4 flex flex-wrap gap-2">
          <AnimatePresence initial={false}>
            {view.lobby.map((h) => (
              <motion.span key={h} layout initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} transition={spring}
                className={cn("inline-flex h-8 items-center rounded-full border px-3 text-sm",
                  h === view.me?.handle ? "border-accent/40 bg-accent-soft text-accent" : "border-border bg-surface-2 text-text")}>
                {h}
              </motion.span>
            ))}
          </AnimatePresence>
          {!view.lobby.length && <p className="text-sm text-faint">Nobody yet. Be the first to join.</p>}
        </div>
        <div className="mt-6 border-t border-border pt-4"><Rules /></div>
      </Card>
    </div>
  );
}

function MyStanding({ me, nQ, ended }: { me: NonNullable<ArenaView["me"]>; nQ: number; ended: boolean }) {
  return (
    <Card className="flex flex-wrap items-center gap-5 p-5">
      <RankMark rank={me.rank} className="size-12 text-lg" />
      <div className="min-w-0 flex-1">
        <p className="text-xs text-muted">{ended ? "You finished" : "You are"}</p>
        <p className="text-lg font-semibold text-text">
          #{me.rank} <span className="text-sm font-normal text-muted">of {me.of}</span>
        </p>
        {me.badges.length > 0 && <div className="mt-1.5 flex flex-wrap gap-1">{me.badges.map((b) => <BadgeChip key={b.id} b={b} />)}</div>}
      </div>
      <div className="text-right">
        <p className="text-3xl font-semibold text-text"><Ticker value={me.points} /></p>
        <p className="text-xs text-muted">points · {me.solved}/{nQ} solved</p>
      </div>
    </Card>
  );
}

function QuestionRow({ q, i, live, opening, onPick }: { q: ArenaQuestion; i: number; live: boolean; opening: string | null; onPick: () => void }) {
  const p = q.progress;
  const partial = p && p.total && !p.solved && p.passed !== null;
  return (
    <motion.button variants={item} whileHover={live ? { x: 3 } : undefined} whileTap={live ? { scale: 0.99 } : undefined} transition={spring}
      onClick={onPick} disabled={!live || !!opening}
      className="group flex items-center gap-4 rounded-xl border border-border bg-surface px-4 py-3.5 text-left shadow-sm transition-[border-color,box-shadow] duration-200 enabled:hover:border-accent/40 enabled:hover:shadow-md disabled:cursor-default">
      <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg font-mono text-xs font-semibold",
        p?.solved ? "bg-success-soft text-success" : partial ? "bg-warn-soft text-warn" : "bg-accent-soft text-accent")}>
        {opening === q.id ? <Spinner /> : p?.solved ? <CheckCircle2 className="size-4" /> : partial ? <CircleDot className="size-4" /> : i + 1}
      </span>
      <span className="min-w-0 flex-1">
        <strong className="block text-sm font-semibold text-text">{q.title}</strong>
        <span className="line-clamp-1 text-[13px] text-muted">{q.prompt}</span>
      </span>
      {p?.solved ? <Badge tone="success">Solved · {p.points} pts</Badge>
        : partial ? <Badge tone="warn">{p!.passed}/{p!.total} tests · {p!.points} pts</Badge>
        : p?.tries ? <Badge>{p.tries} {p.tries === 1 ? "try" : "tries"}</Badge> : null}
      {live && <ArrowUpRight className="size-4 shrink-0 text-faint transition-[transform,color] duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent" />}
    </motion.button>
  );
}

function Rules() {
  return (
    <div className="grid gap-2 text-[13px] text-muted">
      <p className="flex items-center gap-1.5 font-medium text-text"><FlaskConical className="size-3.5 text-accent" /> How points work</p>
      <p>Submit runs your code against the question's test cases. You get up to {POINTS.solve} points for the tests you pass, and up to {POINTS.speed} more for solving every test early. Only your best submission counts, and a wrong one costs nothing, so try as often as you like.</p>
    </div>
  );
}
