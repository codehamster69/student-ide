/**
 * A small line diff for fs_change events: which lines a save added and
 * removed, and a clipped unified-style text for the review timeline.
 *
 * Plain LCS over lines after trimming the common head and tail, which is
 * where almost every save differs. Above MAX_CELLS the middle is treated as
 * replaced whole: still correct (every new line counts as added), just less
 * precise, and it keeps a pathological file from stalling the app.
 */

const MAX_CELLS = 4_000_000;
export const MAX_DIFF = 8_000;
export const MAX_ADDED = 20_000;

export interface LineDiff {
  /** the new lines, joined with "\n" (clipped to MAX_ADDED) */
  added: string;
  addedLines: number;
  removedLines: number;
  /** "+line" / "-line" / " line" rows around the changes (clipped to MAX_DIFF) */
  diff: string;
  truncated: boolean;
}

export function lineDiff(before: string, after: string): LineDiff {
  const a = lines(before);
  const b = lines(after);
  let head = 0;
  while (head < a.length && head < b.length && a[head] === b[head]) head++;
  let tail = 0;
  while (tail < a.length - head && tail < b.length - head && a[a.length - 1 - tail] === b[b.length - 1 - tail]) tail++;
  const am = a.slice(head, a.length - tail);
  const bm = b.slice(head, b.length - tail);

  const ops: Array<[" " | "+" | "-", string]> = [];
  if (am.length * bm.length <= MAX_CELLS) {
    // LCS table, then walk it forwards
    const n = am.length, m = bm.length;
    const w = m + 1;
    const L = new Uint32Array((n + 1) * w);
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        L[i * w + j] = am[i] === bm[j] ? L[(i + 1) * w + j + 1]! + 1 : Math.max(L[(i + 1) * w + j]!, L[i * w + j + 1]!);
      }
    }
    let i = 0, j = 0;
    while (i < n && j < m) {
      if (am[i] === bm[j]) { ops.push([" ", am[i]!]); i++; j++; }
      else if (L[(i + 1) * w + j]! >= L[i * w + j + 1]!) ops.push(["-", am[i++]!]);
      else ops.push(["+", bm[j++]!]);
    }
    while (i < n) ops.push(["-", am[i++]!]);
    while (j < m) ops.push(["+", bm[j++]!]);
  } else {
    for (const l of am) ops.push(["-", l]);
    for (const l of bm) ops.push(["+", l]);
  }

  const addedRows = ops.filter(([k]) => k === "+").map(([, l]) => l);
  const added = addedRows.join("\n");
  // context: a line before the first change and after the last
  const ctxBefore = head > 0 ? [` ${a[head - 1]}`] : [];
  const ctxAfter = tail > 0 ? [` ${a[a.length - tail]}`] : [];
  const rows = [...ctxBefore, ...ops.map(([k, l]) => k + l), ...ctxAfter];
  let diff = rows.join("\n");
  const truncated = diff.length > MAX_DIFF || added.length > MAX_ADDED;
  if (diff.length > MAX_DIFF) diff = diff.slice(0, MAX_DIFF);
  return {
    added: added.slice(0, MAX_ADDED),
    addedLines: addedRows.length,
    removedLines: ops.filter(([k]) => k === "-").length,
    diff,
    truncated,
  };
}

/** a file's lines; the newline that ends the last line does not start another */
function lines(text: string): string[] {
  if (text === "") return [];
  const l = text.split("\n");
  if (l[l.length - 1] === "") l.pop();
  return l;
}
