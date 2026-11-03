import { useEffect, useState } from "react";
import { CalendarCheck } from "lucide-react";
import { Button, Spinner } from "../ui";
import { openRollCall } from "../teach/attendanceApi";

/**
 * "My attendance": opens Roll Call's read-only page of this student's own marks,
 * signed in with their own student key (never a teacher's). Shown only when one
 * of their labs records attendance in Roll Call.
 */
export function MyAttendanceButton({ studentId }: { studentId: string }) {
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = `/api/attendance/${encodeURIComponent(studentId)}`;

  useEffect(() => {
    fetch(path).then((r) => (r.ok ? r.json() : { enabled: false })).then((j) => setEnabled(!!j.enabled), () => setEnabled(false));
  }, [path]);

  if (!enabled) return null;
  return (
    <span className="relative">
      <Button variant="ghost" size="sm" disabled={busy} title="Your own attendance, read-only, in Roll Call" onClick={async () => {
        setBusy(true); setError("");
        try {
          await openRollCall(async () => {
            const r = await fetch(`${path}/open`, { method: "POST" });
            const j = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(j.detail ?? `error ${r.status}`);
            return j as { url: string };
          });
        } catch (e) { setError((e as Error).message); }
        setBusy(false);
      }}>
        {busy ? <Spinner /> : <CalendarCheck className="size-3.5" />}
        <span className="hidden sm:inline">My attendance</span>
      </Button>
      {error && <span role="alert" className="absolute right-0 top-full mt-1 w-56 rounded-lg border border-border bg-surface p-2 text-xs text-danger shadow-md">{error}</span>}
    </span>
  );
}
