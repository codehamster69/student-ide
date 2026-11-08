"""Review lanes for Sandbox Lab sessions (plan 5.6 step 4, 6.3 step 8).

The review timeline (review.py) shows the detector's two channels; a Sandbox
Lab adds what happened outside our editor, as evidence lanes beside them:

    terminal   each command (term_cmd end): line, folder, exit code, output tail
    saves      fs_change from the sidecar watcher: vim/nano saves (with or without
               typing behind them), files written by a command, files changed
               with no command we could see ("changed outside the app")
    ports      programs that started listening (port_open)
    network    hosts the lab reached or was refused (net_conn), packages (pkg_install)
    offline    spells when the app could not reach the server (from the signed batches):
               shown as gaps, never as moments
    breaks     batches whose signature or chain did not check out (batches.py)
    unseen     files whose content nothing we saw explains (evidence.py), for the
               latest workspace snapshot and every Submit
    quiet      shell hooks went quiet: Enter pressed at the prompt with no command logged

Same wording rule as the rest of the review: these are things to look at or
ask about, never verdicts. `GET /api/review/sessions/{id}/sandbox`.
"""

from __future__ import annotations

import json

from . import batches, evidence
from .db import Database

MAX_ITEMS = 2000


def is_sandbox(row) -> bool:
    q = json.loads(row["question_json"]) if row["question_json"] else {}
    return q.get("kind") == "sandbox"


def lanes(db: Database, row) -> dict:
    sid = row["id"]
    q = json.loads(row["question_json"]) if row["question_json"] else {}
    lab_id, asg = row["lab_id"], row["question_id"]
    workdir = f"/home/student/labs/{lab_id}/{asg}" if lab_id and asg else ""
    events = list(db.iter_events(sid, ("term_cmd", "term_output", "term_paste", "fs_change", "port_open", "net_conn",
                                       "pkg_install", "key", "session_start", "session_end", "run")))
    with db.connect() as conn:  # every event's time (batches are located by their first seq), without reading bodies
        t_of = {r[0]: r[1] for r in conn.execute("SELECT seq, t FROM events WHERE session_id = ?", (sid,))}
    commands, outputs, pastes, ports, net, pkgs = [], {}, [], [], [], []
    term_keys = 0
    enters: list[float] = []
    open_cmd: dict[str, dict] = {}
    for e in events:
        d, t = e["data"], round(e["t"] / 1000, 2)
        typ = e["type"]
        if typ == "term_cmd":
            if d["phase"] == "start":
                open_cmd[d["term_id"]] = {"t": t, "command": d["command"], "cwd": d["cwd"]}
            else:
                start = open_cmd.pop(d["term_id"], None)
                commands.append({"t": start["t"] if start else max(0.0, t - (d.get("duration_ms") or 0) / 1000), "end": t,
                                 "command": d["command"], "cwd": d["cwd"], "exit_code": d.get("exit_code"), "tail": ""})
                if d["term_id"] in outputs:
                    commands[-1]["tail"] = outputs.pop(d["term_id"])
        elif typ == "term_output":
            if commands and commands[-1]["end"] >= t - 0.5 and not commands[-1]["tail"]:
                commands[-1]["tail"] = d["tail"]
            else:
                outputs[d["term_id"]] = d["tail"]
        elif typ == "term_paste":
            pastes.append({"t": t, "length": d["length"], "lines": d["lines"]})
        elif typ == "port_open":
            ports.append({"t": t, "port": d["port"], "process": d.get("process", ""), "open": d["open"]})
        elif typ == "net_conn":
            net.append({"t": t, "host": d["host"], "allowed": d["allowed"]})
        elif typ == "pkg_install":
            pkgs.append({"t": t, "manager": d["manager"], "action": d["action"], "packages": d["packages"][:20]})
        elif typ == "key" and d.get("surface") in ("terminal", "terminal-editor") and d.get("action") == "down":
            term_keys += 1
            if d.get("surface") == "terminal" and d.get("cls") == "enter":
                enters.append(t)
    for start in open_cmd.values():  # still running when the session ended
        commands.append(start | {"end": None, "exit_code": None, "tail": ""})
    commands.sort(key=lambda c: c["t"])

    saves = [s | {"t": round(s["t"] / 1000, 2)} for s in evidence.saves(events, workdir)]
    # shell hooks went quiet: Enter pressed at the prompt again and again with no command logged
    # (the student has sudo and may remove the hooks; key timing comes from the app, so we still see the Enters)
    starts = sorted(c["t"] for c in commands)
    silent = [t for t in enters if not any(t <= x <= t + 3 for x in starts)]
    quiet, run = [], []
    for t in silent + [float("inf")]:
        if run and t - run[-1] > 120:
            if len(run) >= 3:
                quiet.append({"t": run[0], "end": run[-1], "enters": len(run)})
            run = []
        run.append(t)

    info = batches.integrity(db, sid)
    offline = []
    for o in info["offline"]:
        end = t_of.get(o["min_seq"])
        if end is None:
            continue
        end_s = end / 1000
        offline.append({"t": round(max(0.0, end_s - o["offline_ms"] / 1000), 2), "end": round(end_s, 2),
                        "seconds": round(o["offline_ms"] / 1000), "lag_s": round(o["lag_ms"] / 1000) if o["lag_ms"] else None})
    breaks = [{"t": round(t_of[b["min_seq"]] / 1000, 2) if b["min_seq"] in t_of else None, "problem": b["problem"]}
              for b in info["breaks"]]

    unseen = {"snapshots": []}
    if lab_id and asg:
        starter = {f["path"]: f["content"] for f in q.get("files", []) if isinstance(f, dict) and "content" in f}
        if not starter:
            starter = _starter(db, asg)
        unseen = evidence.for_assignment(db, row["student_id"], lab_id, asg, starter)

    return {
        "commands": commands[:MAX_ITEMS], "saves": saves[:MAX_ITEMS], "pastes": pastes, "ports": ports,
        "network": net, "packages": pkgs, "terminal_keys": term_keys, "quiet": quiet[:50],
        "signed": info["signed"], "offline": offline, "breaks": breaks, "unseen": unseen["snapshots"],
        "watching": any(e["type"] == "fs_change" for e in events) or None,
    }


def _starter(db: Database, assignment_id: str) -> dict[str, str]:
    with db.connect() as conn:
        try:
            row = conn.execute("SELECT files_json FROM sbx_assignments WHERE id = ?", (assignment_id,)).fetchone()
        except Exception:
            return {}
    return {f["path"]: f.get("content", "") for f in json.loads(row["files_json"])} if row else {}
