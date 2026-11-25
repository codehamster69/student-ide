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

What each research question can take from it:

- **RQ1 (switch detection):** only the false-alarm upper bound and its drivers. Detection
  delay and hit rate need the staged Phase 2 sessions.
- **RQ2 (composing vs transcribing):** how common the copying signs are, and whether the
  detector's process channel moves with them. Not accuracy: there are no labels.
- **RQ3 (remote transfer):** nothing yet; no remote sessions.
- **RQ4 (fairness):** flag rates by device class and OS; phones record no key presses at all.

## First run (2026-11-25)

1,118 sessions (281 students) from 27 Oct to 23 Nov: 443 lab, 590 competition, 50 practice,
35 learning lab; 608 C and 456 Python; all web, no desktop app. See the brain entry
`thesis/brain/entries/2026-11-25-01-pilot-data-first-look.md` for the numbers and what they changed.
