import { useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { cn } from "./ui";

/**
 * Where a question's text is loaded from when the app may not store it
 * (LeetCode problems: the server keeps tests and topics, never LeetCode's
 * text). The browser fetches one row of the public dataset and checks it is
 * the right problem before showing it.
 */
export interface LivePrompt {
  url: string;
  field: string;
  match: Record<string, string>;
  credit: string;
}

const cache = new Map<string, Promise<string>>();

function fetchLive(lp: LivePrompt): Promise<string> {
  let p = cache.get(lp.url);
  if (!p) {
    p = fetch(lp.url).then(async (r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const row = (await r.json())?.rows?.[0]?.row ?? {};
      if (!Object.entries(lp.match).every(([k, v]) => row[k] === v)) throw new Error("dataset row moved");
      const text = String(row[lp.field] ?? "").trim();
      if (!text) throw new Error("empty");
      return text;
    });
    p.catch(() => cache.delete(lp.url)); // try again next time
    cache.set(lp.url, p);
  }
  return p;
}

type State = { text: string; status: "own" | "loading" | "live" | "failed" };

/** The teacher's own prompt if there is one, else the live text (if the question has a live source). */
export function useQuestionText(prompt: string, live?: LivePrompt | null): State {
  const own = prompt.trim() !== "" || !live;
  const [s, setS] = useState<State>({ text: prompt, status: own ? "own" : "loading" });
  useEffect(() => {
    if (own) { setS({ text: prompt, status: "own" }); return; }
    let on = true;
    setS({ text: "", status: "loading" });
    fetchLive(live).then((text) => on && setS({ text, status: "live" }), () => on && setS({ text: "", status: "failed" }));
    return () => { on = false; };
  }, [prompt, own, live?.url]); // eslint-disable-line react-hooks/exhaustive-deps
  return s;
}

/** A question's text, as the student reads it. */
export function QuestionText({ prompt, source, className }: {
  prompt: string; source?: { url?: string; live_prompt?: LivePrompt } | null; className?: string;
}) {
  const live = source?.live_prompt;
  const { text, status } = useQuestionText(prompt, live);
  if (status === "own") return <p className={cn("whitespace-pre-line", className)}>{text}</p>;
  return (
    <div className={className}>
      {status === "loading" && (
        <div className="grid gap-2" aria-label="Loading the problem text">
          {[92, 100, 76, 88].map((w) => <span key={w} className="h-3 animate-pulse rounded bg-surface-3" style={{ width: `${w}%` }} />)}
        </div>
      )}
      {status === "live" && <p className="whitespace-pre-line">{text}</p>}
      {status === "failed" && (
        <p>The problem text couldn't be loaded right now.{" "}
          {source?.url && <a href={source.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">Read it on the original site</a>}
        </p>
      )}
      <p className="mt-2 flex flex-wrap items-center gap-1 text-[11px] text-faint">
        {live?.credit}.
        {source?.url && (
          <a href={source.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 hover:text-text">
            Original <ExternalLink className="size-3" />
          </a>
        )}
      </p>
    </div>
  );
}
