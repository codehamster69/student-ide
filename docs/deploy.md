# Deploying Student IDE at IIIT Surat (pilot)

This is how to run Student IDE for real students of one college: Google
sign-in limited to `@iiitsurat.ac.in`, HTTPS, nightly backups and data kept
in India. It targets one Linux VM in an Indian cloud region, but nothing in
it is tied to a provider; a college server works the same way.

> **Pilot first.** Running the editor in a lab is fine with the college's
> permission. Using what it records as *study data* for the thesis also needs
> ethics committee approval and the study's own consent wording. Until then,
> treat the deployment as a pilot: check that sign-in, the editor, labs and the
> timeline work, and keep the recordings out of the thesis results.

## What runs

```
             443 (HTTPS)          internal network "web"        internal network "sandbox" (no internet)
 browser ───────────────► caddy ───────────────────────► app ─────────────────────────────► runner
                          Let's Encrypt cert             API, web app,                       runs student programs:
                          HSTS, security headers         SQLite on volume "data"             no database, no secrets,
                                                         raw-key purge every 6 h             read-only, all caps dropped
                                                               │
                                                         backup (no network): gzipped copy of the database
                                                         every 24 h on volume "backups", 14 days kept
```

All four containers come from one image (`Dockerfile` at the repo root) and
`deploy/docker-compose.yml`.

## 1. A VM in India

Pick an India region so personal data stays in the country (the safe reading
of the DPDP Act 2023 for a college; also the simplest story for the ethics
committee):

| provider | regions |
|---|---|
| AWS | `ap-south-1` Mumbai, `ap-south-2` Hyderabad |
| Google Cloud | `asia-south1` Mumbai, `asia-south2` Delhi |
| Azure | Central India (Pune), South India (Chennai) |
| DigitalOcean | BLR1 Bangalore |

Size: **2 vCPU, 4 GB RAM, 40 GB disk** is enough for a pilot class of about
80. Many students pressing Run at the same moment is the heaviest load; go to
4 vCPU / 8 GB for full lab sections. Use Ubuntu 24.04 LTS, keep the provider's
disk encryption on (the default on all four), and turn on automatic security
updates (`sudo apt install unattended-upgrades`).

Firewall: allow 80 and 443 from anywhere, and 22 (SSH) only from your own IP.
Use SSH keys, not passwords.

## 2. A domain name

Caddy gets the HTTPS certificate by itself, but it needs a name that points at
the VM. Either ask college IT for a subdomain such as
`studentide.iiitsurat.ac.in` (an A record to the VM's public IP), or use a
domain you own. Check with `dig +short studentide.iiitsurat.ac.in` before you
continue.

## 3. The Google OAuth client (you create this once)

1. Open <https://console.cloud.google.com> **signed in with your
   `@iiitsurat.ac.in` account** and create a project, e.g. "Student IDE".
   Creating it inside the college's Google Workspace organisation lets you mark
   the app *Internal*, so Google itself refuses non-college accounts.
2. **Google Auth Platform → Branding**: app name "Student IDE", your support
   email. **Audience**: *Internal* if offered; otherwise *External*, and add
   yourself as a test user until you publish it.
3. **Clients → Create client → Web application**.
   *Authorized JavaScript origins*: `https://studentide.iiitsurat.ac.in` (your
   domain). Add `http://localhost:8000` too if you want to test locally.
   No redirect URI is needed: sign-in uses Google's popup.
4. Copy the **Client ID** (ends in `.apps.googleusercontent.com`). There is no
   client secret to keep: the server only checks the ID tokens Google signs.

If students see "access blocked", the college Workspace admin may be
restricting third-party apps: ask IT to trust this client ID in the Admin
console (Security → API controls).

## 4. Install and start

```bash
# on the VM
curl -fsSL https://get.docker.com | sh          # Docker Engine + compose plugin
sudo usermod -aG docker $USER && newgrp docker

git clone https://github.com/codehamster69/student-ide.git
cd student-ide/deploy
cp .env.example .env && nano .env                 # domain, email, client id, admins
docker compose up -d --build                      # first build takes a few minutes
docker compose ps                                 # all four "Up"
```

Then open `https://<your domain>`. Sign in with the address you put in
`STUDENTIDE_ADMINS`, go to `#/teach`, and you will see **Labs**, **Review** and
**People**.

### Settings (`deploy/.env`)

| variable | meaning |
|---|---|
| `STUDENTIDE_DOMAIN`, `ACME_EMAIL` | site name, and where certificate notices go |
| `STUDENTIDE_GOOGLE_CLIENT_ID` | turns on Google sign-in; roll-number sign-in is then off |
| `STUDENTIDE_ALLOWED_DOMAIN` | `iiitsurat.ac.in`; both the Workspace `hd` claim and the address must match |
| `STUDENTIDE_ADMINS` | comma-separated addresses that are always admins |
| `STUDENTIDE_BRANCH_CODES` | optional, e.g. `cs,ec,ccs`; empty means any 2-4 letters |
| `STUDENTIDE_RAW_KEY_DAYS` | raw keystrokes are deleted after this many days at the latest (default 28) |
| `STUDENTIDE_SESSION_DAYS` | how long a sign-in lasts (default 7) |
| `STUDENTIDE_ADMIN_TOKEN` | leave empty; only for scripts, then unset again |
| `BACKUP_KEEP_DAYS` | how many days of nightly backups to keep (default 14) |

## Who is who

Roles come from the address, so nobody has to be set up by hand:

* `<ug|pg><year><branch><roll>@iiitsurat.ac.in`, any letter case, is a
  **student**. The whole local part, upper-cased, is the student ID used in
  rosters and on the timeline: `pg25cs07@…` is `PG25CS07`. Program, year,
  branch and roll are kept on the account as well.
* Any other college address (`firstname.lastname@…`) is a **teacher**: labs,
  competitions, the review timeline.
* `STUDENTIDE_ADMINS` are **admins**: teachers who can also open **People**
  and override anyone's role. Use this for TAs (a student address made
  teacher), or to make a staff address a student. An override sticks at every
  sign-in until you press Reset. Demoting a teacher signs them out at once.
  You can also add a teacher by address before their first sign-in.

Teachers can paste roll numbers or full addresses into a lab roster; both
become the same ID.

Each student still sees the consent screen at their first sign-in, and
nothing is recorded before they agree.

## Day to day

```bash
cd student-ide/deploy
docker compose logs -f app                        # what the server is doing
git pull && docker compose up -d --build          # update to the latest version
docker compose restart app                        # after editing .env
```

### Backups

The backup container writes `studentide-YYYYMMDD-HHMMSS.sqlite3.gz` every 24 h
(and once shortly after the database first appears), checks each one with
`PRAGMA integrity_check` and keeps 14 days. One right now:

```bash
docker compose exec backup python -m studentide.backup --db /data/studentide.sqlite3 --dir /backups
docker compose exec backup ls -l /backups
```

A backup on the same VM does not survive losing the VM. Turn on the provider's
scheduled disk snapshots (kept in the same India region), or copy backups to
college storage now and then:

```bash
docker compose cp backup:/backups ./backups-copy  # then scp to a college machine
```

Restore (test this once before the pilot):

```bash
docker compose exec backup ls /backups                     # pick one
docker compose stop app
docker compose exec backup python -m studentide.backup --db /data/studentide.sqlite3 \
  --restore /backups/studentide-20261101-020000.sqlite3.gz
docker compose start app
```

The restore goes through SQLite itself, so a leftover write-ahead log cannot
bring back newer data.

### Raw keystrokes

As the consent screen promises, raw key events are deleted once they are no
longer needed (see `backend/studentide/retention.py`): a student's baseline
sessions when their four baseline weeks are over, and any session after
`STUDENTIDE_RAW_KEY_DAYS`. The detector's 30-90 s window summaries are kept, so
baselines, scores and the timeline keep working. To see what is due:

```bash
docker compose exec app python -m studentide.retention --dry-run
```

### A student withdraws or asks for their data to be erased

```bash
docker compose exec app python -m studentide.retention --erase-student PG25CS07
```

This removes their sessions, events, runs, checks, competition entries,
roster places, consent record and account. Copies inside older backups age out
after `BACKUP_KEEP_DAYS`.

## Data protection checklist (DPDP Act 2023)

- [ ] Data stays in India: VM, disk snapshots and backup copies all in an Indian region or on college servers.
- [ ] Purpose is stated on the consent screen, and nothing is recorded before consent.
- [ ] Only college accounts can sign in; only teachers see recordings; only admins change roles.
- [ ] Raw keystrokes are deleted on schedule (purge runs every 6 h); `--dry-run` shows nothing overdue.
- [ ] Erasure requests are handled with `--erase-student` and logged in your own records.
- [ ] Backups are restorable (tested once) and kept no longer than needed.
- [ ] Before using recordings as study data: ethics approval, and the study's consent wording on the consent screen.

## Security notes

- Student programs run only in the `runner` container: read-only file system,
  all Linux capabilities dropped, process and memory limits, and an internal
  network with no route to the internet. It never sees the database or `.env`.
  A student can still crash it with a bad program; Docker restarts it.
- Sign-in uses an HttpOnly, Secure, SameSite=Lax cookie. Only a hash of the
  cookie is stored, so a copy of the database cannot be used to sign in.
- Keep `STUDENTIDE_ADMIN_TOKEN` empty. When set, it opens every teacher endpoint
  to whoever holds it.
- Teachers see every lab and every student at the college. That is fine for a
  pilot with a few teachers; per-teacher lab ownership is a follow-up.

## Without Docker (local development)

Unchanged: leave `STUDENTIDE_GOOGLE_CLIENT_ID` unset and the server runs in dev
mode (roll-number sign-in, `STUDENTIDE_ADMIN_TOKEN` for teacher screens), see
the main README. To try Google sign-in locally, set the client ID, add
`http://localhost:8000` as an authorised origin, and set
`STUDENTIDE_COOKIE_SECURE=0` (cookies over plain HTTP).
