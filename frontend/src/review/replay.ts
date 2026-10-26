// Rebuilds the code at any moment from the recorded edits. Offsets are
// UTF-16 code units, which is exactly how JavaScript strings index, so edits
// apply with plain slicing. Checkpoints every CHECK edits keep scrubbing fast.

import type { ReplayData } from "./api";

const CHECK = 200;

export class Replayer {
  private checkpoints: string[];
  readonly times: number[];

  constructor(private data: ReplayData) {
    this.times = data.edits.map((e) => e[0]);
    this.checkpoints = [data.initial];
    let doc = data.initial;
    data.edits.forEach((e, i) => {
      doc = apply(doc, e[1]);
      if ((i + 1) % CHECK === 0) this.checkpoints.push(doc);
    });
  }

  /** Number of edits at or before time t (ms). */
  count(tMs: number): number {
    let lo = 0, hi = this.times.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (this.times[mid] <= tMs) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }

  /** Document after the first n edits. */
  docAt(n: number): string {
    const c = Math.min(Math.floor(n / CHECK), this.checkpoints.length - 1);
    let doc = this.checkpoints[c];
    for (let i = c * CHECK; i < n; i++) doc = apply(doc, this.data.edits[i][1]);
    return doc;
  }

  /** The n-th edit as [t ms, changes, origin]. */
  edit(i: number) {
    return this.data.edits[i];
  }

  /** Key-press intervals (ms) of the last `n` keys before t. */
  intervals(tMs: number, n = 40): number[] {
    const keys = this.data.keys;
    let lo = 0, hi = keys.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (keys[mid] <= tMs) lo = mid + 1;
      else hi = mid;
    }
    const out: number[] = [];
    for (let i = Math.max(1, lo - n); i < lo; i++) out.push(keys[i] - keys[i - 1]);
    return out;
  }
}

function apply(doc: string, changes: [number, number, string][]): string {
  for (let i = changes.length - 1; i >= 0; i--) {
    const [from, to, text] = changes[i];
    doc = doc.slice(0, from) + text + doc.slice(to);
  }
  return doc;
}

/** 1-based line numbers of `after` that are new or changed compared with `before` (LCS on lines). */
export function changedLines(before: string, after: string): Set<number> {
  const a = before.split("\n"), b = after.split("\n");
  const n = a.length, m = b.length;
  const out = new Set<number>();
  if (n * m > 250_000) return out;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  let i = 0, j = 0;
  while (j < m) {
    if (i < n && a[i] === b[j]) { i++; j++; }
    else if (i < n && dp[i + 1][j] >= dp[i][j + 1]) i++;
    else { if (b[j].trim()) out.add(j + 1); j++; }
  }
  return out;
}
