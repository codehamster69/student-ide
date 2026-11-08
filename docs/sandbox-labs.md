# Sandbox Labs: subjects, lab definitions, library and teacher previews

The server side of Sandbox Labs (plan: `thesis/plans/2026-10-30-desktop-client.md`).
Teachers create **subjects** freely, give each an **environment** (a recipe the
build service turns into a Linux image), add **sandbox labs** of
**assignments**, can **share** a lab to the library, and can **Try as a student**
in a capped cloud preview instance. Students always run labs on their own
machine in the desktop app; the cloud instances are for teachers only.

Code: `backend/studentide/sandbox.py` (catalogue, API), `backend/studentide/previews.py`
(cloud preview instances), `backend/studentide/preview_service.py` (the container that
holds the Docker socket), UI in `frontend/src/sandbox/`.

## Lab definition format `studentide.sandbox-lab/1`

This is the contract with the desktop app (`desktop/`, see `docs/desktop.md` from PR #37) and the local sandbox
runtime. The server sends it; clients never construct one. It is additive: a
client ignores fields it does not know, and a breaking change gets a new
`format` value.

```jsonc
{
  "format": "studentide.sandbox-lab/1",
  "id": "slab_3f9a1c2b7d",            // stable lab id
  "version": 4,                        // bumps on every saved change; clients cache by (id, version)
  "title": "Linked lists",
  "description": "Markdown",
  "subject": { "id": "subj_8c1d0e2f4a", "code": "CS201", "title": "Data Structures" },
  "environment": {
    "id": "env_c_ds", "version": 3, "title": "C with gdb and valgrind",
    "image": "ghcr.io/codehamster69/studentide-env:env_c_ds-3",
    "digest": "sha256:…",            // null until built; pull by image@digest when set
    "recipe": { … },                  // see "Recipes" below; enough to build the image locally
    "resources": { "cpus": 2, "memory_mb": 2048, "disk_gb": 10, "pids": 512 }
  },
  "instance": {                        // one instance per (student, subject), kept for the semester
    "name": "sid-{student}-subj_8c1d0e2f4a",   // client fills {student} with the lower-cased roll number
    "volume": "sidv-{student}-subj_8c1d0e2f4a",
    "user": "student", "home": "/home/student"
  },
  "network": "registries",             // "open" | "registries" | "off"; assessed labs are never "open"
  "assessed": true,
  "status": "published",               // "draft" only in teacher previews
  "min_desktop_version": null,         // e.g. "0.3.0": older apps say "Update the app to open this lab"
  "opens_at": null, "due_at": null,    // unix seconds or null
  "grading": {                         // set in the wizard's Publish step (sandbox_authoring.py)
    "mode": "tests",                   // "tests" | "tests_manual" (tests, then the teacher may change the score) | "manual"
    "late": { "mode": "penalty", "per_day_pct": 10, "max_days": 3 },  // "closed" (default) | "accept" | "penalty"
    "late_summary": "Late work loses 10% per day, not accepted after 3 days."
  },
  "assignments": [
    {
      "id": "asg_51d0c9e2aa",
      "position": 0,
      "title": "Insert at head",
      "statement": "Markdown",
      "workdir": "/home/student/labs/slab_3f9a1c2b7d/asg_51d0c9e2aa",
      "files": [                       // starter files, relative to workdir, UTF-8 text
        { "path": "main.c", "content": "…", "executable": false },
        { "path": "Makefile", "content": "…", "executable": false }
      ],
      "open": ["main.c"],              // files the editor opens first
      "run": "make && ./main",         // what the Run button does (in workdir)
      "tests": {
        "kind": "io",                  // "io": stdin/expected pairs fed to `run`; "command": exit code decides
        "command": "",                 // kind "command": e.g. "make test" or "pytest -q"
        "timeout_s": 10,
        "visible": [ { "name": "empty list", "stdin": "0\n", "expected": "\n", "compare": "text" } ],
        "n_hidden": 3                  // hidden tests never leave the server
      }
    }
  ],
  "updated_at": 1762585200.0
}
```

Rules that follow from the plan:

- `workdir` is always `/home/student/labs/<lab id>/<assignment id>`; files are
  written only when the folder does not exist yet (a student's work is never
  overwritten by a newer starter).
- `compare` is the same as web labs (`grading.py`): `text` (default: trailing spaces and newlines
  ignored), `json`, `tokens` (numbers within 1e-6). `checker` is web-only.
- The reference solution, hidden tests and the recipe's admin-only parts are
  never in a student's copy.
- Image name: `${STUDENTIDE_SANDBOX_REGISTRY}/studentide-env:<env id>-<version>` (one repository, so it is made public once)
  (default registry `ghcr.io/codehamster69`).
- Previews and the desktop runtime start the image with `sleep infinity`; the image's
  `CMD` is the same, and it keeps `bash`, `tar` and `script` for the runtime.

## Recipes

An environment version is a recipe; the server renders it to a Dockerfile
(`GET /api/sandbox/environments/{id}/versions/{v}/dockerfile`) that the build
service, or a developer, builds. Teachers never write one.

```jsonc
{
  "base": "c-cpp",                     // python | c-cpp | java | linux | web-node | databases
  "tools": ["gdb", "valgrind"],        // ids from GET /api/sandbox/tools (apt packages with sizes)
  "apt": [], "pip": [], "npm": [],     // extra packages by name (checked against a safe-name pattern)
  "setup": "",                         // optional shell script run as root at build time
  "dockerfile": ""                     // raw Dockerfile instead of the above: needs admin approval
}
```

Every image is Ubuntu 24.04 with a `student` user (uid 1000, passwordless
sudo), `vim`, `nano`, `tmux`, `git`, `curl` and `ca-certificates`.

## API

Teacher routes need a teacher account (or the admin token in dev mode), like `/api/teach`.

```
GET    /api/sandbox/bases                      base images with what they include
GET    /api/sandbox/tools                      tool checklist with sizes
GET    /api/sandbox/subjects                   my subjects (admins: all)
POST   /api/sandbox/subjects                   {title, code?, semester?, color?, environment_id?}
GET    /api/sandbox/subjects/{id}              subject + labs + people + roster
PATCH  /api/sandbox/subjects/{id}              any of the above
PUT    /api/sandbox/subjects/{id}/people       {co_teachers: [...], tas: [...]}
PUT    /api/sandbox/subjects/{id}/roster       {students: [{id, section?}]} or {text}  (roll ranges expand)
POST   /api/sandbox/subjects/{id}/copy         copy with all labs as drafts (next semester)
GET    /api/sandbox/environments               mine + shared
POST   /api/sandbox/environments               {title, recipe, shared?}
GET    /api/sandbox/environments/{id}
POST   /api/sandbox/environments/{id}/versions {recipe}  new version (draft → building → ready)
GET    /api/sandbox/environments/{id}/versions/{v}/dockerfile
POST   /api/sandbox/environments/{id}/versions/{v}/approve   admins: a raw Dockerfile may be built
POST   /api/sandbox/builds/{env}/{v}           build service callback {status, digest?, log?}  (X-Build-Token)
POST   /api/sandbox/subjects/{id}/labs         {title, description?}
GET    /api/sandbox/labs/{id}                  teacher view: everything incl. hidden tests + solution
PATCH  /api/sandbox/labs/{id}                  {title, description, network, assessed, status, opens_at, due_at, environment_version,
                                                grading_mode, late: {mode, per_day_pct, max_days}}
GET    /api/sandbox/labs/{id}/history          changes made after the lab was published, newest first
POST   /api/sandbox/labs/{id}/history/{c}/undo put back what change c replaced (recorded as a new change)
POST   /api/sandbox/labs/{id}/import           {provider, ref, language}  a question from a question source as an assignment
POST   /api/sandbox/labs/{id}/assignments/copy {assignment_id}  copy one from another lab you can see
GET    /api/sandbox/assignments                every lab you can see with its assignments (for copying)
DELETE /api/sandbox/labs/{id}                  drafts only
POST   /api/sandbox/labs/{id}/assignments      {title, statement, files, open, run, tests, solution_files}
PATCH  /api/sandbox/assignments/{id}
DELETE /api/sandbox/assignments/{id}
PUT    /api/sandbox/labs/{id}/order            {assignment_ids}
GET    /api/sandbox/labs/{id}/definition       the lab as a student gets it (format above, draft allowed)
POST   /api/sandbox/labs/{id}/share            {summary, topics, difficulty}  put a snapshot in the library
DELETE /api/sandbox/labs/{id}/share            withdraw it
GET    /api/sandbox/library                    ?q=&subject=&topic=&difficulty=
GET    /api/sandbox/library/{id}               preview (solutions shown to teachers)
POST   /api/sandbox/library/{id}/use           {subject_id}  independent copy, based_on link
GET    /api/sandbox/previews                   my running previews + seats left
POST   /api/sandbox/previews                   {lab_id}  start "Try as a student" (capped)
                                               {environment_id}  "set up by hand" (same seats)
GET    /api/sandbox/previews/{id}/setup        set up by hand: commands typed so far -> {script, kept, dropped}
GET    /api/sandbox/previews/{id}
POST   /api/sandbox/previews/{id}/stop
GET/PUT /api/sandbox/previews/{id}/files       ?path=  read or write a file in the preview
POST   /api/sandbox/previews/{id}/exec         {command, stdin?}  run a command (Run / Check)
WS     /api/sandbox/previews/{id}/terminal     interactive shell

GET    /api/sandbox/labs/{id}/submissions      gradebook: every rostered student x assignment (latest + attempts)
GET    /api/sandbox/submissions/{id}           one submission, hidden tests in full, session_id for review
POST   /api/sandbox/submissions/{id}/regrade
POST   /api/sandbox/labs/{id}/regrade          the latest submission of every student and assignment

Students (desktop app, same sign-in):
GET    /api/sandbox/my/labs                    published (and closed) labs of my subjects, grouped by subject;
                                               each with closed, submitted, passed_all
GET    /api/sandbox/my/labs/{id}               the lab definition (format above) + closed
GET    /api/sandbox/my/labs/{id}/submissions   my latest submission per assignment (hidden tests: name + pass)
GET    /api/sandbox/my/submissions/{id}        one, for polling while it grades (+ queue_ahead)
POST   /api/sessions  {sandbox_lab_id, assignment_id, sitting_id, …}   one recorded session per assignment visited (docs/sandbox-student.md)
```

## Lab wizard extras

- **Import a question.** Assignments step, "Import a question": any importable question source of web
  labs (Student IDE sets, Codeforces/CodeChef, MBPP; link-only sites are left out). The teacher picks the
  language students answer in; the import brings the statement (with the source's credit line), one
  starter file, a Run command for that language and the source's tests as input/output pairs. A
  function-style question also gets its test driver as `.studentide/harness.<ext>`, which the Run command
  joins to the student's file, as the web grader does. `checker` tests become `tokens` (with a note).
  "Copy from another lab" copies one assignment from any lab the teacher can see.
- **Set up by hand.** On the subject's Environment panel: a fresh preview instance of the environment
  with a terminal, as on any Linux machine (sudo works; network is registries only). Every command lands
  in `~/.studentide-setup-history` (`~/.bash_profile` turns on `history -a`). The page shows the recipe
  live: commands that change the machine in order, look-around ones (`ls`, `cat`, `--version`, editors)
  left out, `sudo` dropped and `apt` given `-y`, because the build runs as root without a terminal.
  The teacher edits it if needed and saves: the script is appended to the recipe's `setup` and a new
  environment version builds. Edits made inside vim or nano are not captured (the page says to use `tee`).
- **Grading mode and late policy** (Publish step), with a "What students will see" summary card before
  the button. `late_policy(lab, submitted_at)` in `sandbox_authoring.py` (re-exported by `sandbox.py`)
  is the one rule: on time up to `due_at` + 120 s; then refused (`closed`), taken and marked late
  (`accept`), or taken with `per_day_pct` off per started day and refused after `max_days` (`penalty`).
  Submissions (`submissions.py`) call it for the gate and the score factor.
- **Editing a lab students already have** (plan §5.5). Every change after the first publish is a row in
  `sbx_lab_changes` with a plain-sentence summary and the old values, shown on the wizard's History step
  with Undo. After a save the wizard says what students will notice: statement and test fixes reach them
  at once; a change to an assignment's tests or Run command calls every hook in
  `router.on_tests_changed` (submissions.py registers its regrade) and records how many submissions were
  regraded; new starter files reach only students who have not opened that assignment yet (the runtime
  seeds a folder only when it does not exist). A failing hook never loses the teacher's edit.
- **Vim mode** in our editors (`frontend/src/editor/vim.ts`, `@replit/codemirror-vim`): a per-browser
  switch next to Reset in the student editor and in every sandbox file editor. Normal-mode keys are
  ordinary key events and the edits they cause ordinary edit events, so the event schema is unchanged.

## Ownership

Subjects follow the lab rules of PR #19: the owner and co-teachers edit, TAs
view, admins see everything, only admins change the owner. A sandbox lab
belongs to its subject's people. Environments belong to their author; a
**shared** environment can be used by every teacher but edited only by its
author. Library entries are snapshots: using one makes an independent copy
with a `based_on` link.

## Teacher previews ("Try as a student")

`previews.py` runs a lab in a short-lived instance on the VM, for teachers only
(students never get a cloud instance). Caps, all from the environment:

| variable | default | meaning |
|---|---|---|
| `STUDENTIDE_PREVIEW_URL` + `STUDENTIDE_PREVIEW_TOKEN` | unset | the preview service (Compose profile `previews`); unset = previews off |
| `STUDENTIDE_PREVIEW_DOCKER=1` | unset | dev: use the docker CLI on this machine instead of the service |
| `STUDENTIDE_PREVIEW_BUILD_LOCAL=1` | unset | dev: build a missing environment image from its Dockerfile |
| `STUDENTIDE_PREVIEW_SEATS` | 3 | previews running at once, all teachers together; one per teacher |
| `STUDENTIDE_PREVIEW_IDLE_MIN` / `_MAX_MIN` | 15 / 60 | idle stop and hard limit |
| `STUDENTIDE_PREVIEW_CPUS` / `_MEMORY_MB` | 1 / 1024 | per preview, at most |
| `STUDENTIDE_PREVIEW_NETWORK` + `STUDENTIDE_PREVIEW_PROXY` | set by Compose | registries-only network (internal Docker network + allowlist proxy); without them previews have no network |

A preview never gets the open internet, even for an open-network lab. Its
container uses the same `docker run` flags as the desktop runtime (`--init`,
`--user student`, capabilities listed one per `--cap-add`, never
`--privileged`, no host mounts) plus the limits above. The app never holds the
Docker socket: `preview_service.py` does, in its own container on the internal
network, and accepts only containers named `sbxp-prv_…` and paths under
`/home/student` or `/tmp`. The browser terminal is a WebSocket (JSON
`{type: input|resize}` in, text out), proxied by the app to the service.

The lab wizard's **Check** step uses a preview: per assignment, the reference
solution laid over the starter must pass every test and the starter alone
should fail at least one.

## Grading submissions

Submit in the desktop app uploads the assignment folder with reason `submit`
(`PUT /api/workspaces/...`, see workspaces.py). Every upload is checked first:
the lab must be open to the student (published or closed, on the roster and
section, past `opens_at`) and contain the assignment, else 403/404. A Submit
after the due time (plus 2 minutes' grace) or on a closed lab is refused with
409 and a sentence the app shows ("This lab closed at …"); change and run
backups are still kept, so no work is lost.

A kept Submit becomes a row in `sbx_submissions` and joins a queue
(`backend/studentide/submissions.py`). One grader thread works through it, so
grading never competes with itself on the e2-medium VM: for each submission it
starts a fresh container of the lab's environment image through the preview
driver (in deployment `preview_service.py`, the only holder of the Docker
socket; containers `sbxp-sub_*`), with **no network**, at most 1 CPU and
1 GB, lays the starter files and then the student's UTF-8 files over them, runs
every test (hidden ones too) with the assignment's Run command, records the
result and removes the container. A run that fails (image not built, deleted
lab) is recorded as `failed` with the reason and the queue goes on; a restart
puts a run that was cut off back in the queue.

The student gets status, passed/total and each visible test in full; hidden
tests show only their name and whether they passed. Teachers open a published
lab on its **Submissions** step: a gradebook of students × assignments with
filters (not submitted, failing a test, all passed), attempt counts, a side
panel with every test (hidden ones in full), a link to the session's review
("How it was written"), Regrade one or all (after fixing a test), and a CSV
download.

Without a preview driver (`STUDENTIDE_PREVIEW_URL` or
`STUDENTIDE_PREVIEW_DOCKER=1`) submissions are kept but wait ungraded, and the
gradebook says so; `STUDENTIDE_GRADING=off` turns grading off while previews
stay on. Grading uses the lab's image only, not packages a student installed in
their own instance, like any autograder. e2e with screenshots:
`frontend/e2e/sandbox-grading.mjs`.

### Registries-only network

With the `previews` profile, Compose puts preview instances on the internal
network `studentide_previews`, which has no route out. The one way out is
`preview-proxy` (`backend/studentide/registry_proxy.py`, a small forward
proxy, read-only, no capabilities), which the instance reaches through
`HTTP(S)_PROXY`. It passes CONNECT (HTTPS, never decrypted) and plain-HTTP
requests (apt) only to the package registries in `REGISTRY_HOSTS`, on ports 80
and 443, and answers 403 to anything else. It logs host names only. The list is
the desktop runtime's `desktop/sandbox/src/registries.ts`;
`tests/test_registry_proxy.py` fails if the two drift. The image's sudoers keeps
the proxy variables, so `sudo apt install` works too.

## Building environment images

Images are built off the student-facing VM, by
`backend/studentide/sandbox_build.py` (standard library only), run every 10
minutes by the GitHub Actions workflow `.github/workflows/sandbox-env-images.yml`.
It polls `GET /api/sandbox/builds` with `X-Build-Token: $STUDENTIDE_BUILD_TOKEN`,
marks each job `building`, builds and pushes `{image, dockerfile}` for amd64 +
arm64 with buildx, smoke-tests the result (student user, passwordless sudo,
bash, tar, script, editors, git, curl), then posts `{status: "ready", digest}`
(or `"failed"` with the log tail) to `/api/sandbox/builds/{env}/{version}`. A
job left `building` for over 2 hours (a builder that died) is handed out again.
A raw Dockerfile waits for an admin's approval first. Until a version is ready
the lab definition carries `digest: null` and the recipe, so a client can build
it locally.

Every environment is a tag of one package,
`ghcr.io/codehamster69/studentide-env:<env>-<version>`, so it is made public
once and every image after that is pullable without a login. Setup, once:

1. In the repo's Actions settings add the secret `STUDENTIDE_BUILD_TOKEN` (the
   same value as on the VM) and the variable `STUDENTIDE_URL`
   (`https://studentide.hokora.xyz`). Without the variable the job does nothing.
2. After the first build, set the `studentide-env` package's visibility to public.

Locally: `STUDENTIDE_BUILD_TOKEN=… python backend/studentide/sandbox_build.py
--server http://127.0.0.1:8000 --no-push` builds for this machine only.

## Checks

- `backend/tests/test_sandbox.py`: subjects, people and TAs, rosters with
  ranges and sections, recipes and Dockerfiles, build callbacks, publish rules,
  the student definition (no hidden tests or solutions), library share/use/update, stale builds handed out again, and
  `sandbox_build.py` against the real endpoints with Docker faked.
- `backend/tests/test_registry_proxy.py`: allowlist, 403 for other hosts and
  ports, CONNECT tunnel and plain-HTTP forwarding, same hosts as the desktop.
- `backend/tests/test_previews.py`: seats, one per teacher, idle stop, time
  limit, files, run/check/verify; one test runs real Docker when
  `ubuntu:24.04` is present.
- `frontend/e2e/sandbox.mjs`: the whole teacher flow in a browser against a
  server with previews on, writing screenshots to `thesis/latex/snapshots/sandbox/`.
