# Desktop app (Sandbox Labs shell)

`desktop/app/` is the Student IDE desktop app: an Electron window on the Student IDE
server, plus a bridge to local features (the lab engine, sandboxes, terminals) that the
web app uses when it runs inside the app. Plan: `thesis/plans/2026-10-30-desktop-client.md`.

## How it fits

```
 desktop/app (Electron)                                    Student IDE server
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
| Version gate | Before loading, `GET /api/desktop/config`; below `min_version` it shows an update page with `download_url`. Where the app can update itself it downloads the new version on that page and restarts into it. |
| Updates | `modules/updates.ts` (below). |
| Offline | A local page with retry when the server can't be reached; work is on the server. `app.online` events tell the web app when the network drops (the 5-minute reconnect buffer of plan 4.3 builds on this). |
| Device | A random install id, hashed (`app.info().deviceId`), so analysis can tell devices apart (RQ3) without machine identifiers. The web app records it in `sessions.client_meta.client`. |
| Portable | `--portable` (or the portable .exe) keeps settings and cookies in `StudentIDE-data/` next to the app. `--server=<origin>` / `$STUDENTIDE_SERVER` point it at another server (https, or http on localhost). |

## Browser sign-in (Google mode)

Google blocks sign-in inside embedded browsers, so the app follows RFC 8252 (loopback + PKCE):

1. The app makes a random `verifier`, `challenge = base64url(SHA-256(verifier))` and a `state`,
   and listens on `127.0.0.1:<random port>`.
2. It opens `<server>/#/desktop/signin?challenge&port&state` in the system browser. The page signs
   in as on the web, shows "Sign in to the Student IDE app as <you>?" and on Continue calls
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
| `updates` | shell (`modules/updates.ts`) | `status() -> UpdateStatus`, `check()`, `restart()` | `updates.status UpdateStatus` |

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

| Build | How it updates |
|---|---|
| Windows, installed (NSIS) | Downloads in the background, installs when the app closes or on "Restart now". No admin. |
| Linux AppImage | Same; the AppImage file is replaced. |
| macOS dmg | `manual`: Squirrel.Mac only accepts signed apps, so the app shows the new version with a Download link until it is signed. |
| Windows portable, Linux .deb | `manual`: download link (a portable exe has no installer; a .deb belongs to the package manager). |

It never restarts on its own while you work: checks at start and every 4 h, the web app shows a quiet
"ready, installs when you close the app" note outside editor sessions (`screens/DesktopUpdate.tsx`).
The one exception is the version gate: the app can't be used then, so it restarts as soon as the
download is done. Server setting: `STUDENTIDE_UPDATES_REPO` (+ `STUDENTIDE_UPDATES_TOKEN`, a read-only
fine-grained token for that repository); unset = updates off and the app says so quietly.

To release: bump nothing by hand, push a tag: `git tag desktop-v0.2.0 && git push origin desktop-v0.2.0`.

## Run it

```bash
cd desktop/app && npm install && npm run build
npx electron . --server=http://127.0.0.1:8000     # against a local backend (dev mode)
npm run smoke                                     # Playwright drives the app against $BASE
```

Server settings: `STUDENTIDE_DESKTOP_MIN_VERSION`, `STUDENTIDE_DESKTOP_DOWNLOAD_URL`, `STUDENTIDE_UPDATES_REPO`,
`STUDENTIDE_UPDATES_TOKEN` (see docs/deploy.md). `STUDENTIDE_UPDATES_DEV=1` lets an unpackaged build try
the updater against a local server.
