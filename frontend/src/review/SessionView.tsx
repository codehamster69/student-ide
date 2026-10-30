import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowLeft, ChevronLeft, ChevronRight, ClipboardPaste, RotateCcw, Eye, EyeOff, FlaskConical, HeartHandshake,
  MessageCircleQuestion, Pause, Play, Play as RunIcon, ScanEye, SkipBack,
  Trophy,
} from "lucide-react";
import { Badge, Button, Card, RhythmBars, cn, item, pop, spring, stagger } from "../ui";
import { AuthError, CHANNELS, get, type Episode, type ReplayData, type Review } from "./api";
import { CH_CHANGED, CH_COLOR, ChannelTag, Skeleton } from "./bits";
import { CodeReplay } from "./CodeReplay";
import { Timeline } from "./Timeline";
import { changedLines, Replayer } from "./replay";
import { clock, CONDITION, dayKey, dayTime, TASKS, value } from "./format";

const SPEEDS = [1, 5, 20, 60];
const RECENT_S = 30;

export function SessionView({ id, onAuthLost }: { id: string; onAuthLost: () => void }) {
  const [review, setReview] = useState<Review | null>(null);
  const [replay, setReplay] = useState<Replayer | null>(null);
  const [error, setError] = useState("");
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(20);
  const [dragging, setDragging] = useState(false);
  const [truth, setTruth] = useState(false);
  const [focusEp, setFocusEp] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([get<Review>(`/api/review/sessions/${id}`), get<ReplayData>(`/api/review/sessions/${id}/replay`)])
      .then(([r, rep]) => {
        setReview(r);
        setReplay(new Replayer(rep));
        // open at the first moment to discuss, else at the end
        setT(r.episodes.length ? Math.max(0, r.episodes[0].switch_est - 15) : r.session.duration_s);
      })
      .catch((e) => (e instanceof AuthError ? onAuthLost() : setError(e.message)));
  }, [id, onAuthLost]);

  // playback
  const last = useRef<number | null>(null);
  useEffect(() => {
    if (!playing || !review) return;
    let raf = 0;
    const tick = (now: number) => {
      const dt = last.current === null ? 0 : (now - last.current) / 1000;
      last.current = now;
      setT((prev) => {
        const next = prev + dt * speed;
        if (next >= review.session.duration_s) { setPlaying(false); return review.session.duration_s; }
        return next;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(raf); last.current = null; };
  }, [playing, speed, review]);

  const seek = useCallback((s: number) => { setT(s); }, []);
  const togglePlay = useCallback(() => {
    if (!review) return;
    if (!playing && t >= review.session.duration_s - 0.5) setT(0);
    setPlaying((p) => !p);
  }, [playing, t, review]);

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, textarea, button")) return;
      if (e.code === "Space") { e.preventDefault(); togglePlay(); }
      if (e.code === "ArrowRight") setT((v) => Math.min(review?.session.duration_s ?? 0, v + 10));
      if (e.code === "ArrowLeft") setT((v) => Math.max(0, v - 10));
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [togglePlay, review]);

  // code at the playhead (the doc only changes when the edit count does)
  const n = replay ? replay.count(t * 1000) : 0;
  const n0 = replay ? replay.count((t - RECENT_S) * 1000) : 0;
  const code = useMemo(() => {
    if (!replay) return { doc: "", changed: [] as number[], caret: 0, origin: "" };
    const doc = replay.docAt(n);
    const changed = [...changedLines(replay.docAt(n0), doc)];
    const e = n > 0 ? replay.edit(n - 1) : null;
    const caret = e?.[1].length ? e[1][0][0] + e[1][0][2].length : 0;
    return { doc, changed, caret, origin: e?.[2] ?? "" };
  }, [replay, n, n0]);
  const rhythm = replay ? replay.intervals(t * 1000) : [];

  if (error) return <div className="mx-auto max-w-3xl px-5 pt-16"><Card className="p-6 text-sm text-danger">{error}</Card></div>;
  if (!review || !replay) return <Loading />;

  const s = review.session;
  const syn = s.synthetic;
  const eps = review.episodes;
  const nextEp = eps.find((e) => e.switch_est - 15 > t + 1);
  const prevEp = [...eps].reverse().find((e) => e.switch_est - 15 < t - 1);

  return (
    <motion.div variants={stagger(0.07)} initial="initial" animate="animate" className="mx-auto max-w-[1440px] px-5 pb-20 pt-6">
      <motion.a variants={item} href={`#/review/l/${s.lab_id ?? "practice"}/${dayKey(s.started_at)}`} className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted transition-colors hover:text-text">
        <ArrowLeft className="size-4" /> {s.lab_id ? "Back to the lab session" : "Practice sessions"}
      </motion.a>

      {/* header */}
      <motion.div variants={item} className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-accent to-[#8b5cf6] font-mono text-sm font-semibold text-white shadow-md">
            {s.student_id.slice(-2)}
          </span>
          <div>
            <h1 className="flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight text-text">
              <span className="font-mono">{s.student_id}</span>
              <span className="text-faint">·</span>
              <span>{s.task_title ?? TASKS[s.task_id] ?? s.task_id}</span>
            </h1>
            <p className="mt-0.5 text-sm text-muted">
              {dayTime(s.started_at)} · {clock(s.duration_s)} long · compared with {review.baseline.n_sessions}{" "}
              {s.context === "competition"
                ? `session${review.baseline.n_sessions === 1 ? "" : "s"} from this student's other competitions`
                : `baseline session${review.baseline.n_sessions === 1 ? "" : "s"}`}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {s.context === "competition" && <Badge tone="warn"><Trophy className="size-3.5" /> Competition</Badge>}
          {s.phase === "baseline" ? <Badge>Baseline week</Badge> : <Badge tone="accent">Reviewed session</Badge>}
          {syn && (
            <>
              <Badge tone="warn"><FlaskConical className="size-3.5" /> Simulated</Badge>
              <Button size="sm" variant={truth ? "primary" : "secondary"} onClick={() => setTruth((v) => !v)} aria-pressed={truth}>
                {truth ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />} Ground truth
              </Button>
            </>
          )}
        </div>
      </motion.div>

      <AnimatePresence>
        {truth && syn && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <p className="mb-4 rounded-xl border border-dashed border-border-strong bg-surface px-4 py-2.5 text-sm text-muted">
              <span className="font-medium text-text">Simulated condition: {CONDITION[syn.condition]}.</span>{" "}
              {syn.condition === "honest" ? "The same simulated student typed the whole session." :
                syn.condition === "proxy" ? `Typed throughout by ${syn.author_after}.` :
                syn.condition === "takeover" ? `${syn.author_after} took over at ${clock(syn.switch_s ?? 0)}.` :
                `The student switched to ${syn.condition === "copying" ? "copying from another window" : "pasting code"} at ${clock(syn.switch_s ?? 0)}.`}
              {" "}Shown only for demo data, so the detector can be checked against what really happened.
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div variants={item}><Verdict review={review} /></motion.div>

      {/* timeline */}
      <Card variants={item} className="mt-5 p-4 pb-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-3 px-1">
          <div className="flex items-center gap-1.5">
            <Button size="icon" variant="ghost" onClick={() => { setPlaying(false); setT(0); }} aria-label="Back to start"><SkipBack className="size-4" /></Button>
            <Button size="icon" variant="ghost" disabled={!prevEp} onClick={() => prevEp && setT(Math.max(0, prevEp.switch_est - 15))} aria-label="Previous moment"><ChevronLeft className="size-4" /></Button>
            <Button size="sm" variant="primary" onClick={togglePlay} className="w-24">
              <AnimatePresence mode="wait" initial={false}>
                <motion.span key={playing ? "p" : "r"} initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.6, opacity: 0 }} transition={{ duration: 0.12 }} className="inline-flex items-center gap-1.5">
                  {playing ? <><Pause className="size-3.5" /> Pause</> : <><Play className="size-3.5" /> Replay</>}
                </motion.span>
              </AnimatePresence>
            </Button>
            <Button size="icon" variant="ghost" disabled={!nextEp} onClick={() => nextEp && setT(Math.max(0, nextEp.switch_est - 15))} aria-label="Next moment"><ChevronRight className="size-4" /></Button>
            <div className="ml-2 flex rounded-lg border border-border bg-surface-2 p-0.5">
              {SPEEDS.map((sp) => (
                <button key={sp} onClick={() => setSpeed(sp)} className={cn("relative h-7 rounded-md px-2.5 font-mono text-xs transition-colors", speed === sp ? "text-text" : "text-muted hover:text-text")}>
                  {speed === sp && <motion.span layoutId="speed-pill" transition={spring} className="absolute inset-0 rounded-md bg-surface shadow-sm" />}
                  <span className="relative">{sp}×</span>
                </button>
              ))}
            </div>
          </div>
          <Legend />
        </div>
        <div onPointerDown={() => { setPlaying(false); setDragging(true); }} onPointerUp={() => setDragging(false)}>
          <Timeline review={review} t={t} onSeek={seek} instant={playing || dragging} showTruth={truth} focusEpisode={focusEp} onFocusEpisode={setFocusEp} />
        </div>
      </Card>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1.35fr_1fr]">
        {/* replay */}
        <Card variants={item} className="flex flex-col overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
            <p className="flex items-center gap-2 text-sm font-medium text-text"><ScanEye className="size-4 text-accent" /> Code at <span className="font-mono tabular-nums">{clock(t)}</span></p>
            <p className="flex items-center gap-2 text-xs text-muted">
              <span className="inline-block size-2.5 rounded-sm bg-accent/25 ring-1 ring-accent/60" /> changed in the last 30 s
              {code.origin === "input.paste" && <Badge tone="warn" className="h-5 px-2 text-[11px]"><ClipboardPaste className="size-3" /> last change was a paste</Badge>}
              {code.origin === "reset" && <Badge className="h-5 px-2 text-[11px]"><RotateCcw className="size-3" /> student reset to the starter code</Badge>}
            </p>
          </div>
          <div className="h-[430px]"><CodeReplay doc={code.doc} changed={code.changed} caret={code.caret} /></div>
          <div className="border-t border-border bg-surface-2/50 px-4 py-3">
            <div className="mb-1.5 flex items-center justify-between text-xs text-muted">
              <span>Typing rhythm just before the playhead</span>
              <span className="text-faint">one bar per key, pauses muted</span>
            </div>
            <RhythmBars intervals={rhythm} slots={56} className="h-10" />
          </div>
          <Nearby review={review} t={t} onSeek={(v) => { setPlaying(false); setT(v); }} />
        </Card>

        {/* moments */}
        <motion.div variants={stagger(0.08, 0.2)} initial="initial" animate="animate" className="grid content-start gap-4">
          {eps.map((ep, i) => (
            <MomentCard key={i} ep={ep} index={i} active={focusEp === i} onHover={setFocusEp}
              onJump={() => { setPlaying(false); setT(Math.max(0, ep.switch_est - 15)); }} />
          ))}
          {s.phase === "assessed" && review.baseline.status === "ready" && <Guide eps={eps} />}
          <ChannelsExplained review={review} />
        </motion.div>
      </div>
    </motion.div>
  );
}

function Verdict({ review }: { review: Review }) {
  const n = review.episodes.length;
  const s = review.session;
  let tone = "border-border bg-surface", icon = <HeartHandshake className="size-5 text-success" />, title: string, body: string;
  if (review.baseline.status !== "ready") {
    title = "Not scored yet";
    body = s.context === "competition"
      ? `Competitions are timed, so they are compared only with this student's other competitions, never with normal labs. ${review.baseline.n_sessions} of the ${review.baseline.needed} sessions needed so far.`
      : `This student has ${review.baseline.n_sessions} of the ${review.baseline.needed} baseline sessions needed. Until then there is nothing to compare with.`;
    icon = <HeartHandshake className="size-5 text-muted" />;
  } else if (s.phase === "baseline") {
    title = n ? `Baseline week: ${n} moment${n > 1 ? "s" : ""} shown for checking the baseline only` : "Baseline week: steady";
    body = "This session is part of the student's own reference weeks. It is checked against their other baseline sessions to see how much they naturally vary, not to judge them.";
    icon = <HeartHandshake className="size-5 text-muted" />;
  } else if (n === 0) {
    title = "Nothing stood out";
    body = "Typing rhythm and way of working stayed within this student's usual range for the whole session.";
  } else {
    tone = "border-warn/35 bg-warn-soft";
    icon = <MessageCircleQuestion className="size-5 text-warn" />;
    title = `${n} moment${n > 1 ? "s" : ""} worth a conversation`;
    body = "Part of this session looks different from how this student usually writes code. That is a reason to talk with them, never evidence of misconduct on its own: habits change with tiredness, a hard problem, a new keyboard or an injury.";
  }
  return (
    <div className={cn("flex items-start gap-3 rounded-2xl border px-4 py-3.5", tone)}>
      <motion.span variants={pop} initial="initial" animate="animate" className="mt-0.5">{icon}</motion.span>
      <div>
        <p className="text-[15px] font-semibold text-text">{title}</p>
        <p className="mt-0.5 max-w-4xl text-sm leading-relaxed text-muted">{body}</p>
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
      {CHANNELS.map((ch) => <ChannelTag key={ch} channel={ch} />)}
      <span className="inline-flex items-center gap-1.5"><span className="inline-block h-3 w-4 rounded-sm border border-warn/60 bg-[repeating-linear-gradient(45deg,var(--warn-soft),var(--warn-soft)_2px,transparent_2px,transparent_4px)]" />moment to discuss</span>
      <span className="inline-flex items-center gap-1.5"><span className="inline-block size-2.5 rotate-45 rounded-[2px] bg-warn" />paste</span>
      <span className="inline-flex items-center gap-1.5"><span className="inline-block size-2.5 rounded-full bg-success" />run ok</span>
      <span className="inline-flex items-center gap-1.5"><span className="inline-block size-2.5 rounded-full bg-danger" />run error</span>
    </div>
  );
}

function MomentCard({ ep, index, active, onHover, onJump }: { ep: Episode; index: number; active: boolean; onHover: (i: number | null) => void; onJump: () => void }) {
  return (
    <Card variants={item} onPointerEnter={() => onHover(index)} onPointerLeave={() => onHover(null)}
      className={cn("p-4 transition-[box-shadow,border-color] duration-200", active && "border-warn/60 shadow-lg")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-faint">Moment {index + 1}</p>
          <p className="mt-1 text-[15px] font-semibold text-text">
            {CH_CHANGED[ep.channel]} from about {clock(ep.switch_est)}
          </p>
          <p className="mt-0.5 text-sm text-muted">
            Noticed at {clock(ep.first_alarm)}{ep.n_alarms > 1 ? `, and still different at ${clock(ep.last_alarm)}` : ""}.
          </p>
        </div>
        <ChannelTag channel={ep.channel} className="mt-0.5 shrink-0 rounded-full border border-border px-2 py-1" />
      </div>
      {ep.evidence.length > 0 && (
        <div className="mt-3 grid gap-2 rounded-xl bg-surface-2/70 p-3">
          <p className="text-xs font-medium text-muted">What moved most, compared with this student's own baseline</p>
          {ep.evidence.map((ev, k) => <EvidenceRow key={ev.feature} ev={ev} k={k} color={CH_COLOR[ep.channel]} />)}
        </div>
      )}
      <Button size="sm" variant="secondary" className="mt-3" onClick={onJump}>
        <RunIcon className="size-3.5" /> Replay from {clock(Math.max(0, ep.switch_est - 15))}
      </Button>
    </Card>
  );
}

function EvidenceRow({ ev, k, color }: { ev: Episode["evidence"][number]; k: number; color: string }) {
  const z = Math.max(-6, Math.min(6, ev.z));
  const w = (Math.abs(z) / 6) * 50;
  return (
    <div className="grid grid-cols-[1fr_7rem] items-center gap-3 text-[13px]">
      <div>
        <p className="text-text">{ev.label}</p>
        <p className="font-mono text-[11.5px] text-muted">usual {value(ev.baseline, ev.unit)} → here {value(ev.observed, ev.unit)}</p>
      </div>
      <div className="relative h-2 rounded-full bg-surface-3" title={`${ev.z > 0 ? "+" : ""}${ev.z.toFixed(1)} × the student's usual spread`}>
        <span className="absolute inset-y-[-3px] left-1/2 w-px bg-border-strong" />
        <motion.span className="absolute inset-y-0 rounded-full" style={{ background: color, [z >= 0 ? "left" : "right"]: "50%" }}
          initial={{ width: 0 }} animate={{ width: `${w}%` }} transition={{ duration: 0.6, delay: 0.3 + k * 0.07, ease: [0.22, 1, 0.36, 1] }} />
      </div>
    </div>
  );
}

function Guide({ eps }: { eps: Episode[] }) {
  const first = eps[0];
  const qs = first ? [
    `Ask the student to walk you through the code written after ${clock(first.switch_est)}, in their own words.`,
    first.channel !== "process"
      ? "Ask whether anything changed at that point: a break, a different laptop or keyboard, someone sitting with them."
      : "Ask how they worked out that part and where the ideas came from (notes, the web, a friend, an AI tool).",
    "Ask them to make a small change to that code while you watch.",
  ] : [];
  return (
    <Card variants={item} className="overflow-hidden p-4">
      <p className="flex items-center gap-2 text-[15px] font-semibold text-text"><HeartHandshake className="size-4 text-accent" /> {first ? "Starting the conversation" : "No conversation needed"}</p>
      {first ? (
        <ol className="mt-2.5 grid gap-2">
          {qs.map((q, i) => (
            <li key={i} className="flex gap-2.5 text-sm text-muted">
              <span className="grid size-5 shrink-0 place-items-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent">{i + 1}</span>{q}
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-1.5 text-sm text-muted">Nothing in this session differs enough from the student's own baseline to ask about.</p>
      )}
      <p className="mt-3 border-t border-border pt-3 text-xs leading-relaxed text-faint">
        Listen first. Habits shift for ordinary reasons, and a good explanation settles it. Record the outcome of the conversation, not the highlight. No mark or penalty follows from this screen.
      </p>
    </Card>
  );
}

function ChannelsExplained({ review }: { review: Review }) {
  const chans = Object.entries(review.channels);
  if (!chans.length) return null;
  return (
    <Card variants={item} className="p-4">
      <p className="mb-2 text-sm font-semibold text-text">How to read the lanes</p>
      <div className="grid gap-2.5">
        {chans.map(([ch, c]) => (
          <div key={ch} className="flex gap-2.5 text-[13px] text-muted">
            <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: CH_COLOR[ch as keyof typeof CH_COLOR] }} />
            <p><span className="font-medium text-text">{c!.label}.</span> {c!.about}</p>
          </div>
        ))}
        <p className="text-[13px] text-muted">
          The strip shows how far each window sits from the baseline ({windowLengths(review)}). The line adds up sustained differences and
          lets ordinary blips fade; a moment is marked when it crosses the threshold, and its start is the detector's best guess of when the change began.
        </p>
      </div>
    </Card>
  );
}

function windowLengths(review: Review): string {
  const byW = new Map<number, string[]>();
  for (const c of Object.values(review.channels)) byW.set(c!.window_s, [...(byW.get(c!.window_s) ?? []), c!.label.toLowerCase()]);
  if (byW.size <= 1) return `${review.window_s}-second windows`;
  return [...byW].map(([w, names]) => `${w} s for ${names.join(" and ")}`).join("; ");
}

function Nearby({ review, t, onSeek }: { review: Review; t: number; onSeek: (t: number) => void }) {
  const items = useMemo(() => {
    const ev = review.events;
    return [
      ...ev.pastes.map((p) => ({ t: p.t, kind: "paste" as const, text: `Pasted ${p.length} characters (${p.lines} line${p.lines > 1 ? "s" : ""})`, detail: p.preview })),
      ...ev.focus.map((f) => ({ t: f.t, kind: "away" as const, text: `Left the editor for ${clock(f.until - f.t)}`, detail: "" })),
      ...ev.runs.map((r) => ({ t: r.t, kind: r.error_type ? "err" as const : "run" as const, text: r.error_type ? `Ran the code: ${r.error_type}` : "Ran the code: no errors", detail: "" })),
    ].filter((x) => x.t <= t && x.t > t - 120).sort((a, b) => b.t - a.t).slice(0, 4);
  }, [review, t]);
  return (
    <div className="border-t border-border px-4 py-3">
      <p className="mb-2 text-xs font-medium text-muted">In the two minutes before the playhead</p>
      <ul className="grid gap-1.5">
        <AnimatePresence initial={false} mode="popLayout">
          {items.map((x) => (
            <motion.li key={`${x.kind}-${x.t}`} layout initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
              <button onClick={() => onSeek(x.t)} className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1 text-left text-[13px] hover:bg-surface-2">
                <span className={cn("size-2 shrink-0", x.kind === "paste" ? "rotate-45 rounded-[2px] bg-warn" : "rounded-full",
                  x.kind === "away" && "bg-faint", x.kind === "run" && "bg-success", x.kind === "err" && "bg-danger")} />
                <span className="font-mono text-xs tabular-nums text-faint">{clock(x.t)}</span>
                <span className="text-text">{x.text}</span>
                {x.detail && <span className="truncate font-mono text-xs text-faint">{x.detail.split("\n")[0]}</span>}
              </button>
            </motion.li>
          ))}
        </AnimatePresence>
        {items.length === 0 && <li className="px-2 py-1 text-[13px] text-faint">No pastes, runs or looks away.</li>}
      </ul>
    </div>
  );
}

function Loading() {
  return (
    <div className="mx-auto max-w-[1440px] px-5 pt-14">
      <Skeleton className="mb-3 h-8 w-80" />
      <Skeleton className="mb-6 h-4 w-96" />
      <Skeleton className="mb-5 h-16 w-full rounded-2xl" />
      <Skeleton className="h-[380px] w-full rounded-2xl" />
    </div>
  );
}
