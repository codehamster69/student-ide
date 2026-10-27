import { useCallback, useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowLeft, Eye, EyeOff, Maximize2, Minimize2, ScanSearch, Trophy, Users } from "lucide-react";
import { Button, Card, LiveDot, Spinner, cn, item, stagger } from "../ui";
import { AuthError, get } from "../review/api";
import { Skeleton } from "../review/bits";
import type { TeacherComp } from "./api";
import { Countdown, Leaderboard, Podium } from "./Leaderboard";

const POLL_MS = 2000;

/**
 * #/teach/c/<lab id>: the board to put on the projector. "Present" goes full
 * screen and hides roll numbers, so only the names students picked show.
 */
export function LiveBoard({ id, onAuthLost }: { id: string; onAuthLost: () => void }) {
  const [c, setC] = useState<TeacherComp | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [present, setPresent] = useState(false);
  const [ids, setIds] = useState(false);

  const load = useCallback(() => get<TeacherComp>(`/api/teach/competitions/${id}`).then((next) => {
    setC(next);
    setOffset(next.now - Date.now() / 1000);
  }, (e) => (e instanceof AuthError ? onAuthLost() : setError(e.message))), [id, onAuthLost]);

  useEffect(() => {
    void load();
    const t = window.setInterval(() => void load(), POLL_MS);
    return () => window.clearInterval(t);
  }, [load]);

  useEffect(() => {
    const on = () => setPresent(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  const togglePresent = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void document.documentElement.requestFullscreen?.().catch(() => setPresent((p) => !p));
  };

  if (!c) {
    return (
      <div className="mx-auto max-w-[1100px] px-5 pt-8">
        {error ? <Card className="p-6 text-sm text-danger">{error}</Card> : <Skeleton className="h-64 w-full rounded-2xl" />}
      </div>
    );
  }

  const ended = c.state === "ended" || c.state === "closed";
  const rows = present ? c.board.map(({ student_id: _, ...r }) => r) : c.board;
  return (
    <motion.div variants={stagger(0.06)} initial="initial" animate="animate"
      className={cn("mx-auto px-5 pb-20 pt-6", present ? "fixed inset-0 z-40 max-w-none overflow-auto bg-bg px-[6vw] pt-[4vh]" : "max-w-[1100px]")}>
      {!present && (
        <motion.a variants={item} href={`#/teach/l/${id}`} className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted hover:text-text">
          <ArrowLeft className="size-4" /> Back to the competition
        </motion.a>
      )}
      <motion.div variants={item} className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-gold">
            <Trophy className="size-3.5" /> Class competition
            {c.state === "live" && <span className="ml-2 inline-flex items-center gap-1.5 text-success"><LiveDot tone="success" /> live</span>}
          </p>
          <h1 className={cn("mt-1 font-semibold tracking-tight text-text", present ? "text-4xl" : "text-2xl")}>{c.title}</h1>
        </div>
        <div className="flex items-center gap-3">
          <Card className="flex items-center gap-3 px-5 py-3 shadow-sm">
            <Countdown comp={c} offset={offset} className={present ? "text-4xl" : "text-2xl"} />
          </Card>
          <span className="flex items-center gap-1.5 text-sm text-muted"><Users className="size-4" />{c.board.length}</span>
          {!present && (
            <Button variant="ghost" size="sm" onClick={() => setIds((v) => !v)} title="Show roll numbers next to board names">
              {ids ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />} Roll numbers
            </Button>
          )}
          <Button size="sm" onClick={togglePresent}>
            {present ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />} {present ? "Exit" : "Present"}
          </Button>
        </div>
      </motion.div>

      {c.handing_in && (
        <motion.div variants={item}>
          <Card className="mb-5 flex items-center gap-3 border-gold/30 px-5 py-3 text-sm text-text">
            <Spinner className="size-4 text-gold" />
            Time is up. Handing in and grading the code each student had open; the final standings follow in a few seconds.
          </Card>
        </motion.div>
      )}
      {ended && !c.handing_in && c.board.length > 0 && (
        <motion.div variants={item}><Card className="mb-5 px-6 pb-6 pt-4"><Podium rows={c.board} /></Card></motion.div>
      )}

      <motion.div variants={item}>
        <Leaderboard rows={rows} nQuestions={c.questions.length} size={present ? "lg" : "md"} showIds={ids && !present}
          showLanguages={c.language === "any"}
          empty={c.state === "draft" || c.state === "waiting" ? "The board fills up once you start the clock." : "No scores yet."} />
      </motion.div>
      {!present && (
        <p className="mt-6 text-center text-xs text-faint">
          The board ranks tests passed and solving speed only. Nothing from the review timeline is ever shown here.
          {" "}<a href={`#/teach/similar/${id}`} className="inline-flex items-center gap-1 text-muted hover:text-text"><ScanSearch className="size-3" />Similar submissions</a>
        </p>
      )}
    </motion.div>
  );
}
