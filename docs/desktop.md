# Desktop app (Sandbox Labs shell)

`desktop/app/` is the Scribelab desktop app: an Electron window on the Scribelab
server, plus a bridge to local features (the lab engine, sandboxes, terminals) that the
web app uses when it runs inside the app. Plan: `thesis/plans/2026-10-30-desktop-client.md`.

## How it fits

```
 desktop/app (Electron)                                    Scribelab server
 ┌───────────────────────────────────────────────┐        ┌───────────────────────┐
 │ window: the server's own web app (same origin)│ HTTPS  │ every /api endpoint   │
 │   recorder.ts, editor, labs, live, review…  ──┼───────►│ + desktop.py:         │
 │   window.studentDesktop  (preload bridge)     │        │   /api/desktop/config │
 │        │ IPC "sid:<ns>.<method>"              │        │   /api/auth/desktop/* │
 │ main: modules/app, auth   (this shell)        │        └───────────────────────┘
 │       modules/engine      (@studentide/installer, desktop/installer)
 │       modules/sandbox     (@studentide/sandbox,   desktop/sandbox)
 └───────────────────────────────────────────────┘
```

**The window loads the web app from the server, not a bundled copy.** Every web feature
(labs, sittings, competitions, learning lab, live view, review, attendance, View as student)
therefore works in the app the day it ships on the server, the frontend and API can never be
out of step, and keystrokes are timed by the same recorder in the same Chromium as on the web
(the plan's reason for Electron). The shell itself is versioned and updates itself (below); the
server can refuse old shells (`STUDENTIDE_DESKTOP_MIN_VERSION`). Builds are not code-signed yet
(docs/desktop-installer.md, Signing).

## What the shell does

| | |
|---|---|
| Lock-down | Sandboxed renderer, context isolation, no Node, no `<webview>`. Navigation stays on the server origin; other links open in the system browser. Camera, microphone, screen, location and notification permissions are always refused. Devtools only in unpackaged builds or with `STUDENTIDE_DEVTOOLS=1`. |
| Sign-in | Google mode: through the system browser (below). Dev mode: the roll number / admin token screens work in the window as is. |
| Version gate | Before loading and every 15 minutes, `GET /api/desktop/config`; below `min_version` it shows an update page with `download_url` (at a safe moment, see Updates). Where the app can update itself it downloads the new version on that page and restarts into it, on the page it was on. |
| Updates | `modules/updates.ts` (below). |
| Rename | The product was renamed from Scribelab to Scribelab (2026-11-24). A saved server of `https://studentide.hokora.xyz` is read as the new default `https://scribelab.hokora.xyz`, and the data folder keeps its old name (`Scribelab` under the OS app-data folder), so sign-in, settings and the unsent journal survive the update. Apps from before the rename keep working on the old address: the server's Caddy still serves the desktop user agent and `/api` there. |
| Offline | A local page with retry when the server can't be reached; work is on the server. `app.online` events tell the web app when the network drops (the 5-minute reconnect buffer of plan 4.3 builds on this). |
| Help menu | Student guide, Teacher guide, Keyboard shortcuts (F1) and Sandbox Labs open the server's public guide (`#/help/…`, `frontend/src/guide/`) in a separate window, so a lab session in the main window is never interrupted. |
| Look | The offline and update pages use the same tokens and logo as the web app (`frontend/src/ui/tokens.css`); the window background matches `--bg` so there is no flash on load. |
| Device | A random install id, hashed (`app.info().deviceId`), so analysis can tell devices apart (RQ3) without machine identifiers. The web app records it in `sessions.client_meta.client`. |
| Portable | `--portable` (or the portable .exe) keeps settings and cookies in `StudentIDE-data/` next to the app. `--server=<origin>` / `$STUDENTIDE_SERVER` point it at another server (https, or http on localhost). |

## Browser sign-in (Google mode)

Google blocks sign-in inside embedded browsers, so the app follows RFC 8252 (loopback + PKCE):

1. The app makes a random `verifier`, `challenge = base64url(SHA-256(verifier))` and a `state`,
   and listens on `127.0.0.1:<random port>`.
2. It opens `<server>/#/desktop/signin?challenge&port&state` in the system browser. The page signs
   in as on the web, shows "Sign in to the Scribelab app as <you>?" and on Continue calls
   `POST /api/auth/desktop/grant {challenge}` (needs the browser's session cookie).
3. The browser goes to `http://127.0.0.1:<port>/callback?code&state`.
4. The app calls `POST /api/auth/desktop/exchange {code, verifier}` and stores the returned
   `studentide_session` value in its own cookie jar (HttpOnly). From then on the window is signed in.

Codes live 2 minutes, work once (a failed try burns them) and only with the verifier, which never
leaves the app; only their hashes are stored (`desktop_grants`). The grant needs the SameSite=Lax
session cookie, so another site can't mint codes.

## Bridge contract (`window.studentDesktop`)

Source of truth: `desktop/app/src/shared/contract.ts` and `src/shared/api/<ns>.ts` (types only,
importable by the frontend; `frontend/src/desktop.ts` wraps it). `CONTRACT_VERSION` = 1.

Rules:
- Methods are async, take and return JSON. Main registers them as `<ns>.<method>`; the preload
  builds the object from the list main sends, so adding a method needs no preload change.
- Only the server origin's top-level page gets the bridge; iframes, other sites and the local
  offline page don't, and main checks the sender on every call.
- A failure rejects with a `DesktopError` `{code, title, detail?, fix?, needsAdmin?, needsReboot?}`
  written for students; the web app shows it as is. `not_implemented` means "update the app".
- Events: `studentDesktop.on("<ns>.<event>", cb)` returns an unsubscribe.
- Changing a method's shape bumps `CONTRACT_VERSION`; adding one does not. The web app checks
  `studentDesktop.contract` and that a method exists before using it, so a newer web app keeps
  working in an older shell.

| namespace | owner | methods | events |
|---|---|---|---|
| `app` | shell | `info()`, `openExternal(url)`, `setServer(origin)` | `app.online {online}` |
| `auth` | shell | `signIn() -> {email, role}`, `signOut()` | `auth.changed {signedIn}` |
| `engine` | installer (`desktop/installer`) | `status() -> {state, engine}`, `setup({silent?, images?}) -> EngineInfo` | `engine.progress {step, percent, message}` |
| `sandbox` | sandbox (`desktop/sandbox`) | `setupCheck()`, `openLab(labId)`, `stop`, `reset`, `listFiles`, `readFile`, `writeFile`, `run` | `sandbox.event {sessionKey, type, data}`, `sandbox.progress` |
| `terminal` | sandbox | `open(instanceId, {cwd, cols, rows}) -> {id}`, `write`, `resize`, `close` | `terminal.data {id, data}`, `terminal.exit {id, code}` |
| `updates` | shell (`modules/updates.ts`) | `status() -> UpdateStatus`, `check()`, `restart()`, `setBusy(busy)`, `updateNow()` | `updates.status UpdateStatus` |

All five are implemented: `engine` by `@studentide/installer` (docs/desktop-installer.md),
`sandbox` and `terminal` by `@studentide/sandbox` (docs/sandbox-runtime.md). `updates` is optional
in `DesktopBridge` because apps older than 0.2.0 don't have it.
`sandbox.event` carries schema v2 events from the instance; the renderer's `Recorder` logs them
into the open session (it assigns `seq` and `t`), so a session stays one event stream.

### Adding to a namespace (other threads)

Edit only your two files: `src/shared/api/<ns>.ts` (types) and `src/main/modules/<ns>.ts`
(`ctx.handle("<ns>.<method>", fn)`, `ctx.emit(...)`). A module gets `ctx.server()`,
`ctx.fetch(path)` (already signed in with the app's cookie jar, no bearer token), and
`ctx.userData` (where `engine.json` lives). New namespaces add one line to `modules/index.ts`
and one field to `DesktopBridge` in `contract.ts`.

### `journal` namespace

`journal.append(sessionId, events)`, `journal.close(sessionId)`, `journal.state()`
and the `journal.state` event. The recorder uses it instead of `fetch` when
present: batches go to disk first and are sent signed and hash-chained by the
main process (`desktop/sandbox/src/journal.ts`). The per-install Ed25519 key
is kept with `safeStorage` in `device-key.bin`. Additive: the contract
version stays 2.

## Packaging

The installer thread owns electron-builder config and `.github/workflows/desktop.yml` (NSIS,
dmg, AppImage/deb, plus the portable .exe). Builds must set Electron fuses: `RunAsNode` off,
`EnableNodeOptionsEnvironmentVariable` off, `EnableNodeCliInspectArguments` off,
`EnableEmbeddedAsarIntegrityValidation` and `OnlyLoadAppFromAsar` on.

## Updates

Releases are GitHub releases tagged `desktop-vX.Y.Z` (CI's `release` job builds every OS and uploads
the installers plus electron-builder's feeds `latest.yml` and `latest-linux.yml`). The repository is
private, so the app never talks to GitHub: its updater (electron-updater, generic provider) reads
`<server>/api/desktop/updates/`, and the server (`backend/studentide/desktop_updates.py`) copies the
feed from the newest release and answers installer downloads with a 302 to GitHub's short-lived
signed link, so 150 MB installers never pass through the VM.

Updates are **mandatory** (Rohan, 2026-11-25: no student keeps using an old version). With the
feed on, the server makes the newest release the minimum version (`VersionPolicy` in
`backend/studentide/desktop.py`; `STUDENTIDE_DESKTOP_REQUIRE_LATEST=0` leaves only
`STUDENTIDE_DESKTOP_MIN_VERSION`). If GitHub can't be reached the fixed minimum still holds, so a
GitHub outage never locks students out.

| Build | How it updates |
|---|---|
| Windows, installed (NSIS) | electron-updater: downloads in the background, installs silently and reopens. No admin. |
| Linux AppImage | Same; the AppImage file is replaced. |
| macOS dmg | `modules/macupdate.ts`: Squirrel.Mac refuses unsigned apps, so the app downloads the new .dmg (checked against GitHub's SHA-256 for the asset), quits, and a detached shell mounts it, copies the app beside the old one, swaps them (the old one comes back if the swap fails) and opens it. Needs a bundle the account may replace; a copy run from the disk image or translocated, or in an Applications folder the account can't write, is `manual`. |
| Windows portable, Linux .deb, Mac as above | `manual`: the update page blocks the app and offers the download link and why. |

When it installs, so no work is lost:

1. Checks at start and every 15 minutes; downloads quietly.
2. Never while work is open: the web app reports an open lab, sitting or competition
   (`updates.setBusy`, from the editor layer in `App.tsx`), the journal counts a recorded session as
   open until it is closed (or 10 minutes without a batch), and events still waiting to upload (while
   online) hold it too. A full page load clears the web app's flag; the web app says it again.
3. At the first safe moment after that (no input for 2 minutes, the window hidden or in the
   background, **Update now** on the card, or a 426 from the server) the app shows the update page,
   installs and reopens on the page it was on. On quit the journal flushes (before-quit, up to 10 s)
   and anything left stays on disk and goes up on the next start.
4. While the update waits, the server lets the old version finish open work (events, runs, checks,
   submissions) but answers `POST /api/sessions` and `POST /api/competitions/{id}/join` with
   **426** `{"code": "desktop_update_required", "min_version"}`, and the web app calls
   `updates.updateNow()`. Browsers are never gated.

The web app's card (`screens/DesktopUpdate.tsx`, student home and staff areas, never in the editor)
says "Update required" with **Update now** and can't be closed; a version that is ready but not yet
required gets the old quiet note. Server setting: `STUDENTIDE_UPDATES_REPO` (+
`STUDENTIDE_UPDATES_TOKEN`, a read-only fine-grained token for that repository); unset = updates off
and the app says so quietly.

### Where students download it

Share **`<server>/#/download`** (scribelab.hokora.xyz/#/download). The page needs no sign-in and
lists the newest release from `GET /api/desktop/release` (version, date, one entry per installer with
size and a server link that 302s to GitHub). It offers the installer for the visitor's computer first
(OS from the browser; Mac CPU from `userAgentData` where the browser gives it, otherwise Apple silicon),
the other systems below, and the one first-launch step an unsigned build needs (SmartScreen
"Run anyway", right-click Open on a Mac, `chmod +x` for an AppImage). On a phone it shows the list only.
Students also reach it from the login page ("Get the desktop app") and from the Sandbox Labs banner on
their web home, whose button downloads the right installer directly with "Other systems" next to it.
Before the first release is published the page says the app isn't available yet.

To release: bump nothing by hand, push a tag: `git tag desktop-v0.2.0 && git push origin desktop-v0.2.0`.

## Run it

```bash
cd desktop/app && npm install && npm run build
npx electron . --server=http://127.0.0.1:8000     # against a local backend (dev mode)
npm run smoke                                     # Playwright drives the app against $BASE
```

Server settings: `STUDENTIDE_DESKTOP_MIN_VERSION`, `STUDENTIDE_DESKTOP_REQUIRE_LATEST`, `STUDENTIDE_DESKTOP_DOWNLOAD_URL`, `STUDENTIDE_UPDATES_REPO`,
`STUDENTIDE_UPDATES_TOKEN` (see docs/deploy.md). `STUDENTIDE_UPDATES_DEV=1` lets an unpackaged build try
the updater against a local server.
