"""Descriptive statistics for real recordings, in a form that is safe to take off the server.

    python -m studentide.pilot --db /data/studentide.sqlite3 --out /tmp/pilot.json [--detector]
    python -m studentide.pilot --summary /tmp/pilot.json

The first form runs next to the database (inside the app container on the VM)
and writes one row per session: counts, rates, percentiles and window-feature
medians, never key codes, code, clipboard text, names or roll numbers.
Students and labs get salted-hash pseudonyms; the salt is random per run and
not saved, so two reports cannot be joined and nobody can reverse them.
`--detector` also scores every session the way the review screen does (slow:
about a second per session on the pilot VM). The second form prints the tables.

What it answers when there are no ground-truth labels (docs/pilot-data.md):
* data quality: lost events, missing ends, clock skew, upload lag, sessions
  with edits but no key events (phones; the desktop dev-mode bug);
* devices: web or desktop, OS, and whether a browser fingerprint (OS, browser,
  screen, platform, time zone, language; no version, so updates do not split
  a machine) is shared by several students (lab-PC-like) or not;
* weak copying signs: big pastes, pastes soon after leaving the window, text
  typed with no key presses, low-revision "transcription-like" typing;
* the detector's flag rate per active typing hour, split by context, device
  and OS: with no takeovers known, an upper bound on its false-alarm rate;
* what teachers noted after talking with students about review moments
  (`outcome_counts`): counts by outcome and channel on the dev split only,
  reported descriptively, never as labels of cheating.
Staff previews ("View as student") are left out, as everywhere else.
"""

from __future__ import annotations

import argparse
import collections as C
import hashlib
import itertools
import json
import re
import secrets
import sqlite3
import sys
import time

import numpy as np

from .harness.split import pilot_split

STUDY = ("lab", "competition", "practice", "sandbox")
BIG_PASTE = 80  # characters
AWAY_PASTE_S = 60.0  # a paste this soon after coming back to the window
NO_KEY_MS = 300.0  # typed text with no key press this close before it
LAB_PC_STUDENTS = 3  # a fingerprint shared by this many students looks like a lab PC
WINDOW_FEATURES = ("dg_median", "dg_lscale", "hold_median", "del_per_100", "pause_per_100", "fill_in_frac", "paste_frac")


def ua_info(ua: str | None) -> tuple[str, str, str]:
    ua = ua or ""
    os_ = ("Android" if "Android" in ua else "iOS" if re.search("iPhone|iPad", ua) else "Windows" if "Windows" in ua
           else "ChromeOS" if "CrOS" in ua else "Mac" if "Macintosh" in ua or "Mac OS X" in ua else "Linux" if "Linux" in ua else "other")
    m = re.search(r"(Edg|OPR|Firefox|Chrome|Version)/(\d+)", ua)
    br = {"Edg": "Edge", "OPR": "Opera", "Version": "Safari"}.get(m.group(1), m.group(1)) if m else "other"
    return os_, br, m.group(2) if m else ""


def device_fingerprint(meta: dict) -> str:
    """What identifies the machine a session ran on, from its client_meta: the desktop
    app's device id, else OS, browser, screen, platform, time zone and language (no
    browser version, so an update does not make a new device)."""
    cl = meta.get("client") or {}
    if cl.get("kind") == "desktop" and cl.get("device"):
        return str(cl["device"])
    os_, br, _ = ua_info(meta.get("user_agent"))
    scr = meta.get("screen") or {}
    return "|".join(map(str, (os_, br, scr.get("w"), scr.get("h"), scr.get("dpr"), meta.get("platform"),
                              meta.get("timezone"), meta.get("language"))))


def device_class(client: str, os_: str, n_students_on_fp: int) -> str:
    """desktop app | phone | lab-PC-like (fingerprint shared by >= LAB_PC_STUDENTS students) | personal-like."""
    return ("desktop app" if client == "desktop" else "phone" if os_ in ("Android", "iOS")
            else "lab-PC-like" if n_students_on_fp >= LAB_PC_STUDENTS else "personal-like")


class _Acc:
    """Running per-session counts while streaming its events in seq order."""

    def __init__(self) -> None:
        self.types: C.Counter = C.Counter()
        self.chars: C.Counter = C.Counter()  # inserted characters by edit origin
        self.n = self.t_back = self.downs = self.ups = self.code_downs = self.dels = 0
        self.seq_max = -1
        self.t_last = -1e18
        self.t_max = 0.0
        self.lag: list[float] = []
        self.skew: float | None = None
        self.last_down = -1e12
        self.down_at: dict[str, float] = {}
        self.iki: list[float] = []
        self.hold: list[float] = []
        self.typed = self.typed_no_key = self.typed_no_key_chars = 0
        self.pastes = self.paste_chars = self.big_pastes = self.away_pastes = 0
        self.blur = 0
        self.blur_at: float | None = None
        self.back_at = -1e12
        self.runs = self.run_err = 0

    def add(self, seq: int, t: float, typ: str, d: dict, lag: float | None, started: float) -> None:
        self.n += 1
        self.types[typ] += 1
        self.seq_max = max(self.seq_max, seq)
        self.t_back += t < self.t_last
        self.t_last, self.t_max = t, max(self.t_max, t)
        if lag is not None:
            self.lag.append(lag)
        if typ == "session_start" and d.get("wall_clock_ms"):
            self.skew = d["wall_clock_ms"] / 1000 - started
        elif typ == "key" and d.get("surface", "editor") == "editor":
            if d["action"] == "up":
                self.ups += 1
                t0 = self.down_at.pop(d["code"], None)
                if t0 is not None and 0 <= t - t0 < 2000:
                    self.hold.append(t - t0)
                return
            self.downs += 1
            if d.get("repeat") or d["cls"] == "modifier":
                return
            self.code_downs += 1
            self.dels += d["cls"] in ("backspace", "delete")
            if t - self.last_down < 5000:
                self.iki.append(t - self.last_down)
            self.last_down = t
            self.down_at[d["code"]] = t
        elif typ == "edit":
            o = d["origin"]
            ins = sum(len(c[2]) for c in d["changes"])
            self.chars[".".join(o.split(".")[:2])] += ins
            if o in ("input.type", "input.type.compose"):
                self.typed += 1
                if t - self.last_down > NO_KEY_MS:
                    self.typed_no_key += 1
                    self.typed_no_key_chars += ins
            elif o.startswith("input.paste"):
                self.pastes += 1
                self.paste_chars += ins
                self.big_pastes += ins >= BIG_PASTE
                self.away_pastes += t - self.back_at < AWAY_PASTE_S * 1000
        elif typ == "focus" and d.get("target") in ("window", "page"):
            if d["state"] == "out":
                self.blur += 1
                self.blur_at = t
            elif self.blur_at is not None:
                self.blur_at, self.back_at = None, t
        elif typ == "run":
            self.runs += 1
            self.run_err += bool(d.get("error_type")) or d.get("exit_code") not in (0, None)


def _pct(x: list[float], ps=(10, 50, 90)) -> list[float] | None:
    return [round(float(v), 1) for v in np.percentile(x, ps)] if len(x) > 20 else None


def session_rows(db_path: str, salt: str | None = None) -> dict[str, dict]:
    """One aggregate row per non-preview session, keyed by session id (the ids stay
    on the server: report() drops them). Reads the database read-only."""
    salt = salt or secrets.token_hex(8)
    ph = lambda x, n=8: hashlib.sha256((salt + str(x)).encode()).hexdigest()[:n]  # noqa: E731
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    kind = {r["id"]: r["kind"] for r in c.execute("SELECT id, kind FROM labs")}
    rows: dict[str, dict] = {}
    for s in c.execute("SELECT * FROM sessions WHERE context IS NULL OR context != 'preview'"):
        meta = json.loads(s["client_meta"] or "{}")
        cl = meta.get("client") or {}
        os_, br, ver = ua_info(meta.get("user_agent"))
        scr = meta.get("screen") or {}
        desktop = cl.get("kind") == "desktop"
        fp = device_fingerprint(meta)
        q = json.loads(s["question_json"]) if s["question_json"] else {}
        ctx = s["context"] or ("competition" if kind.get(s["lab_id"]) == "competition" else
                               "lab" if s["lab_id"] in kind else "sandbox" if s["lab_id"] else "practice")
        rows[s["id"]] = dict(
            student=ph(s["student_id"], 6), lab=ph(s["lab_id"] or "-", 6), ctx=ctx, lang=q.get("language"),
            started=s["started_at"], ended=s["ended_at"] is not None, end_reason=s["end_reason"], schema=s["schema_version"],
            client="desktop" if desktop else "web", app_version=cl.get("app_version"), os=os_, browser=br, browser_major=ver,
            screen=f'{scr.get("w")}x{scr.get("h")}@{scr.get("dpr")}', fp=ph(fp), purged=s["keys_purged_at"] is not None,
            n_events=0)
    started = {sid: r["started"] for sid, r in rows.items()}

    def flush(sid: str, a: _Acc) -> None:
        r = rows[sid]
        ins = sum(a.chars.values())
        r.update(
            n_events=a.n, types=dict(a.types), chars=dict(a.chars),
            missing_events=a.seq_max + 1 - a.n, t_backwards=a.t_back, active_s=round(a.t_max / 1000, 1),
            lag_median_s=round(float(np.median(a.lag)), 2) if a.lag else None, lag_max_s=round(max(a.lag), 1) if a.lag else None,
            clock_skew_s=round(a.skew, 1) if a.skew is not None else None,
            key_downs=a.code_downs, key_ups=a.ups, iki_ms=_pct(a.iki), hold_ms=_pct(a.hold),
            del_share=round(a.dels / a.code_downs, 3) if a.code_downs else None,
            typed_edits=a.typed, typed_no_key=None if r["purged"] else a.typed_no_key,
            typed_no_key_chars=None if r["purged"] else a.typed_no_key_chars,
            pastes=a.pastes, paste_share=round(a.paste_chars / ins, 3) if ins else 0.0,
            big_pastes=a.big_pastes, away_pastes=a.away_pastes, blur=a.blur, runs=a.runs, run_errors=a.run_err)

    cur, acc = None, _Acc()
    for sid, seq, t, typ, data, rec in c.execute(
            "SELECT session_id, seq, t, type, data, received_at FROM events ORDER BY session_id, seq"):
        if sid not in rows:
            continue
        if sid != cur:
            if cur:
                flush(cur, acc)
            cur, acc = sid, _Acc()
        acc.add(seq, t, typ, json.loads(data), rec - (started[sid] + t / 1000), started[sid])
    if cur:
        flush(cur, acc)
    c.close()

    shared = C.defaultdict(set)
    for r in rows.values():
        shared[r["fp"]].add(r["student"])
    for r in rows.values():
        r["device"] = device_class(r["client"], r["os"], len(shared[r["fp"]]))
    return rows


def copying_signs(r: dict) -> list[str]:
    """Weak, unlabelled signs that text came from somewhere else (docs/pilot-data.md)."""
    out = []
    if r.get("big_pastes"):
        out.append("big paste")
    if r.get("away_pastes"):
        out.append("paste soon after leaving the window")
    if r.get("typed_no_key_chars") and r["typed_no_key_chars"] >= 200 and r["typed_no_key"] > 0.2 * max(1, r["typed_edits"]):
        out.append("typed text with no key presses")
    f = r.get("features") or {}
    if (r.get("n_active") or 0) >= 6 and f.get("del_per_100") is not None and f["del_per_100"] < 3 and (f.get("pause_per_100") or 9) < 2:
        out.append("transcription-like")
    return out


def add_detector(rows_by_id: dict[str, dict], db_path: str, log=print) -> None:
    """Score each session as the review screen does; adds baseline status, episodes and window medians."""
    from .db import Database
    from .review import Reviewer

    db = Database(db_path)
    rv = Reviewer(db)
    for i, s in enumerate(db.list_sessions()):
        r = rows_by_id.get(s["id"])
        if r is None:
            continue
        if i % 100 == 0:
            log(f"  detector {i}")
        sm = rv.summary(s["id"])
        wins = [w for w in rv.windows(dict(s)) if w["active"]]
        r.update(baseline=sm["baseline"], phase=sm.get("phase"), n_active=len(wins),
                 episodes=[e["channel"] for e in sm["episodes"]],
                 features={f: round(float(np.median(v)), 3) if (v := [w[f] for w in wins if np.isfinite(w.get(f, np.nan))]) else None
                           for f in WINDOW_FEATURES})


def report(db_path: str, detector: bool = False, log=print) -> dict:
    t0 = time.time()
    by_id = session_rows(db_path)
    if detector:
        add_detector(by_id, db_path, log)
    rows = list(by_id.values())  # session ids stay behind
    for r in rows:
        r["copying_signs"] = copying_signs(r)
    return {"generated": time.time(), "took_s": round(time.time() - t0), "detector": detector, "rows": rows,
            "outcomes": outcome_counts(db_path)}


# -- conversation outcomes (staff notes on review moments; docs/review.md)

OUTCOME_ORDER = ("own_work", "had_help", "copied", "not_discussed")  # = review.OUTCOMES
OUTCOME_LABEL = {"own_work": "Explained, own work", "had_help": "Had help", "copied": "Copied",
                 "not_discussed": "Not discussed"}
CHANNEL_ORDER = ("identity", "pairs", "process")


def outcome_counts(db_path: str, test_from: float | None = None) -> dict:
    """What teachers noted after talking about review moments, on the shared dev split
    (harness.split.pilot_split) only: counts by outcome and by channel x outcome, plus
    how many notes were held out. No ids leave: just numbers. `test_from` other than
    the split's own date only in tests on seeded data."""
    def split(student: str, started: float) -> str:
        if test_from is None:
            return pilot_split(student, started)
        return "test" if started >= test_from else pilot_split(student, 0.0)

    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = c.execute("""SELECT o.channel, o.outcome, s.student_id, s.started_at, s.id FROM moment_outcomes o
                            JOIN sessions s ON s.id = o.session_id
                            WHERE s.context IS NULL OR s.context NOT IN ('preview', 'learn')""").fetchall()
    except sqlite3.OperationalError:  # a database from before outcomes existed
        rows = []
    finally:
        c.close()
    dev = [r for r in rows if split(r[2], r[3]) == "dev"]
    by_ch: dict[str, dict[str, int]] = {}
    for ch, oc, *_ in dev:
        row = by_ch.setdefault(ch, {o: 0 for o in OUTCOME_ORDER})
        row[oc] = row.get(oc, 0) + 1
    return {"n_notes": len(dev), "held_out": len(rows) - len(dev),
            "n_sessions": len({r[4] for r in dev}), "n_students": len({r[2] for r in dev}),
            "by_outcome": {o: sum(1 for r in dev if r[1] == o) for o in OUTCOME_ORDER},
            "by_channel": by_ch}


def outcome_summary(c: dict) -> str:
    out = [f"\n-- conversation outcomes (dev split): {c['n_notes']} notes on {c['n_sessions']} sessions, "
           f"{c['n_students']} students; {c['held_out']} held out"]
    out.append("channel".ljust(10) + "".join(OUTCOME_LABEL[o].rjust(22) for o in OUTCOME_ORDER))
    for ch in [*CHANNEL_ORDER, *sorted(set(c["by_channel"]) - set(CHANNEL_ORDER))]:
        if ch in c["by_channel"]:
            out.append(ch.ljust(10) + "".join(str(c["by_channel"][ch].get(o, 0)).rjust(22) for o in OUTCOME_ORDER))
    out.append("all".ljust(10) + "".join(str(c["by_outcome"][o]).rjust(22) for o in OUTCOME_ORDER))
    return "\n".join(out)


def outcome_table(c: dict) -> str:
    """LaTeX table for thesis/latex/tables/teacher-outcomes.tex (generated: rerun, don't edit)."""
    ch_name = {"identity": "Typing rhythm", "pairs": "Key-pair timing", "process": "Way of working"}
    lines = ["% generated by: python -m studentide.pilot --summary REPORT --thesis ../thesis/latex",
             "\\begin{tabular}{l" + "r" * len(OUTCOME_ORDER) + "}", "\\toprule",
             "Channel & " + " & ".join(OUTCOME_LABEL[o] for o in OUTCOME_ORDER) + " \\\\", "\\midrule"]
    for ch in [*CHANNEL_ORDER, *sorted(set(c["by_channel"]) - set(CHANNEL_ORDER))]:
        if ch in c["by_channel"]:
            lines.append(ch_name.get(ch, ch) + " & " + " & ".join(str(c["by_channel"][ch].get(o, 0)) for o in OUTCOME_ORDER) + " \\\\")
    lines += ["\\midrule", "All moments & " + " & ".join(str(c["by_outcome"][o]) for o in OUTCOME_ORDER) + " \\\\",
              "\\bottomrule", "\\end{tabular}", ""]
    return "\n".join(lines)


# -- summary tables

def _q(v, ps=(25, 50, 75)) -> str:
    v = [x for x in v if x is not None]
    return f"n={len(v)} " + "/".join(f"{x:.1f}" for x in np.percentile(v, ps)) if v else "n=0"


def _rate(rows: list[dict]) -> str:
    h = sum(r["n_active"] for r in rows) * 30 / 3600
    eps = C.Counter(e for r in rows for e in r["episodes"])
    return (f"{len(rows)} sessions, {sum(bool(r['episodes']) for r in rows)} flagged, {h:.1f} active h, "
            f"per h: " + ", ".join(f"{k} {v / h:.2f}" for k, v in sorted(eps.items())) if h else f"{len(rows)} sessions")


def summary(rep: dict) -> str:
    R = rep["rows"]
    out: list[str] = []
    P = lambda *a: out.append(" ".join(str(x) for x in a))  # noqa: E731
    P("sessions", len(R), "students", len({r["student"] for r in R}))
    for k in ("ctx", "lang", "client", "os", "device", "end_reason"):
        P(k, dict(C.Counter(r[k] for r in R).most_common()))
    P("events/session (25/50/75)", _q([r["n_events"] for r in R]), "| minutes", _q([r.get("active_s", 0) / 60 for r in R]))
    P("\n-- data quality")
    P("no events", sum(r["n_events"] == 0 for r in R), "| no end", sum(not r["ended"] for r in R))
    P("missing events: in purged sessions", sum(r.get("missing_events", 0) for r in R if r["purged"]),
      "| in unpurged", sum(r.get("missing_events", 0) for r in R if not r["purged"]))
    P("edits but no key presses (unpurged)", dict(C.Counter(r["device"] for r in R if not r["purged"] and r.get("types", {}).get("edit", 0) >= 5 and not r.get("key_downs"))))
    P("events out of time order", sum(r.get("t_backwards", 0) for r in R), "in", sum(bool(r.get("t_backwards")) for r in R), "sessions")
    P("client clock off > 60 s", sum(abs(r.get("clock_skew_s") or 0) > 60 for r in R), "| upload lag > 5 min", sum((r.get("lag_max_s") or 0) > 300 for r in R))
    S = [r for r in R if r["ctx"] in STUDY and r["n_events"] > 10]
    P("\n-- copying signs (study sessions)", len(S))
    P("any paste", sum(r["pastes"] > 0 for r in S), "| over half pasted", sum(r["paste_share"] > .5 for r in S))
    P("signs", dict(C.Counter(x for r in S for x in r["copying_signs"])), "| sessions with any", sum(bool(r["copying_signs"]) for r in S))
    if rep.get("outcomes"):
        P(outcome_summary(rep["outcomes"]))
    if not rep.get("detector"):
        return "\n".join(out)
    P("\n-- detector (baseline ready, some typing)")
    D = [r for r in R if r.get("baseline") == "ready" and r.get("n_active")]
    P("baseline status", dict(C.Counter(r.get("baseline") for r in R if "baseline" in r)))
    P("all:", _rate(D))
    for k in ("ctx", "device", "os"):
        for v in sorted({r[k] for r in D}):
            P(f"  {k}={v}:", _rate([r for r in D if r[k] == v]))
    usual = {s: C.Counter(r["fp"] for r in R if r["student"] == s).most_common(1)[0][0] for s in {r["student"] for r in D}}
    P("  usual device:", _rate([r for r in D if usual[r["student"]] == r["fp"]]))
    P("  other device:", _rate([r for r in D if usual[r["student"]] != r["fp"]]))
    P("  with copying signs:", _rate([r for r in D if r["copying_signs"]]))
    P("  without:", _rate([r for r in D if not r["copying_signs"]]))
    # how far apart two sessions are: same student / same student other device / two students
    F = ("dg_median", "hold_median", "dg_lscale", "del_per_100", "pause_per_100")
    V = [r for r in R if (r.get("n_active") or 0) >= 4 and all((r.get("features") or {}).get(f) is not None for f in F)]
    if len(V) >= 10:
        X = np.array([[r["features"][f] for f in F] for r in V])
        Z = (X - np.median(X, 0)) / (np.median(np.abs(X - np.median(X, 0)), 0) * 1.4826 + 1e-9)
        by = C.defaultdict(list)
        for i, r in enumerate(V):
            by[r["student"]].append(i)
        same, other = [], []
        for ii in by.values():
            for a, b in itertools.combinations(ii, 2):
                (same if V[a]["fp"] == V[b]["fp"] else other).append(float(np.linalg.norm(Z[a] - Z[b])))
        rng = np.random.default_rng(0)
        pairs = rng.integers(len(V), size=(5000, 2))
        between = [float(np.linalg.norm(Z[a] - Z[b])) for a, b in pairs if V[a]["student"] != V[b]["student"]]
        P("\n-- rhythm distance (robust z, 5 features; 25/50/75)")
        P("same student, same device", _q(same)); P("same student, other device", _q(other)); P("two students", _q(between))
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db")
    p.add_argument("--out", help="write the report JSON here (default: stdout)")
    p.add_argument("--detector", action="store_true", help="also score every session (slow)")
    p.add_argument("--summary", metavar="REPORT", help="print the tables of a saved report")
    p.add_argument("--thesis", metavar="LATEX_DIR", help="with --summary: write tables/teacher-outcomes.tex there")
    a = p.parse_args()
    if a.summary:
        rep = json.load(open(a.summary))
        print(summary(rep))
        if a.thesis and rep.get("outcomes"):
            with open(f"{a.thesis}/tables/teacher-outcomes.tex", "w") as f:
                f.write(outcome_table(rep["outcomes"]))
        return
    if not a.db:
        p.error("--db or --summary is required")
    rep = report(a.db, a.detector, log=lambda m: print(m, file=sys.stderr))
    if a.out:
        with open(a.out, "w") as f:
            json.dump(rep, f)
    else:
        json.dump(rep, sys.stdout)


if __name__ == "__main__":
    main()
