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
