// The evidence timeline: one lane per detector channel (window score strip +
// accumulated evidence against its threshold), then pastes, looks away, runs
// and typing activity, all on one time axis with a draggable playhead.

import { useEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ease, spring } from "../ui";
import { CHANNELS, type Channel, type Review } from "./api";
import { CH_COLOR } from "./bits";
import { clock } from "./format";

const GUTTER = 128;
const PAD_R = 18;
const AXIS_H = 26;
const STRIP_H = 10;
const CH_H = 92;
const EV_ROW = 18;
const ACT_H = 34;
const GAP = 14;

interface Props {
  review: Review;
  t: number;
  onSeek: (t: number) => void;
  instant: boolean; // playing or dragging: the playhead follows without a spring
  showTruth: boolean;
  focusEpisode: number | null;
  onFocusEpisode: (i: number | null) => void;
}

export function Timeline({ review, t, onSeek, instant, showTruth, focusEpisode, onFocusEpisode }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  const [hover, setHover] = useState<number | null>(null);
  const [drag, setDrag] = useState(false);

  useEffect(() => {
    const el = wrap.current!;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(480, e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const dur = Math.max(review.session.duration_s, 1);
  const plotW = width - GUTTER - PAD_R;
  const x = (s: number) => GUTTER + (Math.min(Math.max(s, 0), dur) / dur) * plotW;
  const toT = (px: number) => Math.min(dur, Math.max(0, ((px - GUTTER) / plotW) * dur));

  const chans = CHANNELS.filter((c) => review.channels[c]);
  const chTop = (i: number) => AXIS_H + i * (CH_H + STRIP_H + GAP);
  const evTop = AXIS_H + chans.length * (CH_H + STRIP_H + GAP);
  const actTop = evTop + 3 * EV_ROW + GAP;
  const height = actTop + ACT_H + 8;
  const win = review.windows;

  const ticks = useMemo(() => {
    const step = [60, 120, 300, 600, 900].find((s) => dur / s <= 10) ?? 1200;
    return Array.from({ length: Math.floor(dur / step) + 1 }, (_, i) => i * step);
  }, [dur]);

  const pointer = (e: RPointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    return e.clientX - r.left;
  };
  const hoverIdx = hover === null ? null : Math.min(win.length - 1, Math.max(0, Math.floor(hover / review.window_s)));

  return (
    <div ref={wrap} className="relative select-none">
      <svg width={width} height={height} className="block touch-none"
        onPointerDown={(e) => { const px = pointer(e); if (px < GUTTER) return; e.currentTarget.setPointerCapture(e.pointerId); setDrag(true); onSeek(toT(px)); }}
        onPointerMove={(e) => { const px = pointer(e); setHover(px >= GUTTER ? toT(px) : null); if (drag) onSeek(toT(px)); }}
        onPointerUp={() => setDrag(false)}
        onPointerLeave={() => setHover(null)}
        role="img" aria-label="Evidence timeline">
        <defs>
          <clipPath id="tl-wipe">
            <motion.rect x={GUTTER} y={0} height={height} initial={{ width: 0 }} animate={{ width: plotW + 2 }} transition={{ duration: 1.1, ease: ease.out, delay: 0.15 }} />
          </clipPath>
          <pattern id="tl-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--warn)" strokeOpacity="0.35" strokeWidth="2" />
          </pattern>
        </defs>

        {/* axis */}
        {ticks.map((s) => (
          <g key={s}>
            <line x1={x(s)} x2={x(s)} y1={AXIS_H - 6} y2={height - 6} stroke="var(--border)" strokeWidth={1} />
            <text x={x(s)} y={AXIS_H - 11} textAnchor="middle" className="fill-faint font-mono text-[10.5px]">{clock(s)}</text>
          </g>
        ))}

        {/* channel lanes */}
        {chans.map((ch, i) => (
          <ChannelLane key={ch} ch={ch} review={review} top={chTop(i)} x={x} plotW={plotW}
            focusEpisode={focusEpisode} onFocusEpisode={onFocusEpisode} />
        ))}
        {chans.length === 0 && (
          <text x={GUTTER + plotW / 2} y={AXIS_H + 40} textAnchor="middle" className="fill-muted text-[13px]">
            No detector lanes: this student needs {review.baseline.needed} baseline sessions first ({review.baseline.n_sessions} so far).
          </text>
        )}

        {/* evidence events */}
        <g clipPath="url(#tl-wipe)">
          {review.events.focus.map((f, i) => (
            <rect key={i} x={x(f.t)} y={evTop + EV_ROW + 5} width={Math.max(3, x(f.until) - x(f.t))} height={EV_ROW - 10} rx={3} fill="var(--text-faint)" fillOpacity={0.55} />
          ))}
          {review.events.pastes.map((p, i) => (
            <rect key={i} x={x(p.t) - 5} y={evTop + EV_ROW / 2 - 5} width={10} height={10} rx={2} transform={`rotate(45 ${x(p.t)} ${evTop + EV_ROW / 2})`}
              fill="var(--warn)" stroke="var(--surface)" strokeWidth={2} />
          ))}
          {review.events.runs.map((r, i) => (
            <circle key={i} cx={x(r.t)} cy={evTop + 2.5 * EV_ROW} r={4.5} fill={r.error_type ? "var(--danger)" : "var(--success)"} stroke="var(--surface)" strokeWidth={2} />
          ))}
          {/* typing activity */}
          {win.map((w, i) => {
            const h = Math.min(1, w.n_keys / 160) * (ACT_H - 4);
            return <rect key={i} x={x(w.start) + 1} y={actTop + ACT_H - h} width={Math.max(1, x(w.end) - x(w.start) - 2)} height={h} rx={2}
              fill={w.active ? "var(--text-faint)" : "var(--border-strong)"} fillOpacity={w.active ? 0.6 : 0.5} />;
          })}
        </g>
        {[["Pastes", 0], ["Looked away", 1], ["Runs", 2]].map(([label, r]) => (
          <text key={label} x={GUTTER - 14} y={evTop + (Number(r) + 0.5) * EV_ROW + 4} textAnchor="end" className="fill-muted text-[11.5px]">{label}</text>
        ))}
        <text x={GUTTER - 14} y={actTop + ACT_H / 2 + 4} textAnchor="end" className="fill-muted text-[11.5px]">Typing</text>
        <line x1={GUTTER} x2={GUTTER + plotW} y1={actTop + ACT_H} y2={actTop + ACT_H} stroke="var(--border-strong)" />

        {/* simulated ground truth (demo data only) */}
        <AnimatePresence>
          {showTruth && review.session.synthetic?.switch_s != null && review.session.synthetic.condition !== "honest" && (
            <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <line x1={x(review.session.synthetic.switch_s)} x2={x(review.session.synthetic.switch_s)} y1={AXIS_H - 4} y2={height - 6}
                stroke="var(--text)" strokeWidth={1.5} strokeDasharray="2 4" />
              <text x={x(review.session.synthetic.switch_s) + 6} y={height - 10} className="fill-text text-[10.5px] font-medium">simulated switch</text>
            </motion.g>
          )}
        </AnimatePresence>

        {/* hover crosshair */}
        {hover !== null && !drag && (
          <line x1={x(hover)} x2={x(hover)} y1={AXIS_H - 4} y2={height - 6} stroke="var(--text-muted)" strokeOpacity={0.45} strokeWidth={1} pointerEvents="none" />
        )}

        {/* playhead */}
        <motion.g initial={false} animate={{ x: x(t) }} transition={instant ? { duration: 0 } : spring} pointerEvents="none">
          <line x1={0} x2={0} y1={AXIS_H - 6} y2={height - 6} stroke="var(--accent)" strokeWidth={2} />
          <rect x={-22} y={2} width={44} height={17} rx={8.5} fill="var(--accent)" />
          <text x={0} y={14} textAnchor="middle" className="fill-accent-fg font-mono text-[10.5px] font-semibold">{clock(t)}</text>
        </motion.g>
      </svg>

      {/* hover tooltip */}
      <AnimatePresence>
        {hover !== null && hoverIdx !== null && !drag && win[hoverIdx] && (
          <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}
            className="pointer-events-none absolute z-10 w-52 rounded-xl border border-border bg-surface p-3 text-xs shadow-lg"
            style={{ left: Math.min(x(hover) + 12, width - 216), top: AXIS_H + 4 }}>
            <p className="mb-2 font-mono text-[11px] text-muted">{clock(win[hoverIdx].start)} – {clock(win[hoverIdx].end)}</p>
            {chans.map((ch) => {
              const c = review.channels[ch]!;
              const v = c.cusum[Math.min(c.cusum.length - 1, Math.floor(hover / c.window_s))];
              return (
                <p key={ch} className="flex items-center justify-between gap-2 py-0.5">
                  <span className="flex items-center gap-1.5 text-text"><span className="size-2 rounded-full" style={{ background: CH_COLOR[ch] }} />{c.label}</span>
                  <span className="font-mono tabular-nums text-text">{v == null ? "–" : `${Math.round((100 * v) / c.h)}%`}</span>
                </p>
              );
            })}
            <p className="mt-1.5 flex justify-between border-t border-border pt-1.5 text-muted">
              <span>Keys typed</span><span className="font-mono tabular-nums">{win[hoverIdx].n_keys}</span>
            </p>
            {!win[hoverIdx].active && <p className="mt-1 text-faint">Too little typing to score this window.</p>}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ChannelLane({ ch, review, top, x, plotW, focusEpisode, onFocusEpisode }: {
  ch: Channel; review: Review; top: number; x: (s: number) => number; plotW: number;
  focusEpisode: number | null; onFocusEpisode: (i: number | null) => void;
}) {
  const c = review.channels[ch]!;
  // this channel's own windows (the process lane uses longer ones than the typing lanes)
  const win = c.start.map((start, i) => ({ start, end: c.end[i] }));
  const norm = c.cusum.map((v) => (v ?? 0) / c.h);
  const yMax = Math.max(1.3, ...norm) * 1.05;
  const base = top + STRIP_H + 4 + CH_H;
  const y = (v: number) => base - (v / yMax) * (CH_H - 6);
  const pts = win.map((w, i) => [x(w.end), y(norm[i])] as const);
  const line = `M${x(0)},${base}` + pts.map(([px, py]) => `L${px},${py}`).join("");
  const area = line + `L${pts.at(-1)?.[0] ?? x(0)},${base}Z`;
  const color = CH_COLOR[ch];

  return (
    <g>
      <circle cx={14} cy={top + 14} r={4} fill={color} />
      <text x={24} y={top + 18} className="fill-text text-[12.5px] font-semibold">{c.label}</text>
      <text x={14} y={top + STRIP_H + 2} dy={20} className="fill-faint text-[10.5px]">window score</text>
      <text x={14} y={top + STRIP_H + 2} dy={34} className="fill-faint text-[10.5px]">accumulated</text>
      <text x={14} y={top + STRIP_H + 2} dy={46} className="fill-faint text-[10.5px]">evidence</text>

      {/* moments to discuss, under the trace */}
      {review.episodes.map((ep, i) => ep.channel === ch && (
        <motion.g key={i} initial={{ opacity: 0, scaleX: 0 }} animate={{ opacity: 1, scaleX: 1 }}
          transition={{ duration: 0.5, delay: 1.0 + i * 0.08, ease: ease.out }} style={{ originX: 0, transformBox: "fill-box" }}
          onPointerEnter={() => onFocusEpisode(i)} onPointerLeave={() => onFocusEpisode(null)} className="cursor-pointer">
          <rect x={x(ep.switch_est)} y={top} width={Math.max(4, x(ep.last_alarm) - x(ep.switch_est))} height={STRIP_H + 4 + CH_H}
            rx={6} fill="url(#tl-hatch)" opacity={focusEpisode === i ? 1 : 0.7} />
          <rect x={x(ep.switch_est)} y={top} width={Math.max(4, x(ep.last_alarm) - x(ep.switch_est))} height={STRIP_H + 4 + CH_H}
            rx={6} fill="none" stroke="var(--warn)" strokeOpacity={focusEpisode === i ? 0.9 : 0.35} strokeWidth={1.5} />
        </motion.g>
      ))}

      <g clipPath="url(#tl-wipe)">
        {/* per-window score strip: one hue, stronger = further from the student's baseline */}
        {win.map((w, i) => {
          const s = c.score[i];
          const a = s == null ? 0 : Math.min(1, Math.max(0, s) / 4);
          return <rect key={i} x={x(w.start) + 0.5} y={top} width={Math.max(1, x(w.end) - x(w.start) - 1)} height={STRIP_H} rx={2}
            fill={s == null ? "var(--surface-3)" : color} fillOpacity={s == null ? 0.6 : 0.08 + 0.85 * a} />;
        })}
        <path d={area} fill={color} fillOpacity={0.12} />
        <path d={line} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
        {review.episodes.map((ep, i) => ep.channel === ch && (
          <g key={i}>
            <circle cx={x(ep.first_alarm)} cy={y(1)} r={5} fill="var(--warn)" stroke="var(--surface)" strokeWidth={2} />
          </g>
        ))}
      </g>

      <line x1={x(0)} x2={x(0) + plotW} y1={y(1)} y2={y(1)} stroke="var(--text-muted)" strokeDasharray="4 4" strokeOpacity={0.7} />
      <text x={x(0) + 4} y={y(1) - 5} className="fill-muted text-[10.5px]">threshold</text>
      <line x1={x(0)} x2={x(0) + plotW} y1={base} y2={base} stroke="var(--border-strong)" />
    </g>
  );
}
