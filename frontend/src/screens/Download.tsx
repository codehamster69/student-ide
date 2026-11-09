// #/download: the public page students get the desktop app from (no sign-in).
// Offers the installer for this computer first, every other system below, and
// the one step an unsigned build needs on first launch. Shareable with a class
// before any Sandbox Lab exists.

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Download as DownloadIcon, Laptop, Monitor, MonitorSmartphone, ShieldAlert, Terminal } from "lucide-react";
import { bestInstaller, detectPlatform, latestRelease, megabytes, type DesktopOs, type Installer, type Release } from "../download";
import { Card, Logo, Spinner, item, stagger } from "../ui";

const OS_NAME: Record<DesktopOs, string> = { windows: "Windows", mac: "macOS", linux: "Linux" };
const OS_ICON = { windows: Monitor, mac: Laptop, linux: Terminal } as const;
const FIRST_RUN: Record<DesktopOs, string> = {
  windows: "Windows may say “Windows protected your PC” the first time. Click More info, then Run anyway.",
  mac: "Open the .dmg and drag Student IDE to Applications. The first time, right-click the app and choose Open, then Open again.",
  linux: "Make the AppImage executable (right-click, Properties, Allow executing, or chmod +x), then double-click it.",
};

export function DownloadPage() {
  const [rel, setRel] = useState<Release | null | undefined>(undefined);
  const [platform, setPlatform] = useState<Awaited<ReturnType<typeof detectPlatform>>>(null);
  useEffect(() => {
    document.title = "Get Student IDE";
    void detectPlatform().then(setPlatform);
    void latestRelease().then(setRel);
  }, []);
  const best = rel ? bestInstaller(rel, platform) : null;
  const others = rel ? rel.installers.filter((i) => i !== best) : [];

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4 py-10">
      <motion.div variants={stagger(0.07)} initial="initial" animate="animate" className="w-full max-w-xl">
        <motion.div variants={item} className="mb-6 flex justify-center"><Logo /></motion.div>
        <Card variants={item} className="p-7 sm:p-8">
          <h1 className="text-2xl font-semibold tracking-tight text-text">Get the Student IDE app</h1>
          <p className="mt-1.5 text-sm text-muted">
            Sandbox Labs run on your own computer in the desktop app. Install it once; it keeps itself up to date
            and signs in with your college Google account.
          </p>

          {rel === undefined && <div className="mt-8 flex justify-center"><Spinner /></div>}
          {rel === null && (
            <p className="mt-6 rounded-lg bg-surface-2 px-4 py-3 text-sm text-muted">
              The app isn't available to download yet. Ask your teacher, or check back later.
            </p>
          )}

          {rel && (
            <>
              {best ? <Primary inst={best} version={rel.version} /> : (
                <p className="mt-6 flex items-center gap-2 rounded-lg bg-surface-2 px-4 py-3 text-sm text-muted">
                  <MonitorSmartphone className="size-4 shrink-0" />
                  {platform ? `There's no build for this computer yet. ` : "Open this page on a laptop or desktop computer to install. "}
                  The builds below are for Windows, macOS and Linux.
                </p>
              )}
              {best && (
                <p className="mt-3 flex gap-2 text-[13px] leading-relaxed text-muted">
                  <ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-warn" /> {FIRST_RUN[best.os]}
                </p>
              )}
              {others.length > 0 && (
                <div className="mt-7 border-t border-border pt-5">
                  <h2 className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">
                    {best ? "Other systems" : "Downloads"}
                  </h2>
                  <ul className="grid grid-cols-[minmax(0,1fr)] gap-1">
                    {others.map((i) => <Row key={i.file} inst={i} />)}
                  </ul>
                </div>
              )}
              <p className="mt-6 text-xs text-muted">
                Version {rel.version}{rel.published_at ? `, released ${new Date(rel.published_at).toLocaleDateString()}` : ""}.
                {" "}Needs about 4 GB free; setup downloads the lab environment on first launch.
              </p>
            </>
          )}
        </Card>
      </motion.div>
    </main>
  );
}

function Primary({ inst, version }: { inst: Installer; version: string }) {
  const Icon = OS_ICON[inst.os];
  return (
    <a href={inst.href} data-testid="primary-download"
      className="mt-6 flex items-center gap-4 rounded-xl bg-accent px-5 py-4 text-accent-fg transition-colors hover:bg-accent-hover">
      <Icon className="size-6 shrink-0" />
      <span className="grid min-w-0 flex-1">
        <span className="text-[15px] font-semibold">Download for {inst.os === "mac" ? inst.label : OS_NAME[inst.os]}</span>
        <span className="truncate text-xs opacity-85">Student IDE {version}{inst.size ? ` · ${megabytes(inst.size)}` : ""}</span>
      </span>
      <DownloadIcon className="size-5 shrink-0" />
    </a>
  );
}

function Row({ inst }: { inst: Installer }) {
  const Icon = OS_ICON[inst.os];
  return (
    <li>
      <a href={inst.href} className="flex items-center gap-3 rounded-lg px-2 py-2 text-sm hover:bg-surface-2">
        <Icon className="size-4 shrink-0 text-muted" />
        <span className="min-w-0 flex-1">
          <span className="font-medium text-text">{inst.label}</span>
          <span className="block truncate text-xs text-muted">{inst.note}</span>
        </span>
        <span className="shrink-0 text-xs text-muted">{megabytes(inst.size)}</span>
        <DownloadIcon className="size-3.5 shrink-0 text-muted" />
      </a>
    </li>
  );
}
