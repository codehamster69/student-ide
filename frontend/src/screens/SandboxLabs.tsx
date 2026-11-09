// The student home's "Sandbox labs" section: published Sandbox Labs of the
// student's subjects (GET /api/sandbox/my/labs), one shelf per subject. In the
// desktop app a card opens the lab workspace (SandboxLab.tsx); on the website
// the labs are listed with a note to open them in the Student IDE app, because
// they run in a Linux instance on the student's own machine (docs/sandbox-labs.md).
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowUpRight, Boxes, CalendarClock, Download, Laptop, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { bestInstaller, detectPlatform, DOWNLOAD_PAGE, latestRelease, type Installer } from "../download";
import { desktop } from "../desktop";
import { Badge, Spinner, cn, item, spring, stagger } from "../ui";
import { COLOR_VAR, tint, type Network } from "../sandbox/api";

export interface MyLab {
  id: string; version: number; title: string; description: string; due_at: number | null; assessed: boolean;
  network: Network; min_desktop_version: string | null; n_assignments: number;
  // from the grading side (optional until it is on the server): submitted / all tests passing counts, past due or closed
  submitted?: number; passed_all?: number; closed?: boolean;
}
export interface MySubject { id: string; title: string; code: string; semester: string; color: string; labs: MyLab[] }

/** "0.10.0" >= "0.9.1"; anything unparsable passes (the runtime checks again). */
export function versionAtLeast(have: string, want: string | null): boolean {
  if (!want) return true;
  const a = have.split(".").map(Number), b = want.split(".").map(Number);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = a[i] ?? 0, y = b[i] ?? 0;
    if (Number.isNaN(x) || Number.isNaN(y)) return true;
    if (x !== y) return x > y;
  }
  return true;
}

export const dueText = (due: number | null) => {
  if (!due) return null;
  const d = new Date(due * 1000), days = (due * 1000 - Date.now()) / 86_400_000;
  if (days < 0) return `Was due ${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })}`;
  if (days < 6) return `Due ${d.toLocaleDateString(undefined, { weekday: "short" })} ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
  return `Due ${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })}`;
};

export const NETWORK_LABEL: Record<Network, string> = { open: "Internet on", registries: "Package sites only", off: "No internet" };

export function SandboxLabs({ studentId, onOpen, delay = 0.1 }: {
  studentId: string;
  /** desktop app only: open the lab workspace */
  onOpen: (lab: MyLab, subject: MySubject) => void;
  delay?: number;
}) {
  const [subjects, setSubjects] = useState<MySubject[] | null>(null);
  const [appVersion, setAppVersion] = useState<string | null>(null);
  // the installer for this computer (or the download page when none fits or no release is out)
  const [download, setDownload] = useState<Installer | null>(null);
  const last = (() => { try { return localStorage.getItem("studentide.sandbox.last"); } catch { return null; } })();

  useEffect(() => {
    // dev mode needs ?student_id=; with Google sign-in the server uses the cookie and ignores it
    api<MySubject[]>(`/api/sandbox/my/labs?student_id=${encodeURIComponent(studentId)}`).then(setSubjects, () => setSubjects([]));
    if (desktop) desktop.app.info().then((i) => setAppVersion(i.version), () => {});
    else void Promise.all([latestRelease(), detectPlatform()]).then(([rel, p]) => setDownload(rel && bestInstaller(rel, p)));
  }, [studentId]);

  if (subjects === null) return <div className="mt-8 flex justify-center text-muted"><Spinner /></div>;
  if (!subjects.length) return null;

  return (
    <motion.section variants={stagger(0.06, delay)} initial="initial" animate="animate" className="mt-8" data-testid="sandbox-labs">
      <motion.div variants={item} className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text"><Boxes className="size-4 text-accent" /> Sandbox labs</h2>
          <p className="mt-0.5 max-w-2xl text-[13px] text-muted">
            A full Linux machine per subject, with a terminal, on your own computer. Your files are saved to the server, so they follow you to any machine.
          </p>
        </div>
      </motion.div>

      {!desktop && (
        <motion.div variants={item} className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-accent/30 bg-accent-soft px-4 py-3">
          <Laptop className="size-5 shrink-0 text-accent" />
          <p className="min-w-0 flex-1 text-[13px] text-text">
            <strong className="font-semibold">Open these in the Student IDE app.</strong>{" "}
            <span className="text-muted">Sandbox labs run on your computer, so they need the desktop app; the website only lists them.</span>
          </p>
          <span className="flex flex-wrap items-center gap-3">
            <a href={download?.href ?? DOWNLOAD_PAGE} target={download ? undefined : "_blank"} rel="noreferrer"
              className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-accent px-3 text-[13px] font-medium text-accent-fg hover:bg-accent-hover">
              <Download className="size-3.5" /> {download ? `Get the app for ${download.os === "mac" ? "Mac" : download.os === "windows" ? "Windows" : "Linux"}` : "Get the app"}
            </a>
            {download && <a href={DOWNLOAD_PAGE} target="_blank" rel="noreferrer" className="text-[13px] font-medium text-accent hover:underline">Other systems</a>}
          </span>
        </motion.div>
      )}

      <div className="grid gap-6">
        {subjects.map((s) => (
          <motion.div key={s.id} variants={item}>
            <div className="mb-2 flex items-center gap-2">
              <span className="size-2.5 rounded-full" style={{ backgroundColor: COLOR_VAR[s.color] ?? COLOR_VAR.indigo }} />
              <h3 className="text-[13px] font-semibold text-text">{s.title}</h3>
              {s.code && <span className="font-mono text-[11px] text-faint">{s.code}</span>}
              {s.semester && <span className="text-[11px] text-faint">· {s.semester}</span>}
            </div>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {s.labs.map((lab) => {
                const tooOld = !!appVersion && !versionAtLeast(appVersion, lab.min_desktop_version);
                const can = !!desktop && !tooOld;
                const due = dueText(lab.due_at);
                return (
                  <motion.button
                    key={lab.id}
                    whileHover={can ? { y: -2 } : undefined} whileTap={can ? { scale: 0.99 } : undefined} transition={spring}
                    onClick={() => can && onOpen(lab, s)}
                    disabled={!can}
                    title={!desktop ? "Open this lab in the Student IDE app" : tooOld ? `Update the app to ${lab.min_desktop_version} or later to open this lab` : "Open the lab"}
                    className={cn("group relative flex flex-col gap-2 overflow-clip rounded-xl border border-border bg-surface p-4 text-left shadow-sm transition-[border-color,box-shadow] duration-200",
                      can ? "hover:border-accent/40 hover:shadow-md" : "cursor-default")}
                  >
                    <span className="absolute inset-y-0 left-0 w-1" style={{ backgroundColor: COLOR_VAR[s.color] ?? COLOR_VAR.indigo }} />
                    <span className="flex items-start gap-3">
                      <span className="grid size-8 shrink-0 place-items-center rounded-lg" style={tint(s.color)}><Boxes className="size-4" /></span>
                      <span className="min-w-0 flex-1">
                        <strong className="block text-sm font-semibold text-text">{lab.title}</strong>
                        {lab.description && <span className="line-clamp-2 text-[13px] text-muted">{lab.description}</span>}
                      </span>
                      {can && <ArrowUpRight className="size-4 shrink-0 text-faint transition-[transform,color] duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent" />}
                    </span>
                    <span className="flex flex-wrap items-center gap-1.5 pl-11">
                      <Badge>{lab.n_assignments} assignment{lab.n_assignments === 1 ? "" : "s"}</Badge>
                      <Badge tone={lab.network === "open" ? "neutral" : "accent"}>{NETWORK_LABEL[lab.network]}</Badge>
                      {lab.assessed && <Badge tone="warn"><ShieldCheck className="size-3" /> Assessed</Badge>}
                      {lab.submitted != null && lab.n_assignments > 0 && (
                        <Badge tone={lab.passed_all === lab.n_assignments ? "success" : lab.submitted ? "accent" : "neutral"}>
                          {lab.submitted} of {lab.n_assignments} submitted
                        </Badge>
                      )}
                      {lab.closed && <Badge>Closed: open to look, not to submit</Badge>}
                      {desktop && lab.id === last && <Badge tone="accent">Last opened</Badge>}
                      {due && <span className="inline-flex items-center gap-1 text-[11px] text-faint"><CalendarClock className="size-3" />{due}</span>}
                      {tooOld && <Badge tone="danger">Update the app to open</Badge>}
                      {!desktop && <span className="text-[11px] text-faint">Open in the app</span>}
                    </span>
                  </motion.button>
                );
              })}
            </div>
          </motion.div>
        ))}
      </div>
    </motion.section>
  );
}
