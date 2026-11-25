import { useCallback, useEffect, useState } from "react";
import { Eye, EyeOff, Maximize2, Minimize2, ScanSearch, Trophy, Users } from "lucide-react";
import { Button, Card, LiveDot, Page, Spinner, cn } from "../ui";
import { AuthError, get } from "../review/api";
import { Skeleton } from "../review/bits";
import type { TeacherComp } from "./api";
import { Countdown, Leaderboard, Podium } from "./Leaderboard";
import { href } from "../routes";

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
      <Page>
        {error ? <Card className="p-6 text-sm text-danger">{error}</Card> : <Skeleton className="h-64 w-full rounded-xl" />}
      </Page>
    );
  }

  const ended = c.state === "ended" || c.state === "closed";
  const rows = present ? c.board.map(({ student_id: _, ...r }) => r) : c.board;
  return (
    <div className={cn("mx-auto w-full pb-20", present ? "fixed inset-0 z-40 max-w-none overflow-auto bg-bg px-[6vw] pt-[4vh]" : "max-w-[1120px] px-4 pt-6 sm:px-6 sm:pt-8")}>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-xs font-medium text-gold">
            <Trophy className="size-3.5" /> Class competition
            {c.state === "live" && <span className="ml-2 inline-flex items-center gap-1.5 text-success"><LiveDot tone="success" /> live</span>}
          </p>
          <h1 className={cn("mt-1 font-semibold tracking-[-0.015em] text-text", present ? "text-4xl" : "text-[22px] leading-tight")}>{c.title}</h1>
        </div>
        <div className="flex items-center gap-3">
          <Card className="flex items-center gap-3 px-4 py-2.5">
            <Countdown comp={c} offset={offset} className={present ? "text-4xl" : "text-xl"} />
          </Card>
          <span className="flex items-center gap-1.5 text-sm tabular-nums text-muted"><Users className="size-4" />{c.board.length}</span>
          {!present && (
            <Button variant="ghost" size="sm" onClick={() => setIds((v) => !v)} title="Show roll numbers next to board names">
              {ids ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />} Roll numbers
            </Button>
          )}
          <Button size="sm" onClick={togglePresent}>
            {present ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />} {present ? "Exit" : "Present"}
          </Button>
        </div>
      </div>

      {c.handing_in && (
        <Card className="mb-5 flex items-center gap-3 border-gold/30 px-5 py-3 text-sm text-text">
          <Spinner className="size-4 text-gold" />
          Time is up. Handing in and grading the code each student had open; the final standings follow in a few seconds.
        </Card>
      )}
      {ended && !c.handing_in && c.board.length > 0 && (
        <Card className="mb-5 px-6 pb-6 pt-4"><Podium rows={c.board} /></Card>
      )}

      <div>
        <Leaderboard rows={rows} nQuestions={c.questions.length} size={present ? "lg" : "md"} showIds={ids && !present}
          showLanguages={c.language === "any"}
          empty={c.state === "draft" || c.state === "waiting" ? "The board fills up once you start the clock." : "No scores yet."} />
      </div>
      {!present && (
        <p className="mt-6 text-center text-xs text-faint">
          The board ranks tests passed and solving speed only. Nothing from the review timeline is ever shown here.
          {" "}<a href={href.similar(id)} className="inline-flex items-center gap-1 text-muted hover:text-text"><ScanSearch className="size-3" />Similar submissions</a>
        </p>
      )}
    </div>
  );
}
