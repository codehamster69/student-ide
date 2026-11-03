import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  AlertTriangle, ArrowLeft, Check, ClipboardCheck, ExternalLink, Link2, Plus, RefreshCw, Send, Settings2, Unplug, UsersRound, X,
} from "lucide-react";
import { Badge, Button, Card, Checkbox, Field, Input, Spinner, cn, item, stagger } from "../ui";
import { AuthError, get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { href } from "../routes";
import type { LabDetail } from "./api";
import {
  dayLabel, splitId, type Connection, type LabClasses, type Preview, type RollCallClass, type Rule, type StudentMark,
} from "./attendanceApi";

function useFail(onAuthLost: () => void, setError: (s: string) => void) {
  return useCallback((e: unknown) => {
    if (e instanceof AuthError) onAuthLost();
    else setError((e as Error).message);
  }, [onAuthLost, setError]);
}

/** Paste the Roll Call sync key once; shows the connection afterwards. Used on Getting started and in a lab. */
export function ConnectRollCall({ onAuthLost, onChange, compact = false }: {
  onAuthLost: () => void; onChange?: (c: Connection) => void; compact?: boolean;
}) {
  const [conn, setConn] = useState<Connection | null>(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fail = useFail(onAuthLost, setError);
  const update = useCallback((c: Connection) => { setConn(c); onChange?.(c); }, [onChange]);
  useEffect(() => { get<Connection>("/api/teach/attendance").then(update, fail); }, [update, fail]);

  if (!conn) return <Skeleton className="h-16 w-full rounded-xl" />;
  if (conn.connected) {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-success/30 bg-success-soft px-3 py-2.5 text-[13px]">
        <Check className="size-4 text-success" />
        <span className="flex-1 text-text">Connected to <a href={conn.url} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">Roll Call</a></span>
        <Button size="sm" variant="ghost" onClick={async () => {
          if (!confirm("Disconnect Roll Call? Labs keep their class groups, but attendance can't be sent until you connect again.")) return;
          try { update(await send<Connection>("DELETE", "/api/teach/attendance")); } catch (e) { fail(e); }
        }}><Unplug className="size-3.5" /> Disconnect</Button>
      </div>
    );
  }
  return (
    <form className="grid gap-2" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true); setError("");
      try { update(await send<Connection>("PUT", "/api/teach/attendance", { sync_key: key.trim() })); setKey(""); } catch (err) { fail(err); }
      setBusy(false);
    }}>
      {!compact && (
        <p className="text-[13px] text-muted">
          In <a href={`${conn.url}/settings#student-ide`} target="_blank" rel="noreferrer" className="font-medium text-accent hover:underline">Roll Call → Settings → Connect Student IDE</a>,
          copy your sync key and paste it here. It stays on the server and is never shown to students.
        </p>
      )}
      <div className="flex gap-2">
        <Input value={key} onChange={(e) => setKey(e.target.value)} placeholder="Roll Call sync key" aria-label="Roll Call sync key"
          className="h-9 font-mono text-[13px]" autoComplete="off" spellCheck={false} />
        <Button type="submit" size="sm" variant="primary" className="h-9" disabled={key.trim().length < 32 || busy}>
          {busy ? <Spinner /> : <Link2 className="size-3.5" />} Connect
        </Button>
      </div>
      {error && <p className="text-xs text-danger" role="alert">{error}</p>}
    </form>
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
                {info.auto_send ? "Sent to Roll Call when you close the lab." : "Sent only when you press Send."}{" "}
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
  useEffect(() => { get<RollCallClass[]>("/api/teach/attendance/classes").then((c) => { setClasses(c); if (!c.length) setCreating(true); }, fail); }, [fail]);
  const onRoster = useMemo(() => new Set(lab.roster), [lab.roster]);

  return (
    <div className="mt-3 grid gap-2 rounded-xl border border-border bg-surface-2/50 p-3">
      {!classes ? <Spinner /> : classes.map((c) => {
        const matched = c.students.filter((s) => onRoster.has(s)).length;
        return (
          <label key={c.id} className="flex cursor-pointer items-center gap-2.5 rounded-lg px-1.5 py-1 text-[13px] hover:bg-surface">
            <Checkbox checked={chosen.includes(c.id)} onChange={(e) => setChosen(e.target.checked ? [...chosen, c.id] : chosen.filter((x) => x !== c.id))} />
            <span className="flex-1 font-medium text-text">{c.label}</span>
            <span className="font-mono text-[11px] text-faint">{c.students[0]}{c.students.length > 1 ? `–${c.students[c.students.length - 1].slice(-3)}` : ""}</span>
            <span className="text-xs tabular-nums text-faint" title={`${matched} already on this lab's roster`}>{c.students.length}</span>
          </label>
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
  const sentAll = p.classes.length > 0 && p.classes.every((c) => c.sent && !c.sent.error);

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
              const r = await send<{ results: { label: string; present: number; total: number; error: string | null }[] }>(
                "POST", `/api/teach/labs/${lab.id}/attendance`, { day: p.day, overrides });
              const bad = r.results.filter((x) => x.error);
              setNotice(bad.length ? "" : `Sent: ${r.results.map((x) => `${x.label} ${x.present}/${x.total}`).join(", ")}.`);
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
                        {c.sent ? (c.sent.error ? <span className="text-danger">Not sent: {c.sent.error}</span>
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
