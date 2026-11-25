# Pilot data: what the live recordings can and can't say

The IIIT Surat pilot (scribelab.hokora.xyz) has recorded real classes since 27 Oct 2026.
Approval: oral institutional approval (Dean, HoD, faculty) per Rohan, 2026-11-25; written
confirmation pending (appendix B). Students saw and accepted the consent screen. Detector
design changes use this data as **development** data only, so the held-out test protocol
(docs/evaluation.md) stays clean.
Nothing here has ground-truth labels: no takeover, proxy or copying is known.

## The tool

`backend/studentide/pilot.py` runs next to the database and writes aggregates only:

```bash
# on the VM, inside the app container (read-only on the database; --detector takes ~1 s a session)
docker compose exec app python -m studentide.pilot --db /data/studentide.sqlite3 --detector --out /tmp/pilot.json
# anywhere
python -m studentide.pilot --summary pilot.json
```

One row per session: counts, rates, percentiles and window-feature medians. No key codes,
code, clipboard text, names, roll numbers or session ids. Students and labs get salted
pseudonyms with a fresh salt per run that is not saved, so reports can't be joined or
reversed. Staff "View as student" sessions are left out.

Raw key events are deleted after 28 days (retention.py); purged sessions keep their stored
windows, so the detector still scores them, but per-key statistics (inter-key and hold
percentiles, "typed with no key") are only available for recent sessions. Run the tool
soon after a class if those matter.

## Splitting unlabelled data

| Question | How the tool answers it | Caveat |
|---|---|---|
| Own laptop or lab PC? | browser fingerprint (OS, browser, screen, platform, time zone, language; no version) shared by ≥3 students = lab-PC-like, else personal-like; Android/iOS = phone; desktop app by its device id | identical laptops collide; a lab PC can look personal if few students used it |
| Does a student's rhythm move with the device? | robust-z distance of five rhythm medians between two sessions: same student same device, same student other device, two students | needs sessions with ≥4 active windows |
| Copying (e.g. from an LLM)? | weak signs: a paste of ≥80 characters, a paste within 60 s of coming back to the window, text typed with no key press within 300 ms (auto-typers), low-revision low-pause "transcription-like" typing | signs, not labels: pasting own code from elsewhere looks the same |
| How often does the detector flag? | episodes per active typing hour (30 s windows with ≥20 keys), split by context, device, OS, usual vs other device, with vs without copying signs | with no known takeovers, every flag counts toward an *upper bound* on the false-alarm rate |

What each research question takes from it (the thesis now uses classroom data only;
see docs/evaluation.md "Classroom data" and thesis ch 3 and 6):

- **RQ1 (switch detection):** false alarms per hour on real sessions (upper bound), plus
  detection and delay on takeovers spliced from two real sessions on the same question.
- **RQ2 (composing vs transcribing):** agreement of the transcription measures with the
  copying signs above (and blocked outside pastes once paste blocking ships). No accuracy.
- **RQ3 (now transfer across devices):** students who used both a lab PC and their own
  laptop; same-device vs other-device drift and cross-device baselines.
- **RQ4 (fairness):** flag rates and splice detection by device class, OS, language,
  context and typing speed; phones record no key presses at all.

**Split.** Tuning uses only the dev split: `harness.split.pilot_split(student_id,
started_at)`, applied to the real id inside the container before pseudonymising.

## First run (2026-11-25)

1,118 sessions (281 students) from 27 Oct to 23 Nov: 443 lab, 590 competition, 50 practice,
35 learning lab; 608 C and 456 Python; all web, no desktop app. See the brain entry
`thesis/brain/entries/2026-11-25-01-pilot-data-first-look.md` for the numbers and what they changed.
