import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  AlertTriangle, ArrowLeft, Check, ClipboardCheck, Copy, ExternalLink, KeyRound, Link2, Plus, RefreshCw, Send, Settings2, Unplug, UsersRound, X,
} from "lucide-react";
import { Badge, Button, Card, Checkbox, Dialog, Field, Input, Spinner, cn, item, stagger } from "../ui";
import { AuthError, get, send, token } from "../review/api";
import { Skeleton } from "../review/bits";
import { href } from "../routes";
import type { LabDetail } from "./api";
import {
  dayLabel, openRollCall, splitId, type Connection, type LabClasses, type Preview, type RollCallClass, type Rule, type StudentMark,
} from "./attendanceApi";

function useFail(onAuthLost: () => void, setError: (s: string) => void) {
  return useCallback((e: unknown) => {
    if (e instanceof AuthError) onAuthLost();
    else setError((e as Error).message);
  }, [onAuthLost, setError]);
}

/** Opens Roll Call signed in, making the teacher's key on first use. */
export function OpenRollCall({ onAuthLost, onOpened, label = "Open Roll Call", variant = "secondary", className }: {
  onAuthLost: () => void; onOpened?: () => void; label?: string; variant?: "primary" | "secondary" | "ghost"; className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fail = useFail(onAuthLost, setError);
  return (
    <span className="inline-flex flex-col gap-1">
      <Button size="sm" variant={variant} className={className} disabled={busy} onClick={async () => {
        setBusy(true); setError("");
        try { await openRollCall(() => send<{ url: string }>("POST", "/api/teach/attendance/open")); onOpened?.(); } catch (e) { fail(e); }
        setBusy(false);
      }}>{busy ? <Spinner /> : <ExternalLink className="size-3.5" />} {label}</Button>
      {error && <span className="text-xs text-danger" role="alert">{error}</span>}
    </span>
  );
}

/**
 * Roll Call for this teacher. Student IDE makes their key (their own Roll Call
 * register, seen only by them) and signs them in with one button; a teacher who
 * already keeps a register there can paste that key instead. Used on Getting
 * started and in a lab.
 */
export function ConnectRollCall({ onAuthLost, onChange, compact = false }: {
  onAuthLost: () => void; onChange?: (c: Connection) => void; compact?: boolean;
}) {
  const [conn, setConn] = useState<Connection | null>(null);
  const [key, setKey] = useState("");
  const [pasting, setPasting] = useState(false);
  const [shown, setShown] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [rotated, setRotated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fail = useFail(onAuthLost, setError);
  const update = useCallback((c: Connection) => { setConn(c); onChange?.(c); }, [onChange]);
  const reload = useCallback(() => get<Connection>("/api/teach/attendance").then(update, fail), [update, fail]);
  useEffect(() => { void reload(); }, [reload]);

  if (!conn) return <Skeleton className="h-16 w-full rounded-xl" />;
  if (conn.connected) {
    return (
      <div className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-success/30 bg-success-soft px-3 py-2.5 text-[13px]">
          <Check className="size-4 text-success" />
          <span className="min-w-0 flex-1 text-text">Your Roll Call is ready{conn.issued ? "" : " (your own key)"}</span>
          <OpenRollCall onAuthLost={onAuthLost} variant="primary" />
          {!compact && (
            <Button size="sm" variant="ghost" onClick={async () => {
              if (shown) { setShown(null); return; }
              try { setShown((await get<{ sync_key: string }>("/api/teach/attendance/key")).sync_key); } catch (e) { fail(e); }
            }}><KeyRound className="size-3.5" /> {shown ? "Hide key" : "Show key"}</Button>
          )}
          {!compact && (
            <Button size="sm" variant="ghost" onClick={async () => {
              if (!confirm("Disconnect Roll Call? Your register stays in Roll Call and labs keep their class groups, but attendance can't be sent until you connect again. Keep your key (Show key) if Student IDE made it.")) return;
              try { update(await send<Connection>("DELETE", "/api/teach/attendance")); setShown(null); } catch (e) { fail(e); }
            }}><Unplug className="size-3.5" /> Disconnect</Button>
          )}
        </div>
        {shown && (
          <div className="grid gap-1.5 rounded-xl border border-border bg-surface-2/60 p-3 text-[13px]">
            <div className="flex gap-2">
              <code className="min-w-0 flex-1 truncate rounded-lg border border-border bg-surface px-2.5 py-1.5 font-mono text-xs text-text" aria-label="Your Roll Call key">{shown}</code>
              <Button size="sm" variant="secondary" aria-label="Copy key" onClick={async () => {
                await navigator.clipboard.writeText(shown).catch(() => {});
                setCopied(true); setTimeout(() => setCopied(false), 1500);
              }}>{copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}</Button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="secondary" disabled={busy} onClick={async () => {
                if (!confirm("Make a new key? Your classes, sessions and subjects stay exactly as they are and move to the new key. The old key stops working everywhere, so other devices signed in with it must sign in again (Open Roll Call).")) return;
                setBusy(true); setError("");
                try {
                  update(await send<Connection>("POST", "/api/teach/attendance/key/rotate"));
                  setShown((await get<{ sync_key: string }>("/api/teach/attendance/key")).sync_key);
                  setRotated(true);
                } catch (e) { fail(e); }
                setBusy(false);
              }}>{busy ? <Spinner /> : <RefreshCw className="size-3.5" />} Make a new key</Button>
              {rotated && <span className="text-xs text-success" role="status">New key ready. Your records moved with it; the old key no longer works.</span>}
            </div>
            <p className="text-xs text-muted">
              Your key is your whole register, so keep it private, like a password. If it may have leaked, make a new one: nothing is lost. To sign in by hand on another device, paste it at{" "}
              <a href={`${conn.url}/login`} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">{conn.url.replace(/^https?:\/\//, "")}/login</a>.
              Students never see it: they get their own key, which shows only their marks.
            </p>
          </div>
        )}
        {error && <p className="text-xs text-danger" role="alert">{error}</p>}
      </div>
    );
  }
  return (
    <div className="grid gap-2">
      {!compact && (
        <p className="text-[13px] text-muted">
          Roll Call is the attendance register. Student IDE makes your own key for it, so you see only your classes, and signs you in with one press.
        </p>
      )}
      {!pasting ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="primary" disabled={busy} onClick={async () => {
            setBusy(true); setError("");
            try { update(await send<Connection>("POST", "/api/teach/attendance/key")); } catch (e) { fail(e); }
            setBusy(false);
          }}>{busy ? <Spinner /> : <ClipboardCheck className="size-3.5" />} Set up Roll Call for me</Button>
          <button type="button" className="text-xs font-medium text-muted hover:text-text" onClick={() => setPasting(true)}>
            I already use Roll Call
          </button>
        </div>
      ) : (
        <form className="grid gap-2" onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true); setError("");
          try { update(await send<Connection>("PUT", "/api/teach/attendance", { sync_key: key.trim() })); setKey(""); } catch (err) { fail(err); }
          setBusy(false);
        }}>
          <p className="text-[13px] text-muted">
            Copy your key from <a href={`${conn.url}/settings#student-ide`} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">Roll Call → Settings</a> and paste it here, so labs use the classes you already have.
          </p>
          <div className="flex gap-2">
            <Input value={key} onChange={(e) => setKey(e.target.value)} placeholder="Roll Call sync key" aria-label="Roll Call sync key"
              className="h-9 font-mono text-[13px]" autoComplete="off" spellCheck={false} />
            <Button type="submit" size="sm" variant="primary" className="h-9" disabled={key.trim().length < 32 || busy}>
              {busy ? <Spinner /> : <Link2 className="size-3.5" />} Connect
            </Button>
          </div>
          <button type="button" className="justify-self-start text-xs font-medium text-muted hover:text-text" onClick={() => setPasting(false)}>
            Back: let Student IDE set it up
          </button>
        </form>
      )}
      {error && <p className="text-xs text-danger" role="alert">{error}</p>}
    </div>
  );
}

interface Register { email: string; issued: boolean; connected_at: number; labs: number; last_opened: number | null }

/**
 * Admins: every teacher's Roll Call register, each opened with full access in a
 * new tab (Roll Call shows whose it is; Student IDE logs each open). Renders
 * nothing for teachers.
 */
export function AllRegisters({ onAuthLost }: { onAuthLost: () => void }) {
  const [rows, setRows] = useState<Register[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const fail = useFail(onAuthLost, setError);
  useEffect(() => {
    fetch("/api/teach/attendance/registers", { headers: { "X-Admin-Token": token.get() } })
      .then(async (r) => (r.ok ? setRows(await r.json()) : setRows(null)), () => setRows(null));
  }, []);
  if (!rows) return null;
  return (
    <Card className="p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text"><ClipboardCheck className="size-4 text-accent" /> Teachers' Roll Call registers</h2>
      <p className="mt-1 text-xs text-muted">
        As an admin you can open any teacher's register with full access: Roll Call shows a banner saying whose it is, and each open is logged here.
      </p>
      {rows.length === 0 ? <p className="mt-3 text-[13px] text-muted">No teacher has set up Roll Call yet.</p> : (
        <div className="mt-3 grid gap-1.5">
          {rows.map((r) => (
            <div key={r.email} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-surface-2/60 px-3 py-2 text-[13px]">
              <span className="min-w-0 flex-1 truncate font-medium text-text">{r.email || "Shared (admin token)"}</span>
              <span className="text-xs text-faint">{r.labs} lab{r.labs === 1 ? "" : "s"} with class groups</span>
              <span className="text-xs text-faint">{r.last_opened ? `opened by an admin ${new Date(r.last_opened * 1000).toLocaleDateString()}` : "never opened by an admin"}</span>
              <Button size="sm" variant="secondary" disabled={busy === r.email} aria-label={`Open register of ${r.email}`} onClick={async () => {
                setBusy(r.email); setError("");
                try {
                  await openRollCall(() => send<{ url: string }>("POST", `/api/teach/attendance/registers/${encodeURIComponent(r.email || "-")}/open`));
                  setRows((xs) => xs && xs.map((x) => (x.email === r.email ? { ...x, last_opened: Date.now() / 1000 } : x)));
                } catch (e) { fail(e); }
                setBusy(null);
              }}>{busy === r.email ? <Spinner /> : <ExternalLink className="size-3.5" />} Open register</Button>
            </div>
          ))}
        </div>
      )}
      {error && <p className="mt-2 text-xs text-danger" role="alert">{error}</p>}
    </Card>
  );
}

/**
 * "Which group is performing?" asked when a lab with class groups is opened, and
 * when switching to the next group while it stays open. Only the chosen groups'
 * students can work in the lab meanwhile; the sitting's attendance is sent for
 * them alone when it ends.
 */
export function PerformingDialog({ open, groups, current, switching, onConfirm, onClose }: {
  open: boolean; groups: { class_id: string; label: string; n_students: number }[]; current?: string[];
  switching: boolean; onConfirm: (ids: string[]) => Promise<void>; onClose: () => void;
}) {
  const [picked, setPicked] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setPicked(groups.length === 1 ? [groups[0].class_id] : groups.filter((g) => !current?.includes(g.class_id)).slice(0, 1).map((g) => g.class_id));
  }, [open, groups, current]);
  return (
    <Dialog open={open} onClose={onClose} icon={<UsersRound className="size-5" />}
      title={switching ? "Switch to the next group" : "Which group is performing?"}
      description={<div className="grid gap-3">
        <p>{switching
          ? "The current group's sitting ends and its attendance is sent to Roll Call. Then only the groups you tick can work in the lab."
          : "Only the groups you tick can work in the lab until you close it or switch groups. When it ends, attendance is sent for them alone."}</p>
        <div className="grid gap-1.5">
          {groups.map((g) => (
            <label key={g.class_id} className="flex cursor-pointer items-center gap-2.5 rounded-lg border border-border bg-surface-2/60 px-3 py-2 text-[13px] text-text">
              <Checkbox checked={picked.includes(g.class_id)} aria-label={g.label}
                onChange={(e) => setPicked((p) => (e.target.checked ? [...p, g.class_id] : p.filter((x) => x !== g.class_id)))} />
              <span className="flex-1 font-medium">{g.label}</span>
              <span className="text-xs tabular-nums text-faint">{g.n_students} students</span>
              {current?.includes(g.class_id) && <Badge>now</Badge>}
            </label>
          ))}
        </div>
      </div>}
      actions={<>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" data-autofocus disabled={!picked.length || busy} onClick={async () => {
          setBusy(true); await onConfirm(picked); setBusy(false);
        }}>{busy ? <Spinner /> : null}{switching ? "Switch" : "Open the lab"}</Button>
      </>} />
  );
}

/** While a lab is open for chosen groups: which ones, and a way to move on to the next. */
export function SittingBar({ lab, info, onSwitch }: { lab: LabDetail; info: LabClasses | null; onSwitch: () => void }) {
  if (lab.status !== "open" || !info || !info.classes.length) return null;
  const cur = info.current;
  const who = cur && cur.class_ids.length ? cur.labels.join(", ") : "every attached group";
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-success/30 bg-success-soft px-4 py-2.5 text-[13px]" role="status">
      <span className="size-2 rounded-full bg-success" />
      <span className="min-w-0 flex-1 text-text">
        Open for <span className="font-semibold">{who}</span>
        {cur && <span className="text-muted"> · since {new Date(cur.opened_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
      </span>
      {info.classes.length > 1 && <Button size="sm" onClick={onSwitch}><RefreshCw className="size-3.5" /> Next group</Button>}
    </div>
  );
}

/** Lab sidebar: which Roll Call class groups this lab marks attendance in. */
export function ClassGroupsCard({ lab, onAuthLost, onRosterChanged }: {
  lab: LabDetail; onAuthLost: () => void; onRosterChanged: () => void;
}) {
  const [info, setInfo] = useState<LabClasses | null>(null);
  const [conn, setConn] = useState<Connection | null>(null);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState("");
  const fail = useFail(onAuthLost, setError);
  const load = useCallback(() => get<LabClasses>(`/api/teach/labs/${lab.id}/classes`).then(setInfo, fail), [lab.id, fail]);
  useEffect(() => { void load(); get<Connection>("/api/teach/attendance").then(setConn, fail); }, [load, fail]);

  const save = async (class_ids: string[]) => {
    setError("");
    try {
      setInfo(await send<LabClasses>("PUT", `/api/teach/labs/${lab.id}/classes`, { class_ids, add_to_roster: true }));
      onRosterChanged();
      return true;
    } catch (e) { fail(e); return false; }
  };

  const lastSent = info?.sent[0];
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text"><ClipboardCheck className="size-4 text-accent" /> Class groups and attendance</h2>
        {info && info.classes.length > 0 && (
          <a href={href.labAttendance(lab.id)} className="text-xs font-medium text-accent hover:underline">Attendance</a>
        )}
      </div>
      <p className="mt-1 text-xs text-muted">
        Attach the Roll Call class groups taking this lab. When it closes, each student is marked in their own group.
      </p>
      {!info || !conn ? <Skeleton className="mt-4 h-16 w-full rounded-xl" /> : (
        <>
          {!conn.connected && info.classes.length === 0 ? (
            <div className="mt-4"><ConnectRollCall onAuthLost={onAuthLost} onChange={setConn} compact /></div>
          ) : (
            <div className="mt-4 grid gap-1.5">
              {info.classes.map((c) => (
                <div key={c.class_id} className="flex items-center gap-2 rounded-lg border border-border bg-surface-2/60 px-3 py-2 text-[13px]">
                  <UsersRound className="size-3.5 text-faint" />
                  <span className="flex-1 font-medium text-text">{c.label}</span>
                  <span className="text-xs tabular-nums text-faint">{c.n_students}</span>
                  <button aria-label={`Detach ${c.label}`} title="Detach" className="grid size-5 place-items-center rounded text-faint hover:bg-surface-3 hover:text-text"
                    onClick={() => void save(info.classes.filter((x) => x.class_id !== c.class_id).map((x) => x.class_id))}>
                    <X className="size-3.5" />
                  </button>
                </div>
              ))}
              {info.classes.length === 0 && <p className="text-xs text-faint">No class group attached yet.</p>}
              {conn.connected && !picking && (
                <Button size="sm" className="mt-1 justify-self-start" onClick={() => setPicking(true)}><Plus className="size-3.5" /> Attach class groups</Button>
              )}
            </div>
          )}
          <AnimatePresence>
            {picking && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                <ClassPicker lab={lab} attached={info.classes.map((c) => c.class_id)} onAuthLost={onAuthLost}
                  onCancel={() => setPicking(false)} onSave={async (ids) => { if (await save(ids)) setPicking(false); }} />
              </motion.div>
            )}
          </AnimatePresence>
          {info.classes.length > 0 && (
            <div className="mt-4 grid gap-1 border-t border-border pt-3 text-xs text-muted">
              <span>{info.describe}.</span>
              <span>
                {info.auto_send ? "Sent to Roll Call for the groups performing when you close the lab or move to the next group." : "Sent only when you press Send."}{" "}
                {lastSent && (lastSent.error
                  ? <span className="text-danger">Last send failed: {lastSent.error}</span>
                  : <>Last sent {dayLabel(lastSent.day)}.</>)}
              </span>
              <a href={href.labAttendance(lab.id)} className="mt-1 font-medium text-accent hover:underline">Preview, adjust and send</a>
            </div>
          )}
        </>
      )}
      {error && <p className="mt-2 text-xs text-danger" role="alert">{error}</p>}
    </Card>
  );
}

/** Tick class groups from Roll Call, or make a new one from a roll-number range. */
function ClassPicker({ lab, attached, onSave, onCancel, onAuthLost }: {
  lab: LabDetail; attached: string[]; onSave: (ids: string[]) => Promise<void>; onCancel: () => void; onAuthLost: () => void;
}) {
  const [classes, setClasses] = useState<RollCallClass[] | null>(null);
  const [chosen, setChosen] = useState<string[]>(attached);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const fail = useFail(onAuthLost, setError);
  useEffect(() => { get<RollCallClass[]>("/api/teach/attendance/classes?every=1").then((c) => { setClasses(c); if (!c.length) setCreating(true); }, fail); }, [fail]);
  const onRoster = useMemo(() => new Set(lab.roster), [lab.roster]);

  return (
    <div className="mt-3 grid gap-2 rounded-xl border border-border bg-surface-2/50 p-3">
      {!classes ? <Spinner /> : classes.map((c, i) => {
        const matched = c.students.filter((s) => onRoster.has(s)).length;
        // admins see every teacher's groups, under each teacher's name
        const head = c.owner !== undefined && (i === 0 || classes[i - 1].owner !== c.owner);
        return (
          <div key={c.id} className="contents">
          {head && (
            <p className={cn("px-1.5 text-[11px] font-semibold uppercase tracking-wider text-faint", i > 0 && "mt-2")}>
              {c.owner || "Shared register"}
            </p>
          )}
          <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-1.5 py-1 text-[13px] hover:bg-surface">
            <Checkbox checked={chosen.includes(c.id)} onChange={(e) => setChosen(e.target.checked ? [...chosen, c.id] : chosen.filter((x) => x !== c.id))} />
            <span className="flex-1 font-medium text-text">{c.label}</span>
            <span className="font-mono text-[11px] text-faint">{c.students[0]}{c.students.length > 1 ? `–${c.students[c.students.length - 1].slice(-3)}` : ""}</span>
            <span className="text-xs tabular-nums text-faint" title={`${matched} already on this lab's roster`}>{c.students.length}</span>
          </label>
          </div>
        );
      })}
      {classes && !creating && (
        <button className="justify-self-start text-xs font-medium text-accent hover:underline" onClick={() => setCreating(true)}>+ New class group in Roll Call</button>
      )}
      {creating && (
        <NewClass roster={lab.roster} onAuthLost={onAuthLost} onCancel={classes?.length ? () => setCreating(false) : undefined}
          onCreated={(c) => { setClasses([...(classes ?? []).filter((x) => x.id !== c.id), c]); setChosen([...chosen, c.id]); setCreating(false); }} />
      )}
      {error && <p className="text-xs text-danger" role="alert">{error}</p>}
      <div className="mt-1 flex justify-end gap-2">
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
        <Button size="sm" variant="primary" onClick={() => void onSave(chosen)} disabled={!classes}>Save</Button>
      </div>
      <p className="text-[11px] text-faint">Their students are added to the lab's roster, so they can open it.</p>
    </div>
  );
}

function NewClass({ roster, onCreated, onCancel, onAuthLost }: {
  roster: string[]; onCreated: (c: RollCallClass) => void; onCancel?: () => void; onAuthLost: () => void;
}) {
  // start from the lab's roster when there is one: same prefix, its roll range
  const guess = useMemo(() => {
    const parts = roster.map(splitId).filter((x): x is NonNullable<typeof x> => !!x);
    if (!parts.length) return { prefix: "", start: 1, end: 60, digits: 3 };
    const p = parts[0];
    const same = parts.filter((x) => x.prefix === p.prefix);
    return { prefix: p.prefix, start: Math.min(...same.map((x) => x.roll)), end: Math.max(...same.map((x) => x.roll)), digits: p.digits };
  }, [roster]);
  const [f, setF] = useState({ branch: "", section: "", group: "", prefix: guess.prefix, start: String(guess.start), end: String(guess.end), digits: String(guess.digits) });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fail = useFail(onAuthLost, setError);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const ok = f.branch.trim() && f.section.trim() && /^[A-Za-z0-9/_-]+$/.test(f.prefix) && Number(f.end) >= Number(f.start);
  const first = ok ? `${f.prefix.toUpperCase()}${String(f.start).padStart(Number(f.digits), "0")}` : "";

  return (
    <form className="grid gap-2 rounded-lg border border-border bg-surface p-3" onSubmit={async (e) => {
      e.preventDefault(); setBusy(true); setError("");
      try {
        onCreated(await send<RollCallClass>("POST", "/api/teach/attendance/classes", {
          branch: f.branch, section: f.section, group: f.group,
          groups: [{ prefix: f.prefix, start: Number(f.start), end: Number(f.end), digits: Number(f.digits), exclude: [] }],
        }));
      } catch (err) { fail(err); }
      setBusy(false);
    }}>
      <div className="grid grid-cols-3 gap-2">
        <Field label="Branch"><Input value={f.branch} onChange={set("branch")} placeholder="CSE" className="h-8 text-[13px]" /></Field>
        <Field label="Section"><Input value={f.section} onChange={set("section")} placeholder="A" className="h-8 text-[13px] uppercase" /></Field>
        <Field label="Lab group"><Input value={f.group} onChange={set("group")} placeholder="G1" className="h-8 text-[13px] uppercase" /></Field>
      </div>
      <div className="grid grid-cols-[1.4fr_1fr_1fr_0.8fr] gap-2">
        <Field label="Prefix"><Input value={f.prefix} onChange={set("prefix")} placeholder="UG23CS" className="h-8 font-mono text-[13px] uppercase" /></Field>
        <Field label="From"><Input value={f.start} onChange={set("start")} inputMode="numeric" className="h-8 font-mono text-[13px]" /></Field>
        <Field label="To"><Input value={f.end} onChange={set("end")} inputMode="numeric" className="h-8 font-mono text-[13px]" /></Field>
        <Field label="Digits"><Input value={f.digits} onChange={set("digits")} inputMode="numeric" className="h-8 font-mono text-[13px]" /></Field>
      </div>
      <p className="text-[11px] text-faint">
        Use the part of the college address before the @: {first ? <>the first student is <span className="font-mono text-muted">{first}</span>.</> : "e.g. prefix UG23CS, 3 digits."}
      </p>
      {error && <p className="text-xs text-danger" role="alert">{error}</p>}
      <div className="flex justify-end gap-2">
        {onCancel && <Button size="sm" variant="ghost" type="button" onClick={onCancel}>Cancel</Button>}
        <Button size="sm" type="submit" disabled={!ok || busy}>{busy ? <Spinner /> : <Plus className="size-3.5" />} Create in Roll Call</Button>
      </div>
    </form>
  );
}

/** #/teach/labs/<id>/attendance: who counts as present on a lab day, why, overrides, and sending to Roll Call. */
export function AttendancePage({ lab, onAuthLost }: { lab: LabDetail; onAuthLost: () => void }) {
  const [day, setDay] = useState<string | undefined>();
  const [p, setP] = useState<Preview | null>(null);
  const [overrides, setOverrides] = useState<Record<string, "P" | "A">>({});
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [editRule, setEditRule] = useState(false);
  const fail = useFail(onAuthLost, setError);
  const load = useCallback((d?: string) =>
    get<Preview>(`/api/teach/labs/${lab.id}/attendance${d ? `?day=${d}` : ""}`).then((x) => {
      setP(x);
      setOverrides(Object.fromEntries(x.classes.flatMap((c) => c.students.filter((s) => s.override).map((s) => [s.student_id, s.override!]))));
    }, fail), [lab.id, fail]);
  useEffect(() => { void load(day); }, [load, day]);

  if (!p) return <div className="mx-auto max-w-[1240px] px-5 pt-8">{error ? <Card className="p-6 text-sm text-danger">{error}</Card> : <Skeleton className="h-40 w-full rounded-2xl" />}</div>;

  const mark = (s: StudentMark): boolean => (overrides[s.student_id] ? overrides[s.student_id] === "P" : s.auto);
  const toggle = (s: StudentMark) => {
    const next = mark(s) ? "A" : "P";
    const o = { ...overrides };
    if ((next === "P") === s.auto) delete o[s.student_id]; else o[s.student_id] = next;
    setOverrides(o);
  };
  const idle = (c: Preview["classes"][number]) => c.idle && !c.students.some((s) => overrides[s.student_id]);
  const sentAll = p.classes.some((c) => !idle(c)) && p.classes.every((c) => idle(c) || (c.sent && !c.sent.error));

  return (
    <motion.div variants={stagger(0.05)} initial="initial" animate="animate" className="mx-auto max-w-[1240px] px-5 pb-20 pt-6">
      <motion.a variants={item} href={href.lab(lab.id)} className="mb-4 inline-flex items-center gap-1.5 rounded-md text-sm text-muted transition-colors hover:text-text">
        <ArrowLeft className="size-4" /> {lab.title}
      </motion.a>
      <motion.div variants={item} className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">Attendance</h1>
          <p className="mt-1 text-sm text-muted">{p.describe}. Learning-lab practice and staff previews never count. Tap a mark to change it.</p>
        </div>
        <div className="flex items-center gap-2">
          {p.days.length > 0 && (
            <select value={p.day} onChange={(e) => setDay(e.target.value)} aria-label="Lab day"
              className="h-9 rounded-lg border border-border bg-surface px-2.5 text-[13px] text-text shadow-sm">
              {(p.days.includes(p.day) ? p.days : [p.day, ...p.days]).map((d) => <option key={d} value={d}>{dayLabel(d)}</option>)}
            </select>
          )}
          <Button size="sm" onClick={() => setEditRule(!editRule)}><Settings2 className="size-3.5" /> Rule</Button>
          <Button size="sm" variant="primary" disabled={busy || !p.classes.length} onClick={async () => {
            setBusy(true); setError(""); setNotice("");
            try {
              const r = await send<{ results: { label: string; present: number; total: number; error: string | null; skipped?: boolean }[] }>(
                "POST", `/api/teach/labs/${lab.id}/attendance`, { day: p.day, overrides });
              const bad = r.results.filter((x) => x.error);
              const skipped = r.results.filter((x) => x.skipped);
              setNotice(bad.length ? "" : `Sent: ${r.results.filter((x) => !x.skipped).map((x) => `${x.label} ${x.present}/${x.total}`).join(", ")}.`
                + (skipped.length ? ` Not sent (nobody from the group worked that day): ${skipped.map((x) => x.label).join(", ")}.` : ""));
              if (bad.length) setError(bad.map((x) => `${x.label}: ${x.error}`).join(" "));
              await load(p.day);
            } catch (e) { fail(e); }
            setBusy(false);
          }}>
            {busy ? <Spinner /> : sentAll ? <RefreshCw className="size-3.5" /> : <Send className="size-3.5" />} {sentAll ? "Send again" : "Send to Roll Call"}
          </Button>
        </div>
      </motion.div>

      <AnimatePresence>
        {editRule && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <RuleForm labId={lab.id} rule={p.rule} autoSend={p.auto_send} onAuthLost={onAuthLost}
              onSaved={() => { setEditRule(false); void load(p.day); }} />
          </motion.div>
        )}
      </AnimatePresence>
      {notice && <p className="mb-4 rounded-lg bg-success-soft px-3 py-2 text-sm text-success" role="status">{notice}</p>}
      {error && <p className="mb-4 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">{error}</p>}

      {p.classes.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted">
          No class group is attached to this lab. <a href={href.lab(lab.id)} className="font-medium text-accent hover:underline">Attach one</a> from the lab page.
        </Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          {p.classes.map((c) => {
            const present = c.students.filter(mark).length;
            return (
              <motion.div key={c.class_id} variants={item}>
                <Card className="overflow-hidden">
                  <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3.5">
                    <div>
                      <h2 className="text-sm font-semibold text-text">{c.label}</h2>
                      <p className="text-xs text-muted">
                        {!c.sent && idle(c) ? "Not sent: nobody from this group worked in the lab this day"
                          : c.sent ? (c.sent.error ? <span className="text-danger">Not sent: {c.sent.error}</span>
                          : <>Sent {new Date(c.sent.sent_at * 1000).toLocaleString()}{c.sent.how === "lab closed" ? " when the lab closed" : ""}</>)
                          : "Not sent yet"}
                      </p>
                    </div>
                    <Badge tone={present === c.students.length ? "success" : "neutral"} className="tabular-nums">{present}/{c.students.length} present</Badge>
                  </div>
                  <div className="max-h-[520px] overflow-auto">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-surface-2/95 text-left text-faint backdrop-blur">
                        <tr><th className="px-5 py-2 font-semibold">Student</th><th className="px-2 py-2 font-semibold">Mark</th><th className="px-5 py-2 font-semibold">Why</th></tr>
                      </thead>
                      <tbody>
                        {c.students.map((s) => {
                          const m = mark(s);
                          const changed = m !== s.auto;
                          return (
                            <tr key={s.student_id} className="border-t border-border/70">
                              <td className="px-5 py-1.5 font-mono text-text">{s.student_id}</td>
                              <td className="px-2 py-1.5">
                                <button onClick={() => toggle(s)} title={changed ? "Changed by you; tap to undo" : "Tap to change"}
                                  className={cn("inline-flex h-6 w-9 items-center justify-center rounded-md border font-semibold",
                                    m ? "border-success/40 bg-success-soft text-success" : "border-danger/30 bg-danger-soft text-danger",
                                    changed && "ring-2 ring-accent/40")}>{m ? "P" : "A"}</button>
                              </td>
                              <td className="px-5 py-1.5 text-muted">
                                {changed ? <span className="text-accent">changed by you · </span> : null}{s.reason}
                                {s.pasted > 0 && <span className="text-faint"> · {s.pasted} pasted</span>}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      {p.not_in_any_class.length > 0 && (
        <motion.div variants={item}>
          <Card className="mt-5 border-warn/40 p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-text"><AlertTriangle className="size-4 text-warn" /> Worked in the lab, but in no attached class group</h2>
            <p className="mt-1 text-xs text-muted">
              They won't be marked anywhere. Usually their Roll Call roster uses a different prefix than the college address, or their group isn't attached.
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {p.not_in_any_class.map((s) => (
                <span key={s.student_id} title={s.reason} className="rounded-full border border-border bg-surface-2 px-2.5 py-1 font-mono text-xs text-muted">
                  {s.student_id} <span className={s.present ? "text-success" : "text-faint"}>{s.present ? "would be P" : "A"}</span>
                </span>
              ))}
            </div>
          </Card>
        </motion.div>
      )}
      <p className="mt-5 flex items-center gap-1.5 text-xs text-faint">
        <ExternalLink className="size-3" /> Each class group gets one Roll Call session per lab day. Sending again replaces it, so edits made in Roll Call are overwritten.
      </p>
    </motion.div>
  );
}

function RuleForm({ labId, rule, autoSend, onSaved, onAuthLost }: {
  labId: string; rule: Rule; autoSend: boolean; onSaved: () => void; onAuthLost: () => void;
}) {
  const [f, setF] = useState({ ...rule, auto_send: autoSend });
  const [error, setError] = useState("");
  const fail = useFail(onAuthLost, setError);
  return (
    <Card className="mb-5 grid gap-4 p-5 sm:grid-cols-[1fr_1fr_1.3fr_auto] sm:items-end">
      <Field label="Active minutes" hint="minutes with typing, a run or a Check">
        <Input type="number" min={0} max={600} value={f.min_active_minutes} onChange={(e) => setF({ ...f, min_active_minutes: Number(e.target.value) })} className="h-9" />
      </Field>
      <Field label="Typed characters" hint="pastes don't count">
        <Input type="number" min={0} value={f.min_typed_chars} onChange={(e) => setF({ ...f, min_typed_chars: Number(e.target.value) })} className="h-9" />
      </Field>
      <div className="grid gap-2 text-[13px]">
        <label className="flex items-center gap-2"><Checkbox checked={f.require_run} onChange={(e) => setF({ ...f, require_run: e.target.checked })} /> Must run or check code at least once</label>
        <label className="flex items-center gap-2"><Checkbox checked={f.auto_send} onChange={(e) => setF({ ...f, auto_send: e.target.checked })} /> Send to Roll Call when the lab closes</label>
      </div>
      <Button variant="primary" size="sm" className="h-9" onClick={async () => {
        try { await send("PUT", `/api/teach/labs/${labId}/attendance/rule`, f); onSaved(); } catch (e) { fail(e); }
      }}>Save rule</Button>
      {error && <p className="text-xs text-danger sm:col-span-4" role="alert">{error}</p>}
    </Card>
  );
}
