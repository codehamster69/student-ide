export function clock(s: number): string {
  const t = Math.max(0, Math.floor(s));
  const m = Math.floor(t / 60);
  return `${m}:${String(t % 60).padStart(2, "0")}`;
}

export function day(unix: number): string {
  return new Date(unix * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function dayTime(unix: number): string {
  return new Date(unix * 1000).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** A local calendar day as YYYY-MM-DD: one lab session is one lab on one day. */
export function dayKey(unix: number): string {
  const d = new Date(unix * 1000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** When a lab ran: "Tue 27 Oct, 10:02 – 11:40" for one day, else the date range and how many days. */
export function span(start: number, end: number, sittings: number[]): string {
  const d = (u: number) => new Date(u * 1000);
  const time = (u: number) => d(u).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  const days = new Set(sittings.map((u) => d(u).toDateString()));
  if (days.size <= 1 && d(start).toDateString() === d(end).toDateString()) {
    return `${d(start).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}, ${time(start)} – ${time(end)}`;
  }
  const short = (u: number) => d(u).toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return `${short(start)} – ${short(end)} · ${days.size} days`;
}

export function value(v: number, unit: string): string {
  const n = Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2);
  return unit ? `${n} ${unit}`.replace(" %", "%") : n;
}

export const TASKS: Record<string, string> = {
  "warmup-fizzbuzz": "Warm-up: FizzBuzz",
  "word-frequency": "Word frequency",
  free: "Free practice",
};

export const CONDITION: Record<string, string> = {
  honest: "Honest",
  proxy: "Someone else throughout",
  takeover: "Takeover partway",
  copying: "Copying from elsewhere",
  paste: "Pasting code in",
};
