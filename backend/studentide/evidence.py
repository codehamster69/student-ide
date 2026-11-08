"""The "appeared without typing" check for Sandbox Labs (plan 4.4).

In a web lab every character reaches the file through our editor, so the edit
log *is* the evidence. In a Sandbox Lab code can also arrive through vim in
the terminal, `cat > main.c`, `curl`, `git checkout` or a tool on the host.
This module compares what is in the student's files with what we saw being
written, and names the content nothing explains. It is evidence for a
conversation, like a large paste, never a verdict, and it does not feed the
detector (see thesis brain 2026-11-08-xx, "terminal events and the detector").

What counts as seen:
  * the assignment's starter files;
  * every line that existed in our editor, built by replaying its edits
    (typed and pasted text both: pastes have their own lane already);
    edits with origin "reload" (the editor picked up a change on disk) are
    replayed but are not evidence themselves;
  * text pasted into the terminal (term_paste);
  * a vim/nano save (fs_change origin "terminal-editor") whose added text is
    covered by keys typed in that terminal editor since the previous save:
    roughly one key per character, with slack for vim commands.

Everything else a file holds is "unseen". Two outputs:
  * `saves(events)`: per fs_change, whether typing explains it, with origin
    ("terminal-editor" without typing, "terminal" = written by a command,
    "outside" = no command we could see), for the review lanes;
  * `check_files(...)`: per file of a workspace snapshot, the lines nothing
    explains (runs at every upload and at Submit, in workspaces.py).

Lines shorter than MIN_LINE non-space characters (braces, `else:`, `}`) are
ignored: they are too common to mean anything.
"""

from __future__ import annotations

import posixpath
import re
from typing import Iterable

from .replay import ReplayError, apply_edit

MIN_LINE = 6
KEY_SLACK = 1.5  # keys per added character allowed for vim's own commands, never below 1
KEY_FLOOR = 20
FLAG_CHARS = 40  # a file is marked when this many unseen characters (non-space) remain

_ws = re.compile(r"\s+")


def norm(line: str) -> str:
    return _ws.sub(" ", line).strip()


def _lines(text: str) -> set[str]:
    return {n for n in (norm(l) for l in text.splitlines()) if len(n.replace(" ", "")) >= MIN_LINE}


def rel_path(path: str | None, workdir: str) -> str | None:
    if not path:
        return None
    p = path
    if p.startswith(workdir.rstrip("/") + "/"):
        p = p[len(workdir.rstrip("/")) + 1:]
    p = posixpath.normpath(p.lstrip("./") if p.startswith("./") else p)
    return p


def saves(events: Iterable[dict], workdir: str = "") -> list[dict]:
    """Every fs_change of a session with whether typing explains it (the review lanes)."""
    keys_since: dict[str | None, int] = {}
    out: list[dict] = []
    for ev in events:
        d = ev["data"]
        if ev["type"] == "key" and d.get("surface") == "terminal-editor" and d.get("action") == "down" \
                and d.get("cls") not in ("modifier", "nav"):
            p = rel_path(d.get("path"), workdir)
            keys_since[p] = keys_since.get(p, 0) + 1
            keys_since[None] = keys_since.get(None, 0) + 1  # vim opened without a file name, or :w other.c
        elif ev["type"] == "fs_change":
            p = rel_path(d["path"], workdir)
            added = len(d.get("added", "").replace(" ", "").replace("\n", ""))
            typed = keys_since.get(p, 0) or keys_since.get(None, 0)
            if d["origin"] == "terminal-editor":
                explained = added == 0 or typed * KEY_SLACK + KEY_FLOOR >= added
            else:
                explained = added == 0 or d.get("deleted", False)
            out.append({"seq": ev["seq"], "t": ev["t"], "path": p, "origin": d["origin"], "command": d.get("command"),
                        "added_lines": d.get("added_lines", 0), "removed_lines": d.get("removed_lines", 0),
                        "added_chars": added, "typed_keys": typed, "deleted": d.get("deleted", False),
                        "binary": d.get("binary", False), "explained": explained, "diff": d.get("diff", "")})
            keys_since[p] = 0
            keys_since[None] = 0
    return out


def seen_lines(events: Iterable[dict], workdir: str = "", starter: dict[str, str] | None = None) -> dict[str | None, set[str]]:
    """Per file (relative path; None = any file), the lines we saw being written."""
    seen: dict[str | None, set[str]] = {None: set()}
    for path, text in (starter or {}).items():
        ls = _lines(text)
        seen.setdefault(rel_path(path, workdir), set()).update(ls)
        seen[None].update(ls)
    docs: dict[str | None, str] = {}
    from_reload: dict[str | None, set[str]] = {}
    events = list(events)

    def harvest(p, doc):
        new = _lines(doc) - from_reload.get(p, set())
        seen.setdefault(p, set()).update(new)
        seen[None].update(new)

    for ev in events:
        d = ev["data"]
        typ = ev["type"]
        if typ in ("snapshot", "edit"):
            p = rel_path(d.get("path"), workdir)
            if typ == "snapshot":
                if p not in docs:
                    docs[p] = d["text"]
                    # the first snapshot is the file as opened: starter, restored or earlier work, not new evidence
                    from_reload.setdefault(p, set()).update(_lines(d["text"]) - seen.get(p, set()))
                else:
                    harvest(p, docs[p])
                continue
            doc = docs.get(p, "")
            try:
                new = apply_edit(doc, d)
            except ReplayError:
                new = doc  # lost events: what we cannot replay we cannot count as seen
            if d.get("origin") == "reload":
                from_reload.setdefault(p, set()).update(_lines(new) - _lines(doc) - seen.get(p, set()))
            elif any("\n" in c[2] for c in d["changes"]) or d.get("origin", "").startswith("input.paste"):
                docs[p] = new
                harvest(p, new)
            docs[p] = new
        elif typ == "term_paste":
            seen[None].update(_lines(d.get("text", "")))
    for p, doc in docs.items():
        harvest(p, doc)
    for s in saves(events, workdir):
        if s["explained"] and s["origin"] == "terminal-editor":
            ev = next(e for e in events if e["seq"] == s["seq"])
            ls = _lines(ev["data"].get("added", ""))
            seen.setdefault(s["path"], set()).update(ls)
            seen[None].update(ls)
    return seen


def check_files(files: dict[str, str], events: Iterable[dict], workdir: str = "", starter: dict[str, str] | None = None) -> list[dict]:
    """For each text file of a snapshot, the lines nothing we saw explains. Only marked files are returned."""
    return unseen_in(files, seen_lines(events, workdir, starter), workdir)


def unseen_in(files: dict[str, str], seen: dict[str | None, set[str]], workdir: str = "") -> list[dict]:
    out = []
    for path, text in sorted(files.items()):
        p = rel_path(path, workdir)
        known = seen.get(p, set()) | seen[None]
        unseen = [l for l in (norm(x) for x in text.splitlines()) if len(l.replace(" ", "")) >= MIN_LINE and l not in known]
        chars = sum(len(l.replace(" ", "")) for l in unseen)
        if chars >= FLAG_CHARS:
            total = sum(len(norm(x).replace(" ", "")) for x in text.splitlines()) or 1
            out.append({"path": p, "unseen_lines": len(unseen), "unseen_chars": chars, "share": round(chars / total, 3),
                        "examples": unseen[:3]})
    return out


# --- per assignment, from stored snapshots ------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace_evidence (
    student_id TEXT NOT NULL, lab_id TEXT NOT NULL, assignment_id TEXT NOT NULL, sha256 TEXT NOT NULL,
    max_seq_json TEXT NOT NULL,  -- the events it was computed from: {session_id: max seq}
    report_json TEXT NOT NULL, created_at REAL NOT NULL,
    PRIMARY KEY (student_id, lab_id, assignment_id, sha256)
);
"""
MAX_TEXT_FILE = 512 * 1024


def snapshot_texts(data: bytes) -> dict[str, str]:
    """The text files of a workspace snapshot (gzip tar from workspaces.py), by relative path."""
    import gzip
    import io
    import tarfile

    out: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(data)), mode="r:") as tar:
        for m in tar.getmembers():
            if not m.isfile() or m.size > MAX_TEXT_FILE:
                continue
            raw = tar.extractfile(m).read()  # type: ignore[union-attr]
            if b"\0" in raw[:8000]:
                continue
            name = m.name[2:] if m.name.startswith("./") else m.name
            out[name] = raw.decode("utf-8", "replace")
    return out


def for_assignment(db, student_id: str, lab_id: str, assignment_id: str, starter: dict[str, str] | None = None) -> dict:
    """The check for the latest snapshot and every Submit of one assignment, over all of the
    student's sessions of it. Cached per snapshot hash until new events arrive."""
    import json
    import time

    workdir = f"/home/student/labs/{lab_id}/{assignment_id}"
    with db.connect() as conn:
        conn.executescript(SCHEMA)
        sessions = conn.execute("""SELECT id FROM sessions WHERE student_id = ? AND lab_id = ? AND question_id = ?
                                   ORDER BY started_at""", (student_id, lab_id, assignment_id)).fetchall()
        try:
            snaps = conn.execute("""SELECT id, sha256, reason, created_at, data FROM workspace_snapshots WHERE student_id = ?
                                    AND lab_id = ? AND assignment_id = ? ORDER BY id""", (student_id, lab_id, assignment_id)).fetchall()
        except Exception:  # workspaces router not mounted (tests of other modules)
            snaps = []
    marks = {s["id"]: db.max_seq(s["id"]) for s in sessions}
    picked = [s for i, s in enumerate(snaps) if s["reason"] == "submit" or i == len(snaps) - 1]
    results = []
    seen_union: dict | None = None
    for snap in picked:
        with db.connect() as conn:
            row = conn.execute("""SELECT max_seq_json, report_json FROM workspace_evidence WHERE student_id = ? AND lab_id = ?
                                  AND assignment_id = ? AND sha256 = ?""", (student_id, lab_id, assignment_id, snap["sha256"])).fetchone()
        if row and json.loads(row["max_seq_json"]) == marks:
            results.append(json.loads(row["report_json"]))
            continue
        if seen_union is None:
            seen_union = {None: set()}
            for s in sessions:
                for p, ls in seen_lines(db.iter_events(s["id"]), workdir, starter).items():
                    seen_union.setdefault(p, set()).update(ls)
        files = snapshot_texts(bytes(snap["data"]))
        flagged = unseen_in(files, seen_union, workdir)
        report = {"sha256": snap["sha256"], "reason": snap["reason"], "created_at": snap["created_at"],
                  "files": len(files), "unseen": flagged}
        with db.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO workspace_evidence VALUES (?,?,?,?,?,?,?)",
                         (student_id, lab_id, assignment_id, snap["sha256"], json.dumps(marks), json.dumps(report), time.time()))
        results.append(report)
    return {"snapshots": results}
