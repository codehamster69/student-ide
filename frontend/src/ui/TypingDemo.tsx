import { useEffect, useState } from "react";
import { useReducedMotion } from "motion/react";
import { RhythmBars } from "./RhythmBars";

const CODE = `def mean(xs):
    total = 0
    for x in xs:
        total += x
    return total / len(xs)`;

const TOKEN = /(\b(?:def|for|in|return)\b)|(\b(?:len|sum)\b)|(\b\d+\b)|(?<=def )(\w+)/g;

function highlight(src: string) {
  const out: (string | JSX.Element)[] = [];
  let last = 0;
  for (const m of src.matchAll(TOKEN)) {
    out.push(src.slice(last, m.index));
    const cls = m[1] ? "text-[var(--syn-keyword)]" : m[2] ? "text-[var(--syn-builtin)]" : m[3] ? "text-[var(--syn-number)]" : "text-[var(--syn-function)]";
    out.push(<span key={m.index} className={cls}>{m[0]}</span>);
    last = m.index! + m[0].length;
  }
  out.push(src.slice(last));
  return out;
}

/** Human-ish gap before typing CODE[i]: slower after line breaks, the odd pause. */
function gapBefore(i: number): number {
  const prev = CODE[i - 1];
  if (prev === "\n") return 380 + Math.random() * 420;
  if (prev === " " && Math.random() < 0.08) return 450 + Math.random() * 300;
  return 55 + Math.random() * 130;
}

/** Self-typing code card with a live keystroke-rhythm strip underneath. */
export function TypingDemo() {
  const reduced = useReducedMotion();
  const [n, setN] = useState(reduced ? CODE.length : 0);
  const [gaps, setGaps] = useState<number[]>([]);

  useEffect(() => {
    if (reduced) return;
    let timer: number;
    let i = 0;
    const step = () => {
      if (i >= CODE.length) {
        timer = window.setTimeout(() => { i = 0; setN(0); setGaps([]); timer = window.setTimeout(step, 600); }, 2600);
        return;
      }
      const g = gapBefore(i);
      // Skip over indentation in one go, like an editor's auto-indent.
      if (CODE[i - 1] === "\n") while (CODE[i] === " ") i++;
      i++;
      setN(i);
      setGaps((p) => [...p.slice(-60), g]);
      timer = window.setTimeout(step, g);
    };
    timer = window.setTimeout(step, 700);
    return () => window.clearTimeout(timer);
  }, [reduced]);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-md">
      <div className="flex items-center gap-1.5 border-b border-border bg-surface-2 px-3 py-2">
        <span className="size-2.5 rounded-full bg-border-strong" />
        <span className="size-2.5 rounded-full bg-border-strong" />
        <span className="size-2.5 rounded-full bg-border-strong" />
        <span className="ml-2 font-mono text-[11px] text-muted">stats.py</span>
      </div>
      <pre className="m-0 h-[132px] px-4 py-3 font-mono text-[12.5px] leading-[1.7] text-text">
        {highlight(CODE.slice(0, n))}
        <span className="ml-px inline-block h-[1.1em] w-[2px] translate-y-[3px] bg-accent animate-blink" />
      </pre>
      <div className="border-t border-border bg-surface-2/60 px-4 pb-3 pt-2.5">
        <div className="mb-2 flex items-center justify-between text-[11px] text-muted">
          <span className="font-medium uppercase tracking-wider">Typing rhythm</span>
          <span className="font-mono">ms between keys</span>
        </div>
        <RhythmBars intervals={gaps} slots={44} maxMs={450} pauseMs={350} />
      </div>
    </div>
  );
}
