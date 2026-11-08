// Sandbox Lab lanes under the review timeline (backend sandbox_review.py): what happened
// outside our editor. Each lane is a thin track over the whole session; a mark seeks the
// replay there. Things to look at or ask about, never verdicts (same wording rule as the
// moments). Hidden for web sessions, where every lane is empty.

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, FileWarning, Link2Off, Network, Radio, SquareTerminal, WifiOff, FilePen } from "lucide-react";
import { Badge, cn } from "../ui";
import type { SandboxLanes as Lanes } from "./api";
import { clock } from "./format";

type Mark = { t: number; end?: number | null; tone: "accent" | "warn" | "muted"; label: string };

const TONE = { accent: "bg-accent", warn: "bg-warn", muted: "bg-faint" };

function Lane({ icon: Icon, name, note, marks, duration, t, onSeek }: {
  icon: typeof SquareTerminal; name: string; note?: string; marks: Mark[]; duration: number; t: number; onSeek: (s: number) => void;
}) {
  const pct = (s: number) => `${Math.min(100, Math.max(0, (s / Math.max(1, duration)) * 100))}%`;
  return (
    <div className="grid grid-cols-[11rem_1fr] items-center gap-3 py-1">
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 truncate text-xs font-medium text-text"><Icon className="size-3.5 shrink-0 text-muted" />{name}</p>
        {note && <p className="truncate text-[11px] text-faint">{note}</p>}
      </div>
      <div className="relative h-5 rounded-md bg-surface-2">
        {marks.map((m, i) => (
          <button key={i} title={`${clock(m.t)} · ${m.label}`} aria-label={`${m.label} at ${clock(m.t)}`} onClick={() => onSeek(Math.max(0, m.t - 2))}
            className={cn("absolute top-1 h-3 min-w-1 rounded-sm opacity-80 transition-opacity hover:opacity-100", TONE[m.tone])}
            style={{ left: pct(m.t), width: m.end ? `max(4px, calc(${pct(m.end)} - ${pct(m.t)}))` : "4px" }} />
        ))}
        <span className="pointer-events-none absolute inset-y-0 w-px bg-text/60" style={{ left: pct(t) }} />
      </div>
    </div>
  );
}

const ORIGIN = { "terminal-editor": "saved from vim/nano", terminal: "written by a command", outside: "changed outside the app" };

export function SandboxLanes({ lanes, duration, t, onSeek }: { lanes: Lanes; duration: number; t: number; onSeek: (s: number) => void }) {
  const unseenFiles = lanes.unseen.flatMap((s) => s.unseen.map((u) => ({ ...u, reason: s.reason, at: s.created_at })));
  const unexplained = lanes.saves.filter((s) => !s.explained);
  const notable = unexplained.length + lanes.breaks.length + unseenFiles.length + lanes.quiet.length;
  const [open, setOpen] = useState(notable > 0);
  const empty = !lanes.commands.length && !lanes.saves.length && !lanes.terminal_keys && !lanes.signed && !unseenFiles.length;

  const recent = useMemo(() => lanes.commands.filter((c) => c.t <= t).slice(-6), [lanes.commands, t]);
  if (empty) return null;

  const summary = [
    `${lanes.commands.length} command${lanes.commands.length === 1 ? "" : "s"}`,
    `${lanes.saves.filter((s) => s.origin === "terminal-editor").length} vim/nano saves`,
    unexplained.length ? `${unexplained.length} change${unexplained.length === 1 ? "" : "s"} without typing behind ${unexplained.length === 1 ? "it" : "them"}` : null,
    lanes.offline.length ? `offline ${lanes.offline.length}×` : null,
  ].filter(Boolean).join(" · ");

  return (
    <div className="mt-3 border-t border-border pt-2">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 rounded-md px-1 py-1 text-left text-sm text-text hover:bg-surface-2/60">
        <span className="flex items-center gap-2 font-medium"><SquareTerminal className="size-4 text-accent" /> Terminal and files
          <span className="text-xs font-normal text-muted">{summary}</span></span>
        <span className="flex items-center gap-2">
          {notable > 0 && <Badge tone="warn" className="h-5 px-2 text-[11px]">{notable} to look at</Badge>}
          {!lanes.signed && <Badge className="h-5 px-2 text-[11px]">unsigned (older app)</Badge>}
          <ChevronDown className={cn("size-4 text-muted transition-transform", open && "rotate-180")} />
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden px-1">
            <div className="pt-1">
              <Lane icon={SquareTerminal} name="Terminal commands" duration={duration} t={t} onSeek={onSeek}
                marks={lanes.commands.map((c) => ({ t: c.t, end: c.end, tone: c.exit_code && c.exit_code !== 0 ? "warn" : "accent", label: c.command }))}
                note={lanes.quiet.length ? `command logging stopped ${lanes.quiet.length}×` : undefined} />
              <Lane icon={FilePen} name="Saves from the terminal" duration={duration} t={t} onSeek={onSeek}
                note="vim/nano: we see keys and each save, not each edit"
                marks={lanes.saves.filter((s) => s.origin === "terminal-editor").map((s) => ({ t: s.t, tone: s.explained ? "accent" : "warn",
                  label: `${s.path}: +${s.added_lines} −${s.removed_lines}${s.explained ? "" : `, ${s.typed_keys} keys for ${s.added_chars} characters`}` }))} />
              <Lane icon={FileWarning} name="Written another way" duration={duration} t={t} onSeek={onSeek} note="by a command, or outside the app"
                marks={lanes.saves.filter((s) => s.origin !== "terminal-editor").map((s) => ({ t: s.t, tone: s.explained ? "muted" : "warn",
                  label: `${s.path}: ${s.deleted ? "deleted" : ORIGIN[s.origin]}${s.command ? ` (${s.command})` : ""}` }))} />
              {(lanes.ports.length > 0 || lanes.network.length > 0 || lanes.packages.length > 0) && (
                <Lane icon={Network} name="Ports, network, packages" duration={duration} t={t} onSeek={onSeek}
                  marks={[...lanes.ports.map((p) => ({ t: p.t, tone: "muted" as const, label: `${p.process || "a program"} ${p.open ? "listening on" : "stopped on"} ${p.port}` })),
                    ...lanes.network.map((n) => ({ t: n.t, tone: n.allowed ? "muted" as const : "warn" as const, label: `${n.host} ${n.allowed ? "reached" : "refused"}` })),
                    ...lanes.packages.map((p) => ({ t: p.t, tone: "muted" as const, label: `${p.manager} ${p.action} ${p.packages.join(" ")}` }))]} />
              )}
              <Lane icon={WifiOff} name="Offline" duration={duration} t={t} onSeek={onSeek} note="a gap, not a moment"
                marks={lanes.offline.map((o) => ({ t: o.t, end: o.end, tone: "muted", label: `offline for ${o.seconds} s` }))} />
              {lanes.breaks.length > 0 && (
                <Lane icon={Link2Off} name="Record breaks" duration={duration} t={t} onSeek={onSeek} note="events missing or changed in transit"
                  marks={lanes.breaks.filter((b) => b.t !== null).map((b) => ({ t: b.t!, tone: "warn", label: BREAK[b.problem] ?? b.problem }))} />
              )}
            </div>

            <div className="mt-2 grid gap-3 pb-1 lg:grid-cols-2">
              <div className="rounded-lg border border-border bg-surface-2/50 p-2.5">
                <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted"><Radio className="size-3.5" /> Terminal up to {clock(t)}</p>
                {recent.length === 0 ? <p className="text-xs text-faint">No commands yet.</p> : (
                  <ol className="grid gap-1 font-mono text-[12px] leading-snug">
                    {recent.map((c, i) => (
                      <li key={i}>
                        <button onClick={() => onSeek(Math.max(0, c.t - 2))} className="text-left text-text hover:underline">
                          <span className="text-faint">{clock(c.t)} $ </span>{c.command}
                          {c.exit_code !== null && c.exit_code !== 0 && <span className="text-warn"> (exit {c.exit_code})</span>}
                        </button>
                        {c.tail && <pre className="mt-0.5 max-h-16 overflow-hidden whitespace-pre-wrap text-[11px] text-muted">{c.tail.split("\n").slice(-3).join("\n")}</pre>}
                      </li>
                    ))}
                  </ol>
                )}
              </div>
              <div className="rounded-lg border border-border bg-surface-2/50 p-2.5">
                <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted"><FileWarning className="size-3.5" /> Appeared without typing</p>
                {unseenFiles.length === 0 ? (
                  <p className="text-xs text-faint">Everything in the uploaded files was typed, pasted or saved in front of us, or came with the starter files.</p>
                ) : (
                  <ul className="grid gap-1.5 text-xs">
                    {unseenFiles.map((u, i) => (
                      <li key={i}>
                        <p className="text-text"><span className="font-mono">{u.path}</span>: {u.unseen_lines} line{u.unseen_lines === 1 ? "" : "s"} ({Math.round(u.share * 100)}% of the file)
                          {u.reason === "submit" && <Badge className="ml-1.5 h-4 px-1.5 text-[10px]">in the submission</Badge>}</p>
                        <pre className="mt-0.5 overflow-hidden whitespace-pre-wrap font-mono text-[11px] text-muted">{u.examples.join("\n")}</pre>
                      </li>
                    ))}
                    <li className="text-[11px] text-faint">Worth asking how this got there: a download, a file brought from elsewhere or generated by a tool all look like this.</li>
                  </ul>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const BREAK: Record<string, string> = {
  chain_break: "some events never arrived",
  rewritten: "events were sent again with other contents",
  bad_signature: "not signed by this student's app",
  other_device: "sent by another student's app",
};
