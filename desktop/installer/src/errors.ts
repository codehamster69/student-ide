/**
 * Plain-English setup errors. Every way setup can stop has one code here, with
 * text the app shows as is: what happened, why, and what to do next. Codes are
 * stable so the app, the Lab doctor and IT notes can refer to them.
 */

export type SetupErrorCode =
  | 'UNSUPPORTED_OS'
  | 'OLD_WINDOWS'
  | 'OLD_MACOS'
  | 'VIRTUALIZATION_OFF'
  | 'NEEDS_ADMIN'
  | 'NEEDS_REBOOT'
  | 'LOW_DISK'
  | 'NO_USER_NAMESPACES'
  | 'ENGINE_INSTALL_FAILED'
  | 'ENGINE_NOT_RESPONDING'
  | 'IMAGE_PULL_FAILED'
  | 'CHECK_FAILED';

export interface SetupErrorInfo {
  code: SetupErrorCode;
  /** One line, shown as the heading. */
  title: string;
  /** What happened, in a sentence or two. */
  detail: string;
  /** What the student (or IT) should do. */
  fix: string;
  /** True when someone with admin rights must act; the app shows the IT note. */
  needsAdmin?: boolean;
  /** True when a restart will let setup carry on by itself. */
  needsReboot?: boolean;
  /** Raw tool output for the "Show details" box and bug reports. Never shown first. */
  log?: string;
}

export class SetupError extends Error implements SetupErrorInfo {
  code: SetupErrorCode;
  title: string;
  detail: string;
  fix: string;
  needsAdmin?: boolean;
  needsReboot?: boolean;
  log?: string;

  constructor(info: SetupErrorInfo) {
    super(`${info.title} ${info.detail}`);
    this.name = 'SetupError';
    this.code = info.code;
    this.title = info.title;
    this.detail = info.detail;
    this.fix = info.fix;
    this.needsAdmin = info.needsAdmin;
    this.needsReboot = info.needsReboot;
    this.log = info.log;
  }

  /** Plain object for IPC (Error fields do not survive structured clone). */
  toJSON(): SetupErrorInfo {
    const { code, title, detail, fix, needsAdmin, needsReboot, log } = this;
    return { code, title, detail, fix, needsAdmin, needsReboot, log };
  }
}

const IT_NOTE =
  'Ask your lab staff or IT to run prepare-lab-pc.ps1 (it comes with the Windows download) once on this PC as ' +
  'an administrator, or to approve the prompt for you. After that, every student can finish setup without admin rights.';

export const errors = {
  unsupportedOs: (platform: string) =>
    new SetupError({
      code: 'UNSUPPORTED_OS',
      title: 'This computer is not supported yet.',
      detail: `Sandbox Labs runs on Windows 10/11, macOS 13 or newer, and Linux. This computer reports "${platform}".`,
      fix: 'Use another computer for Sandbox Labs. Your work is saved on the server, so nothing is lost.',
    }),

  oldWindows: (build: number) =>
    new SetupError({
      code: 'OLD_WINDOWS',
      title: 'Windows needs an update first.',
      detail: `Sandbox Labs needs Windows 10 version 2004 (build 19041) or newer. This PC has build ${build}.`,
      fix: 'Run Windows Update, restart, then open Student IDE again.',
    }),

  oldMacos: (version: string) =>
    new SetupError({
      code: 'OLD_MACOS',
      title: 'macOS needs an update first.',
      detail: `Sandbox Labs needs macOS 13 Ventura or newer. This Mac has ${version}.`,
      fix: 'Update macOS in System Settings > General > Software Update, then open Student IDE again.',
    }),

  virtualizationOff: (os: 'win32' | 'darwin' | 'linux') =>
    new SetupError({
      code: 'VIRTUALIZATION_OFF',
      title: 'Virtualization is switched off on this computer.',
      detail:
        'Sandbox Labs runs your lab in a small Linux machine, which needs the processor feature called ' +
        'virtualization (Intel VT-x or AMD-V). Software cannot switch it on; it is a setting in the BIOS/UEFI.',
      fix:
        os === 'win32'
          ? 'Restart, open the BIOS/UEFI setup (usually F2, F10, Del or Esc at the start), turn on ' +
            '"Intel Virtualization Technology", "VT-x", "SVM" or "AMD-V", save and restart. On a lab PC, ask IT: ' +
            'they can do it once for the whole room.'
          : os === 'linux'
            ? 'Turn on VT-x or AMD-V in the BIOS/UEFI. If this is a virtual machine, enable nested virtualization.'
            : 'This Mac cannot run virtual machines. Use another computer for Sandbox Labs.',
      needsAdmin: os !== 'darwin',
    }),

  needsAdmin: (what: string, log?: string, fix = IT_NOTE) =>
    new SetupError({
      code: 'NEEDS_ADMIN',
      title: 'This step needs an administrator, once.',
      detail: `${what} Your account is not allowed to do that, or the permission prompt was closed.`,
      fix,
      needsAdmin: true,
      log,
    }),

  needsReboot: () =>
    new SetupError({
      code: 'NEEDS_REBOOT',
      title: 'Restart to finish setting up.',
      detail: 'Windows turned on the Linux subsystem (WSL2). It starts working after a restart.',
      fix: 'Save your work and restart the PC. Setup carries on by itself when you sign in again.',
      needsReboot: true,
    }),

  lowDisk: (freeGb: number, needGb: number) =>
    new SetupError({
      code: 'LOW_DISK',
      title: 'Not enough free disk space.',
      detail: `Setup needs about ${needGb} GB free for the Linux engine and lab images; there is ${freeGb.toFixed(1)} GB.`,
      fix: 'Free some space (empty the Recycle Bin or Trash, remove large downloads), then try again.',
    }),

  noUserNamespaces: (log?: string) =>
    new SetupError({
      code: 'NO_USER_NAMESPACES',
      title: 'This Linux system blocks rootless containers.',
      detail:
        'Podman could not be installed with your permission, and the system does not allow unprivileged user ' +
        'namespaces, which the no-admin route needs.',
      fix:
        'Ask the administrator to run "sudo apt install podman" (or dnf/zypper/pacman), or to allow user ' +
        'namespaces (sysctl kernel.unprivileged_userns_clone=1, or the AppArmor userns restriction on Ubuntu 24.04).',
      needsAdmin: true,
      log,
    }),

  engineInstallFailed: (step: string, log?: string) =>
    new SetupError({
      code: 'ENGINE_INSTALL_FAILED',
      title: 'The Linux engine could not be set up.',
      detail: `Setup stopped while ${step}.`,
      fix: 'Try again. If it fails twice, open "Show details", copy the text and send it to your teacher.',
      log,
    }),

  engineNotResponding: (log?: string) =>
    new SetupError({
      code: 'ENGINE_NOT_RESPONDING',
      title: 'The Linux engine is installed but not answering.',
      detail: 'Setup finished installing it, but it did not start.',
      fix: 'Restart the computer and open Student IDE again. If it still fails, send "Show details" to your teacher.',
      log,
    }),

  imagePullFailed: (ref: string, log?: string) =>
    new SetupError({
      code: 'IMAGE_PULL_FAILED',
      title: 'A lab could not be downloaded.',
      detail: `Downloading ${ref} failed. This is usually the network.`,
      fix: 'Check that you are online (campus Wi-Fi may block large downloads), then try again.',
      log,
    }),

  checkFailed: (failed: string[], log?: string) =>
    new SetupError({
      code: 'CHECK_FAILED',
      title: 'The final check found a problem.',
      detail: `These checks failed: ${failed.join(', ')}.`,
      fix: 'Try again. If it keeps failing, open the Lab doctor or send "Show details" to your teacher.',
      log,
    }),
};
