import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AllRegisters } from "./Attendance";
import { motion } from "motion/react";
import { Search, ShieldCheck, Undo2, UserPlus } from "lucide-react";
import { Badge, Button, Card, Field, Input, Spinner, cn, item, stagger } from "../ui";
import { AuthError, get, send } from "../review/api";
import { Skeleton } from "../review/bits";
import { dayTime } from "../review/format";

type Role = "student" | "teacher" | "admin";

interface User {
  email: string;
  name: string;
  role: Role;
  role_source: "pattern" | "admin" | "env";
  student_id: string;
  program: string | null;
  year: number | null;
  branch: string | null;
  last_login_at: number | null;
}

const ROLES: Role[] = ["student", "teacher", "admin"];
const TONE: Record<Role, "neutral" | "success" | "warn"> = { student: "neutral", teacher: "success", admin: "warn" };
const SOURCE: Record<User["role_source"], string> = {
  pattern: "from the address", admin: "set by an admin", env: "server setting (STUDENTIDE_ADMINS)",
};

/** #/admin: every account, and the role override for TAs and odd addresses. Admins only. */
export function Users({ me, onAuthLost }: { me: string; onAuthLost: () => void }) {
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [q, setQ] = useState("");
  const [email, setEmail] = useState("");

  const fail = (e: Error) => (e instanceof AuthError ? onAuthLost() : setError(e.message));
  const load = () => get<User[]>("/api/admin/users").then(setUsers).catch(fail);
  useEffect(() => { void load(); }, []);

  const act = async (key: string, run: () => Promise<unknown>) => {
    setBusy(key);
    setError("");
    try { await run(); await load(); } catch (e) { fail(e as Error); }
    setBusy("");
  };
  const setRole = (addr: string, role: Role) =>
    act(addr, () => send("PUT", `/api/admin/users/${encodeURIComponent(addr)}`, { role }));
  const reset = (addr: string) => act(addr, () => send("DELETE", `/api/admin/users/${encodeURIComponent(addr)}/role`));
  const addTeacher = (e: FormEvent) => {
    e.preventDefault();
    void act("new", async () => { await send("PUT", `/api/admin/users/${encodeURIComponent(email.trim())}`, { role: "teacher" }); setEmail(""); });
  };

  const shown = useMemo(() => (users ?? []).filter((u) =>
    !q || u.email.includes(q.toLowerCase()) || u.student_id.toLowerCase().includes(q.toLowerCase()) || u.name.toLowerCase().includes(q.toLowerCase())),
  [users, q]);
  const count = (r: Role) => users?.filter((u) => u.role === r).length ?? 0;

  return (
    <motion.div variants={stagger(0.06)} initial="initial" animate="animate" className="mx-auto max-w-[1100px] px-5 pb-20 pt-8">
      <motion.div variants={item} className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-text">People</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Roles follow the college address: <span className="font-mono text-xs">ug/pg + year + branch + roll</span> is a student,
          any other college address is a teacher. Override a role here for TAs or unusual addresses; it then sticks at every sign-in.
        </p>
      </motion.div>

      <Card variants={item} className="mb-4 p-5">
        <form onSubmit={addTeacher} className="flex flex-wrap items-end gap-3">
          <div className="min-w-72 flex-1">
            <Field label="Add a teacher before their first sign-in">
              <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@iiitsurat.ac.in" type="email" required />
            </Field>
          </div>
          <Button type="submit" variant="primary" disabled={!email.trim() || busy === "new"}>
            {busy === "new" ? <Spinner /> : <UserPlus className="size-4" />} Make teacher
          </Button>
        </form>
      </Card>

      {error && <Card className="mb-4 p-4 text-sm text-danger" role="alert">{error}</Card>}

      <motion.div variants={item} className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-2 text-xs text-muted">
          {ROLES.map((r) => <Badge key={r} tone={TONE[r]}>{count(r)} {r}{count(r) === 1 ? "" : "s"}</Badge>)}
        </div>
        <label className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-faint" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="h-8 w-56 pl-8 text-[13px]" />
        </label>
      </motion.div>

      {!users ? (
        <div className="grid gap-2">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-14 w-full rounded-xl" />)}</div>
      ) : (
        <Card variants={item} className="divide-y divide-border overflow-hidden">
          {shown.length === 0 && <p className="px-5 py-8 text-center text-sm text-muted">Nobody yet. Accounts appear at their first sign-in.</p>}
          {shown.map((u) => (
            <div key={u.email} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
              <div className="min-w-64 flex-1">
                <p className="text-sm font-medium text-text">{u.name || u.email.split("@")[0]}
                  {u.email === me && <span className="ml-2 text-xs font-normal text-faint">you</span>}</p>
                <p className="font-mono text-xs text-muted">{u.email}{u.program && ` · ${u.program} ${u.year} ${u.branch}`}</p>
              </div>
              <p className="w-52 shrink-0 whitespace-nowrap text-xs text-faint">{u.last_login_at ? `last in ${dayTime(u.last_login_at)}` : "not signed in yet"}</p>
              <div className="flex items-center gap-2">
                <select value={u.role} disabled={u.role_source === "env" || busy === u.email}
                  onChange={(e) => void setRole(u.email, e.target.value as Role)}
                  className={cn("h-8 rounded-md border border-border bg-surface px-2 text-[13px] text-text shadow-sm",
                    u.role_source === "env" && "opacity-60")} aria-label={`Role of ${u.email}`}>
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
                <span className="flex w-52 items-center gap-1 text-xs text-faint" title={SOURCE[u.role_source]}>
                  {u.role_source === "env" && <ShieldCheck className="size-3.5" />}
                  {SOURCE[u.role_source]}
                </span>
                {u.role_source === "admin" && (
                  <Button variant="ghost" size="sm" disabled={busy === u.email} onClick={() => void reset(u.email)} title="Follow the address again">
                    <Undo2 className="size-3.5" /> Reset
                  </Button>
                )}
              </div>
            </div>
          ))}
        </Card>
      )}
      <motion.div variants={item} className="mt-6"><AllRegisters onAuthLost={onAuthLost} /></motion.div>
    </motion.div>
  );
}
