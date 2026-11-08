// The "Class" step of a published Sandbox Lab (plan 5.6, 6.3 steps 5-6): the readiness board
// before the lab ("48 of 52 ready", with each problem in one line), then the live class grid.
// Tiles sort by attention (not ready, app never opened, offline) and animate into place as
// students connect; a tile in a session opens the live editor with the terminal mirror.
// Backend: sandbox_live.py. Never study data.

import { useEffect, useState } from "react";
import { LayoutGroup, motion } from "motion/react";
import { CircleAlert, CircleCheck, CircleHelp, Monitor, SquareTerminal } from "lucide-react";
import { Badge, Card, LiveDot, cn } from "../ui";
import { get } from "../review/api";
import { href } from "../routes";

interface Tile {
  student_id: string; readiness: "ready" | "not_ready" | "unknown"; reason: string; online: boolean;
  app_version: string | null; engine: string | null; platform: string | null; seen_at: number | null; in_lab: boolean;
  session_id: string | null; assignment: string | null; last_activity_at: number | null; typing: boolean;
  running: string | null; commands: number; saves: number; outside: number;
}
interface Board { lab: { id: string; title: string; status: string }; ready: number; total: number; online: number; in_lab: number; tiles: Tile[]; now: number }

const ENGINE: Record<string, string> = { docker: "Docker", podman: "Podman", "wsl-podman": "Podman (WSL)", "lima-podman": "Podman (Lima)" };
const OS: Record<string, string> = { win32: "Windows", darwin: "Mac", linux: "Linux" };

export function ClassBoard({ labId }: { labId: string }) {
  const [b, setB] = useState<Board | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let alive = true;
    const load = () => get<Board>(`/api/sandbox/labs/${labId}/class`).then((x) => alive && (setB(x), setErr(""))).catch((e) => alive && setErr(e.message));
    void load();
    const t = window.setInterval(load, 10_000);
    return () => { alive = false; window.clearInterval(t); };
  }, [labId]);

  if (err) return <Card className="p-5 text-sm text-danger">{err}</Card>;
  if (!b) return <Card className="p-5 text-sm text-muted">Loading the class…</Card>;
  const notReady = b.tiles.filter((x) => x.readiness !== "ready");

  return (
    <div className="grid gap-4">
      <Card className="flex flex-wrap items-center gap-x-8 gap-y-3 p-5">
        <div>
          <p className="text-3xl font-semibold tabular-nums tracking-tight text-text">{b.ready}<span className="text-lg text-faint"> of {b.total}</span></p>
          <p className="text-sm text-muted">machines ready for this lab</p>
        </div>
        <div className="flex gap-6 text-sm">
          <p><span className="font-semibold tabular-nums text-text">{b.online}</span> <span className="text-muted">app open now</span></p>
          <p><span className="font-semibold tabular-nums text-text">{b.in_lab}</span> <span className="text-muted">in this lab</span></p>
        </div>
        {notReady.length > 0 && (
          <p className="basis-full text-xs text-muted">
            Not ready: {notReady.slice(0, 6).map((x) => x.student_id).join(", ")}{notReady.length > 6 ? ` and ${notReady.length - 6} more` : ""}.
            Each tile says why, so IT can fix that PC before the lab. Their files follow them to any machine that passes the check.
          </p>
        )}
      </Card>

      <LayoutGroup>
        <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {b.tiles.map((x) => <TileCard key={x.student_id} x={x} now={b.now} />)}
        </div>
      </LayoutGroup>
    </div>
  );
}

function TileCard({ x, now }: { x: Tile; now: number }) {
  const Icon = x.readiness === "ready" ? CircleCheck : x.readiness === "unknown" ? CircleHelp : CircleAlert;
  const tone = x.readiness === "ready" ? "text-success" : x.readiness === "unknown" ? "text-faint" : "text-warn";
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-mono text-sm font-medium text-text"><Icon className={cn("size-4", tone)} />{x.student_id}</span>
        {x.in_lab ? <Badge tone={x.typing ? "success" : "accent"} className="h-5 px-2 text-[11px]"><LiveDot tone={x.typing ? "success" : "accent"} live={x.typing} />{x.typing ? "typing" : "in the lab"}</Badge>
          : x.online ? <Badge className="h-5 px-2 text-[11px]">app open</Badge>
          : x.seen_at ? <span className="text-[11px] text-faint">seen {ago(now, x.seen_at)}</span> : null}
      </div>
      <p className={cn("mt-1 line-clamp-2 text-xs", x.readiness === "ready" ? "text-muted" : "text-text")}>{x.reason}</p>
      {(x.engine || x.platform) && (
        <p className="mt-1 flex items-center gap-1 text-[11px] text-faint"><Monitor className="size-3" />
          {[OS[x.platform ?? ""] ?? x.platform, ENGINE[x.engine ?? ""] ?? x.engine, x.app_version && `app ${x.app_version}`].filter(Boolean).join(" · ")}</p>
      )}
      {x.session_id && (
        <p className="mt-1.5 flex items-center gap-1.5 truncate text-[11px] text-muted">
          <SquareTerminal className="size-3 shrink-0" />
          {x.running ? <span className="truncate font-mono">$ {x.running}</span> : <span className="truncate">{x.assignment ?? "working"}</span>}
          <span className="ml-auto shrink-0 text-faint">{x.commands} cmd · {x.saves} vim saves{x.outside ? ` · ${x.outside} outside` : ""}</span>
        </p>
      )}
    </>
  );
  const cls = cn("block rounded-xl border bg-surface p-3 shadow-sm transition-colors",
    x.readiness === "not_ready" ? "border-warn/40" : "border-border", x.session_id && "hover:border-accent/50 hover:bg-surface-2/60");
  return (
    <motion.div layout transition={{ type: "spring", stiffness: 420, damping: 34 }}>
      {x.session_id ? <a href={href.liveSession(x.session_id)} className={cls} title="Open the live editor and terminal (the student is told)">{body}</a>
        : <div className={cls}>{body}</div>}
    </motion.div>
  );
}

function ago(now: number, t: number): string {
  const s = Math.max(0, now - t);
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}
