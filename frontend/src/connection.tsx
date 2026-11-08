// Connection state of the desktop app's event journal (desktop/app shared/api/journal.ts),
// for the Sandbox Lab screen: a calm "Reconnecting…" pill while the server cannot be
// reached, and read-only after the 5-minute buffer. In a browser there is no journal,
// so useConnection() is always online and the pill never shows.

import { useEffect, useState } from "react";
import { desktop } from "./desktop";
import type { JournalState } from "../../desktop/app/src/shared/contract";
import { Badge, Spinner } from "./ui";

const ONLINE: JournalState = { online: true, offlineSince: null, readOnly: false, pending: 0, remainingMs: null };

/** Live journal state; `readOnly` means: stop taking input in the editor and terminal. */
export function useConnection(): JournalState {
  const [s, set] = useState<JournalState>(ONLINE);
  useEffect(() => {
    const j = desktop?.journal;
    if (!j || !desktop) return;
    let alive = true;
    void j.state().then((x) => alive && set(x)).catch(() => {});
    const off = desktop.on("journal.state", (x) => set(x));
    // remainingMs counts down between state changes
    const t = window.setInterval(() => void j.state().then((x) => alive && set(x)).catch(() => {}), 5000);
    return () => { alive = false; off(); window.clearInterval(t); };
  }, []);
  return s;
}

const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** Nothing while online. Offline: what is happening, that nothing is lost, and what comes next. */
export function ConnectionPill({ state }: { state: JournalState }) {
  if (state.online) return null;
  if (state.readOnly) {
    return (
      <Badge tone="danger" className="h-auto py-1">
        <Spinner className="size-3" />
        Offline since {state.offlineSince ? clock(state.offlineSince) : "a while"}. Your work is saved on this computer;
        editing resumes when the connection is back.
      </Badge>
    );
  }
  const min = Math.max(1, Math.ceil((state.remainingMs ?? 0) / 60_000));
  return (
    <Badge tone="warn" className="h-auto py-1" >
      <Spinner className="size-3" />
      Reconnecting… keep working, everything is saved here ({min} min left before editing pauses)
    </Badge>
  );
}
