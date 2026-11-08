# Desktop installer: no prerequisites

Sandbox Labs need a container engine on the student's PC. Students do not
install Docker first: the Student IDE installer sets up a private engine for
Student IDE alone, pulls the lab images and checks that a lab container
starts. Code: `desktop/installer/` (package `@studentide/installer`), plan:
`thesis/plans/2026-10-30-desktop-client.md` section 3.6.

## What happens on each OS

| OS | Engine | Admin rights | Restart |
| --- | --- | --- | --- |
| Windows 10 2004+ / 11 | Our WSL2 distro `StudentIDE` (Alpine + rootless Podman, ~34 MB compressed), imported per user with `wsl --import` | Once, only when WSL2 is off: one UAC prompt (`wsl --install --no-distribution`; DISM on older inbox WSL) | Once, only when WSL2 was just turned on. Setup registers a RunOnce entry and carries on after sign-in |
| macOS 13+ (Intel, Apple Silicon) | Bundled Lima 1.0.7 starts a Fedora VM (Apple Virtualization framework, 2 CPU, 2 GB, 20 GB disk) with rootless Podman. No host folders are mounted | No | No |
| Linux | Podman already there; else the distro package through one `pkexec` password prompt; else the bundled static Podman 5.3.1 unpacked into the app's data folder | Only for the package route | No |

A Docker or Podman the student already runs is used instead when our engine
cannot be set up for a reason they cannot fix right now (no admin rights,
virtualization off), with a note in the setup window.

The Windows distro never mounts Windows drives and does not add the Windows
PATH (`assets/wsl/wsl.conf`); the Mac VM mounts nothing. The sandbox does not
see the student's own files.

## Steps and progress

`runSetup()` emits progress in four steps, which the setup window shows as
the three animated stages in the plan (check and engine, images, final check):

1. `check`: OS version, free disk (10 GB needed), memory (under 6 GB only warns).
2. `engine`: the per-OS work above. Every sub-step checks first, so running
   setup again (after a reboot or a failure) carries on where it stopped.
3. `images`: pulls the images in `desktop/sandbox/images/images.json` (shipped
   in the app) plus the subject images the web app passes in; images already
   present are skipped, a failed pull is retried once.
4. `verify`: the setup check. Until `desktop/sandbox`'s `setupCheck` is passed
   as `check`, a built-in subset runs (engine answers, volume create/remove,
   `run --rm --network=none <image> true`).

Then `engine.json` is written in the app's userData folder. The app reads it
with `detectEngine()`; `engine.status` pings it with `engineAlive()`.

## Errors

Every stop is a `SetupError` with plain text (`title`, `detail`, `fix`) and
`needsAdmin` / `needsReboot` flags; raw tool output goes in `log` for the
"Show details" box. In the app the code arrives lower-cased (`needs_admin`).

| Code | When | What the student is told |
| --- | --- | --- |
| `VIRTUALIZATION_OFF` | BIOS/UEFI has VT-x/AMD-V off (Windows: firmware flag and hypervisor both false) | How to turn it on, and that IT can do a whole room once |
| `NEEDS_ADMIN` | UAC prompt refused or not an admin; Linux without the `uidmap` helper | Ask IT to run `prepare-lab-pc.ps1` (Windows) or to install Podman (Linux) once |
| `NEEDS_REBOOT` | WSL2 just turned on | Restart; setup resumes by itself |
| `OLD_WINDOWS` / `OLD_MACOS` | Build < 19041 / macOS < 13 | Update the OS |
| `LOW_DISK` | Under 10 GB free | Free space |
| `NO_USER_NAMESPACES` | Linux, no admin route and user namespaces blocked | What the admin can change |
| `ENGINE_INSTALL_FAILED`, `ENGINE_NOT_RESPONDING` | Tool failed | Try again / restart; send details |
| `IMAGE_PULL_FAILED`, `CHECK_FAILED` | Network, or the final check | Check the connection; open the Lab doctor |

## Lab rooms (IT)

`prepare-lab-pc.ps1` (shipped with the Windows build) runs as administrator:
checks virtualization (exit 2 if off in BIOS), turns on WSL2, updates WSL and,
with `-Install StudentIDE-Setup.exe`, installs the app silently for all users
(`/S /allusers`). Exit 3010 means restart to finish. After that, each student's
first launch imports their own distro without admin rights.

## Packaging

`desktop/installer/packaging/electron-builder.yml` packages `desktop/app` with
the engine assets as extraResources under `resources/installer/`:

| OS | Artifacts | Bundled engine files |
| --- | --- | --- |
| Windows | NSIS one-click per-user installer, portable `.exe` | `wsl/studentide-rootfs.tar.gz`, `prepare-lab-pc.ps1` |
| macOS | dmg for arm64 and x64 | `lima/bin/limactl`, the matching guest agent, licence, `studentide.yaml` |
| Linux | AppImage, deb (depends on podman + uidmap) | `podman-static/podman-linux-amd64.tar.gz` |

Electron fuses are set in the same file: RunAsNode, NODE_OPTIONS and inspect
arguments off; embedded ASAR integrity and only-load-from-ASAR on; cookie
encryption on. Uninstalling on Windows unregisters the `StudentIDE` distro
(`packaging/build/installer.nsh`), but not on an update.

Downloads are pinned by version and SHA-256 in `scripts/fetch-assets.sh`;
the WSL root filesystem is built from `assets/wsl/Containerfile` by
`scripts/build-wsl-rootfs.sh`.

CI (`.github/workflows/desktop.yml`): unit tests on Windows, macOS and Linux,
an end-to-end setup on a Linux runner as an ordinary user with Podman removed
(the no-admin static route, pulling a real image), the WSL rootfs build, and
packages for all three OS uploaded as workflow artifacts. Builds are unsigned
for now: Windows code signing and macOS notarization need certificates added
as repository secrets.

## Commands

```bash
cd desktop/installer && npm install && npm test          # unit tests (faked Windows/Mac/Linux)
scripts/fetch-assets.sh linux|mac|win                    # engine assets (win builds the WSL rootfs with Docker)
node dist/cli.js --data-dir /tmp/sid --images images.json  # real setup from a terminal; exit 0 ok, 2 reboot, 3 admin
npm run package -- --linux                               # AppImage + deb into out/ (needs desktop/app installed)
```

## Known limits

- Rootless Podman in the WSL distro and the static Linux route run without
  systemd cgroup delegation, so per-container CPU and memory limits may not
  apply there; the Lima VM and distro-package Podman have them.
- The static Linux route needs either no subuid range for the user or the
  `uidmap` package; otherwise setup asks for an admin once.
- Real Windows and macOS runs have not been done yet: the flows are covered by
  scripted tests, and the WSL distro was checked running rootless containers
  in a Linux VM. The D0 spike on a lab PC is the next check.
