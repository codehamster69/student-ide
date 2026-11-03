# Attendance through Roll Call

Student IDE can mark lab attendance in [Roll Call](https://attendance.hokora.xyz)
(codehamsters/attendance). Code: `backend/studentide/attendance.py`,
`frontend/src/teach/Attendance.tsx`; tests `backend/tests/test_attendance.py`,
`frontend/e2e/attendance.mjs`.

## For a teacher

1. **Connect once.** Roll Call → Settings → Connect Student IDE → copy your sync key.
   Student IDE → Getting started (`#/teach/setup`) → paste it.
2. **Attach class groups to a lab.** In the lab, *Class groups and attendance* →
   *Attach class groups*: tick groups from your Roll Call or create one (branch,
   section, lab group, roll prefix and range). Their students join the lab's roster.
   A lab can have several groups (e.g. G1 and G2 sharing a slot).
3. **Run the lab, then close it.** Closing sends attendance for every lab day not
   sent yet. To check first, open *Attendance* (`#/teach/labs/<id>/attendance`):
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

## What Roll Call receives

One session per class group and lab day, id `uuid5(lab, class, day)` (resending
replaces it): the group's whole roster marked P/A, subject = the lab's subject,
time slot = first to last activity, and a source link back to the lab.

## Settings

| Variable | Default | |
| --- | --- | --- |
| `STUDENTIDE_ATTENDANCE_URL` | `https://attendance.hokora.xyz` | Roll Call base URL |
| `STUDENTIDE_PUBLIC_URL` | request URL | used in the link back from Roll Call |
| `STUDENTIDE_TIMEZONE` | `Asia/Kolkata` | what a "lab day" is |

## Pages

The teacher area's URL scheme is in `frontend/src/routes.ts`: `#/<area>/<collection>/<id>/<view>`,
e.g. `#/teach/labs/<id>`, `#/teach/labs/<id>/attendance`, `#/teach/subjects/<slug>`,
`#/live/labs/<id>`, `#/review/sessions/<id>`. Older links still work and are rewritten.
