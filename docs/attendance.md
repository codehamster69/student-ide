# Attendance through Roll Call

Student IDE can mark lab attendance in [Roll Call](https://attendance.hokora.xyz)
(codehamsters/attendance). Code: `backend/studentide/attendance.py`,
`frontend/src/teach/Attendance.tsx`; tests `backend/tests/test_attendance.py`,
`frontend/e2e/attendance.mjs`.

## For a teacher

1. **Set up Roll Call once.** Student IDE → Getting started (`#/teach/setup`) →
   *Set up Roll Call for me*. Student IDE makes your own Roll Call key (your own
   register: nobody else's key opens it). From then on *Open Roll Call* (there,
   in a lab, or *Roll Call* in the header) opens Roll Call already signed in.
   *Show key* reveals the key to sign in by hand at `<roll call>/login`.
   Already keep a register in Roll Call? Choose *I already use Roll Call* and
   paste the key from Roll Call → Settings instead.
2. **Attach class groups to a lab.** In the lab, *Class groups and attendance* →
   *Attach class groups*: tick groups from your Roll Call or create one (branch,
   section, lab group, roll prefix and range). Their students join the lab's roster.
   A lab can have several groups (e.g. G1 and G2 sharing a slot).
3. **Open the lab for the group that is performing.** With class groups attached,
   *Open* asks *Which group is performing?*. Tick the group in the room now (or
   several, if they share the slot). Until the lab closes or you move on, only
   those groups' students see the lab; students on no attached roster are not
   restricted. Each opening is a *sitting*.
4. **Move on or close.** *Next group* (in the green "Open for …" bar) ends the
   sitting, sends its attendance for its groups only, and starts a sitting for
   the next group, so G1 on Monday and G2 on Thursday can share one lab without
   G2 being marked absent on Monday. Closing ends the last sitting the same way
   (a lab closed without any sitting sends every lab day not sent yet, as before).
   Groups with nobody working in the lab that day are never sent. To check first, open *Attendance* (`#/teach/labs/<id>/attendance`):
   each student's mark with its reason; tap a mark to override; *Send to Roll Call*.

Roll Call rosters must build the same ids as the college address: `ug23cs001@…`
is `UG23CS001`, so prefix `UG23CS` with 3 digits.

## Who counts as present

Per student and lab day (timezone `STUDENTIDE_TIMEZONE`, default Asia/Kolkata):

| Measure | Default | Counts |
| --- | --- | --- |
| Active minutes | ≥ 10 | distinct minutes with an edit, a Run or a Check |
| Typed characters | ≥ 40 | typed text only; pastes, drops and Reset don't count |
| Run or Check | off | when on, at least one |

Each lab sets its own thresholds (*Rule* on the attendance page), and whether to
send on close. Learning-lab practice and View-as-student previews never count.
The detector is never consulted: a highlighted moment does not change attendance.

## Keys and sign-in

- **Google sign-in in Roll Call.** Teachers without labs can use Roll Call on its
  own: *Sign in with Google* on `/login` (the Student IDE OAuth client, college
  addresses only, student-shaped addresses are sent to My attendance). The first
  sign-in makes their register. With `STUDENTIDE_ROLLCALL_LINK_SECRET` set (same
  value as Roll Call's `LINK_SECRET`), Student IDE and Roll Call keep **one
  register per teacher**: setting up in Student IDE adopts a register the teacher
  already made in Roll Call, a key made in Student IDE is linked so Google sign-in
  opens it, and every existing teacher's key is linked once at start
  (`POST /api/link/teacher`). Admins in Roll Call's `ADMINS` get a *Teachers'
  registers* page there too (Settings), with the same full access and banner.

- **Teachers.** Each teacher's key is one Roll Call workspace. Student IDE keeps it
  on its server (`attendance_links`, `issued = 1` when Student IDE made it). *Open
  Roll Call* asks Roll Call for a one-time link (`POST /api/v1/login-codes`): the
  browser goes to `/login#code=…`, which works once, for two minutes, and stores
  the key in that browser. Roll Call stores the key only encrypted with the code.
- **Students.** *My attendance* (student app header, shown when one of their labs
  has class groups) makes the student's own key (`st_…`, table `student_keys`),
  grants it through every teacher whose attached groups list them
  (`PUT /api/v1/viewers`, Roll Call stores only its sha256) and opens Roll Call's
  `/me` signed in: their own marks, read-only, grouped by subject. A student key
  opens no workspace, and a browser holding one only ever shows `/me`.
- **New key.** *Show key* → *Make a new key* moves the whole register (classes,
  sessions, subjects, students' read access) to a new key in one step
  (`POST /api/v1/rotate` with the new key's hash and the new key, so Roll Call's
  Google sign-in follows). The old key is
  retired: Roll Call answers it with 410, so devices still holding it show
  "Key replaced, sign in again" instead of opening an empty register.
- **Admins** (`STUDENTIDE_ADMINS`, or the admin token in dev mode) see every
  teacher's register under *Teachers' Roll Call registers* (People, and Getting
  started). *Open register* signs them in to it with full access; Roll Call shows
  a banner naming whose register it is, and Student IDE logs every open
  (`attendance_admin_opens`). Roll Call itself has no admin notion: the access
  comes from Student IDE holding the teachers' keys.
- **Shared computers.** Roll Call → Settings → *Sign out* forgets the key and the
  records in that browser. Signing in on a browser that holds someone else's
  records asks whether to move them in or leave them.

## What Roll Call receives

One session per class group and lab day, id `uuid5(lab, class, day)` (resending
replaces it): the group's whole roster marked P/A, subject = the lab's subject,
time slot = first to last activity, and a source link back to the lab.

## Settings

| Variable | Default | |
| --- | --- | --- |
| `STUDENTIDE_ATTENDANCE_URL` | `https://attendance.hokora.xyz` | Roll Call base URL |
| `STUDENTIDE_PUBLIC_URL` | request URL | used in the link back from Roll Call |
| `STUDENTIDE_ROLLCALL_LINK_SECRET` | off | same as Roll Call's `LINK_SECRET`: one register per teacher in both apps |
| `STUDENTIDE_TIMEZONE` | `Asia/Kolkata` | what a "lab day" is |

## Pages

The teacher area's URL scheme is in `frontend/src/routes.ts`: `#/<area>/<collection>/<id>/<view>`,
e.g. `#/teach/labs/<id>`, `#/teach/labs/<id>/attendance`, `#/teach/subjects/<slug>`,
`#/live/labs/<id>`, `#/review/sessions/<id>`. Older links still work and are rewritten.
