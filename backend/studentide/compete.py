"""Class competitions: a lab run as a timed, class-wide challenge with a live
leaderboard. Class labs treat correctness as optional (effort is what
counts there); a competition is the one place where correctness is always
checked: every question needs test cases, and only passing them scores.

A competition is a lab with kind = 'competition'. It reuses the lab's
questions, roster and sessions (so every keystroke is recorded exactly as in
a normal lab) and adds a clock, a scoring switch and a leaderboard.

Lifecycle: draft -> open (students join the lobby and pick a display name,
questions stay hidden) -> started (clock runs, questions appear) -> ended
(board frozen; the teacher can also close the lab as usual).

Teacher (admin token):
    POST  /api/teach/competitions                  {title, description, subject, language, duration_min, board}
    GET   /api/teach/competitions/{lab_id}         settings + full board
    PATCH /api/teach/competitions/{lab_id}         {duration_min?, board?}
    POST  /api/teach/competitions/{lab_id}/start   opens the lab and starts the clock
                                                   (409 while a question has no tests)
    POST  /api/teach/competitions/{lab_id}/end     stops the clock now

Student (roll number, like the rest of the student API):
    GET   /api/competitions/{lab_id}?student_id=   lobby / live view with the board
    POST  /api/competitions/{lab_id}/join          {student_id, handle?}
    POST  /api/sessions/{session_id}/submit        {code} -> standing after this submission

Scoring (see docs/competitions.md). Each submission is run against the
question's tests. Per question a student keeps their best submission:
    100 x passed/total                       (correctness, partial credit)
    +up to 50 when every test passes in a timed competition, scaled by the
     part of the clock still left             (speed, only for full solves)
A wrong submission costs nothing. Ties go to whoever reached the score
first. Runs and fixed errors never score; they only earn badges.

The leaderboard never reads anything from the review timeline or the
detector: a "moment worth a conversation" stays between the teacher and the
student and can never cost a place on the board. In the other direction, the
review timeline measures competition sessions separately (their own
baseline, see review.Reviewer.baseline_ids): a competition is a different
behaviour from a normal lab.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .db import Database
from .grading import competition_ready, grade, parse_tests

STUDENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

SOLVE_PTS = 100
SPEED_PTS = 50
TOP_N = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS competitions (
    lab_id        TEXT PRIMARY KEY REFERENCES labs(id) ON DELETE CASCADE,
    duration_s    INTEGER,                    -- NULL = no clock, the teacher ends it
    board         TEXT NOT NULL DEFAULT 'top' CHECK (board IN ('top', 'all', 'hidden')),
    started_at    REAL,
    ends_at       REAL                        -- NULL while untimed and running
);

CREATE TABLE IF NOT EXISTS competition_players (
    lab_id        TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    student_id    TEXT NOT NULL,
    handle        TEXT NOT NULL,
    joined_at     REAL NOT NULL,
    PRIMARY KEY (lab_id, student_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS submissions (
    id            TEXT PRIMARY KEY,
    lab_id        TEXT NOT NULL,
    question_id   TEXT NOT NULL,
    student_id    TEXT NOT NULL,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    created_at    REAL NOT NULL,
    code          TEXT NOT NULL,
    passed        INTEGER NOT NULL,
    total         INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS submissions_by_lab ON submissions(lab_id, created_at);
"""


def ensure_schema(db: Database) -> None:
    with db.connect() as conn:  # labs.kind itself is added by db.MIGRATIONS
        conn.executescript(SCHEMA)


# scoring ---------------------------------------------------------------------

@dataclass
class QState:
    tries: int = 0                       # submissions
    solved: bool = False                 # every test passed
    passed: int | None = None            # of the best submission
    total: int | None = None
    points: int = 0
    solved_at: float | None = None


@dataclass
class Standing:
    student_id: str
    handle: str
    points: int = 0
    solved: int = 0
    runs: int = 0
    fixes: int = 0                       # an error followed by a clean run on the same question
    last_gain_at: float = float("inf")   # tie-break: reached this score first
    questions: dict[str, QState] = field(default_factory=dict)
    badges: list[dict] = field(default_factory=list)


def score(comp: dict, question_ids: list[str], players: dict[str, str], runs: list[dict],
          submissions: list[dict]) -> list[Standing]:
    """Rank every player. `runs`: {student_id, question_id, created_at, error_type};
    `submissions`: {student_id, question_id, created_at, passed, total}.
    Only activity between the start and the end of the clock counts. Pure, so
    the tests can feed it made-up activity."""
    start = comp.get("started_at")
    end = comp.get("ends_at")
    duration = comp.get("duration_s")
    if start is None:
        return [Standing(s, h) for s, h in sorted(players.items())]

    def live(t: float) -> bool:
        return t >= start and (end is None or t <= end)

    st = {s: Standing(s, h, questions={q: QState() for q in question_ids}) for s, h in players.items()}

    # runs only feed the "most bugs fixed" badge, never the score
    last_error: dict[tuple[str, str], bool] = {}
    for r in sorted(runs, key=lambda r: r["created_at"]):
        s, q = r["student_id"], r["question_id"]
        if s not in st or q not in st[s].questions or not live(r["created_at"]):
            continue
        ok = r["error_type"] is None
        st[s].runs += 1
        st[s].fixes += ok and last_error.get((s, q), False)
        last_error[(s, q)] = not ok

    gains: dict[str, list[tuple[float, int]]] = {s: [] for s in st}
    for sub in sorted(submissions, key=lambda x: x["created_at"]):
        s, q, t = sub["student_id"], sub["question_id"], sub["created_at"]
        if s not in st or q not in st[s].questions or not live(t) or not sub["total"]:
            continue
        qs = st[s].questions[q]
        qs.tries += 1
        solved = sub["passed"] == sub["total"]
        pts = round(SOLVE_PTS * sub["passed"] / sub["total"])
        if solved and duration:
            # measured against the planned end, so ending early never shrinks a bonus already earned
            pts += round(SPEED_PTS * max(0.0, (start + duration - t) / duration))
        if pts > qs.points:
            gains[s].append((t, pts - qs.points))
            qs.points, qs.passed, qs.total = pts, sub["passed"], sub["total"]
        if solved and not qs.solved:
            qs.solved, qs.solved_at = True, t

    for s, p in st.items():
        p.solved = sum(q.solved for q in p.questions.values())
        for t, pts in gains[s]:
            p.points += pts
            p.last_gain_at = t

    ranked = sorted(st.values(), key=lambda p: (-p.points, p.last_gain_at, p.handle.lower()))
    _badges(ranked, question_ids)
    return ranked


def _badges(ranked: list[Standing], question_ids: list[str]) -> None:
    """Small, positive ways to stand out that are not just the top score, so
    more of the class gets something. No badge ever marks someone as low."""
    def first(pred) -> tuple[Standing, float] | None:
        hits = [(p, t) for p in ranked for t in [pred(p)] if t is not None]
        return min(hits, key=lambda x: x[1]) if hits else None

    hit = first(lambda p: min((q.solved_at for q in p.questions.values() if q.solved_at), default=None))
    if hit:
        hit[0].badges.append({"id": "first_solve", "label": "First to solve"})
    for i, qid in enumerate(question_ids):
        hit = first(lambda p: p.questions[qid].solved_at)
        if hit and len(question_ids) > 1:
            hit[0].badges.append({"id": f"fastest_{i + 1}", "label": f"Fastest on Q{i + 1}"})
    if question_ids:
        for p in ranked:
            if p.solved == len(question_ids):
                p.badges.append({"id": "clean_sweep", "label": "Solved them all"})
    top_fixes = max((p.fixes for p in ranked), default=0)
    if top_fixes >= 2:
        for p in ranked:
            if p.fixes == top_fixes:
                p.badges.append({"id": "comeback", "label": "Most bugs fixed"})


def standing_json(p: Standing, rank: int, question_ids: list[str], detail: bool) -> dict:
    d = {"rank": rank, "handle": p.handle, "points": p.points, "solved": p.solved, "badges": p.badges}
    if detail:
        d.update(student_id=p.student_id, runs=p.runs, fixes=p.fixes, questions=[
            {"tries": q.tries, "solved": q.solved, "points": q.points, "passed": q.passed, "total": q.total}
            for q in (p.questions.get(qid, QState()) for qid in question_ids)])
    return d


# storage ---------------------------------------------------------------------

def get_comp(db: Database, lab_id: str) -> dict | None:
    with db.connect() as conn:
        row = conn.execute(
            """SELECT c.*, l.title, l.description, l.status, l.kind, l.language FROM competitions c
               JOIN labs l ON l.id = c.lab_id WHERE c.lab_id = ?""", (lab_id,)).fetchone()
    return dict(row) if row else None


def state_of(comp: dict, now: float | None = None) -> Literal["draft", "waiting", "live", "ended", "closed"]:
    now = time.time() if now is None else now
    if comp["status"] == "closed":
        return "closed"
    if comp["started_at"] is not None:
        return "ended" if comp["ends_at"] is not None and now >= comp["ends_at"] else "live"
    return "waiting" if comp["status"] == "open" else "draft"


def players(db: Database, lab_id: str) -> dict[str, str]:
    with db.connect() as conn:
        return {r["student_id"]: r["handle"] for r in conn.execute(
            "SELECT student_id, handle FROM competition_players WHERE lab_id = ?", (lab_id,))}


def board(db: Database, comp: dict) -> tuple[list[Standing], list[str]]:
    lab_id = comp["lab_id"]
    qids = [q["id"] for q in db.lab_questions(lab_id)]
    with db.connect() as conn:
        runs = [dict(r) for r in conn.execute(
            """SELECT s.student_id, s.question_id, r.created_at, r.error_type
               FROM runs r JOIN sessions s ON s.id = r.session_id WHERE s.lab_id = ?""", (lab_id,))]
        subs = [dict(r) for r in conn.execute(
            "SELECT student_id, question_id, created_at, passed, total FROM submissions WHERE lab_id = ?", (lab_id,))]
    return score(comp, qids, players(db, lab_id), runs, subs), qids


def can_start_session(db: Database, lab_id: str, student_id: str) -> None:
    """Called by POST /api/sessions: questions of a competition only open while
    the clock runs. Starting one puts the student on the board if they skipped
    the lobby (under their roll number)."""
    comp = get_comp(db, lab_id)
    if comp is None:
        return
    if state_of(comp) != "live":
        raise HTTPException(403, "this competition is not running right now")
    with db.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO competition_players(lab_id, student_id, handle, joined_at) VALUES (?,?,?,?)",
                     (lab_id, student_id, student_id, time.time()))


def on_roster(db: Database, lab_id: str, student_id: str) -> bool:
    return lab_id in {l["id"] for l in db.labs_for_student(student_id)}


def student_card(db: Database, lab, student_id: str) -> dict:
    """What the student's lab list shows for a competition (no question text)."""
    comp = get_comp(db, lab["id"])
    joined = student_id in players(db, lab["id"])
    return {"id": lab["id"], "kind": "competition", "title": lab["title"], "description": lab["description"],
            "state": state_of(comp), "ends_at": comp["ends_at"], "duration_s": comp["duration_s"],
            "n_questions": len(db.lab_questions(lab["id"])), "joined": joined, "questions": []}


# API -------------------------------------------------------------------------

class CompIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    subject: str = Field(default="", max_length=120)
    language: Literal["python", "c", "cpp", "java", "javascript"] = "python"
    duration_min: int | None = Field(default=30, ge=1, le=600)
    board: Literal["top", "all", "hidden"] = "top"


class CompPatch(BaseModel):
    duration_min: int | None = Field(default=None, ge=0, le=600)  # 0 = no clock
    board: Literal["top", "all", "hidden"] | None = None


class JoinIn(BaseModel):
    student_id: str
    handle: str = Field(default="", max_length=24)


class SubmitIn(BaseModel):
    code: str = Field(max_length=200_000)


HANDLE = re.compile(r"^[\w .'-]{2,24}$", re.UNICODE)


def router(db: Database, require_admin: Callable) -> APIRouter:
    ensure_schema(db)
    r = APIRouter()

    def comp_or_404(lab_id: str) -> dict:
        comp = get_comp(db, lab_id)
        if comp is None:
            raise HTTPException(404, "unknown competition")
        return comp

    def teacher_view(lab_id: str) -> dict:
        comp = comp_or_404(lab_id)
        ranked, qids = board(db, comp)
        qs = db.lab_questions(lab_id)
        return {**settings_json(comp), "now": time.time(),
                "questions": [{"id": q["id"], "title": q["title"], "n_tests": len(parse_tests(q["tests_json"]))} for q in qs],
                "roster": db.lab_roster(lab_id),
                "board": [standing_json(p, i + 1, qids, detail=True) for i, p in enumerate(ranked)]}

    def settings_json(comp: dict) -> dict:
        return {"lab_id": comp["lab_id"], "title": comp["title"], "description": comp["description"],
                "status": comp["status"], "state": state_of(comp),
                "duration_min": comp["duration_s"] // 60 if comp["duration_s"] else None,
                "duration_s": comp["duration_s"], "board_mode": comp["board"],
                "started_at": comp["started_at"], "ends_at": comp["ends_at"]}

    admin = [Depends(require_admin)]

    @r.post("/api/teach/competitions", dependencies=admin)
    def create(body: CompIn) -> dict:
        lab_id = "lab_" + uuid.uuid4().hex[:10]
        db.create_lab(lab_id, body.title.strip(), body.description.strip())
        db.update_lab(lab_id, {"subject": body.subject.strip(), "language": body.language})
        with db.connect() as conn:
            conn.execute("UPDATE labs SET kind = 'competition' WHERE id = ?", (lab_id,))
            conn.execute("INSERT INTO competitions(lab_id, duration_s, board) VALUES (?,?,?)",
                         (lab_id, body.duration_min * 60 if body.duration_min else None, body.board))
        return teacher_view(lab_id)

    @r.get("/api/teach/competitions/{lab_id}", dependencies=admin)
    def get(lab_id: str) -> dict:
        return teacher_view(lab_id)

    @r.patch("/api/teach/competitions/{lab_id}", dependencies=admin)
    def patch(lab_id: str, body: CompPatch) -> dict:
        comp = comp_or_404(lab_id)
        sets: dict = {}
        if body.duration_min is not None:
            if comp["started_at"] is not None:
                raise HTTPException(409, "the clock is already running")
            sets["duration_s"] = body.duration_min * 60 or None
        if body.board is not None:
            sets["board"] = body.board
        if sets:
            with db.connect() as conn:
                conn.execute(f"UPDATE competitions SET {', '.join(f'{k} = ?' for k in sets)} WHERE lab_id = ?",
                             (*sets.values(), lab_id))
        return teacher_view(lab_id)

    @r.post("/api/teach/competitions/{lab_id}/start", dependencies=admin)
    def start(lab_id: str) -> dict:
        comp = comp_or_404(lab_id)
        if comp["started_at"] is not None:
            raise HTTPException(409, "already started")
        qs = db.lab_questions(lab_id)
        if not qs:
            raise HTTPException(409, "add at least one question before starting")
        not_ready = [q["title"] for q in qs if competition_ready(dict(q))]
        if not_ready:
            raise HTTPException(409, "competitions are scored on correctness, so every question needs a test case; "
                                     "add tests to: " + ", ".join(not_ready))
        now = time.time()
        db.update_lab(lab_id, {"status": "open"})
        with db.connect() as conn:
            conn.execute("UPDATE competitions SET started_at = ?, ends_at = ? WHERE lab_id = ?",
                         (now, now + comp["duration_s"] if comp["duration_s"] else None, lab_id))
        return teacher_view(lab_id)

    @r.post("/api/teach/competitions/{lab_id}/end", dependencies=admin)
    def end(lab_id: str) -> dict:
        comp = comp_or_404(lab_id)
        if state_of(comp) != "live":
            raise HTTPException(409, "the competition is not running")
        with db.connect() as conn:
            conn.execute("UPDATE competitions SET ends_at = ? WHERE lab_id = ?", (time.time(), lab_id))
        return teacher_view(lab_id)

    def student_or_400(raw: str) -> str:
        sid = raw.strip()
        if not STUDENT_ID.match(sid):
            raise HTTPException(400, "student id must be 1-32 letters, digits, '-' or '_'")
        return sid

    def student_view(comp: dict, sid: str) -> dict:
        lab_id = comp["lab_id"]
        state = state_of(comp)
        ranked, qids = board(db, comp)
        me = next(((i + 1, p) for i, p in enumerate(ranked) if p.student_id == sid), None)
        mode = comp["board"]
        if mode == "all" or (mode == "top" and state != "waiting"):
            shown = ranked if mode == "all" else ranked[:TOP_N]
        else:
            shown = ranked[:TOP_N] if state == "ended" else []
        rows = [standing_json(p, i + 1, qids, detail=False) | {"me": p.student_id == sid} for i, p in enumerate(shown)]
        mine = standing_json(me[1], me[0], qids, detail=True) | {"of": len(ranked)} if me else None
        qs = []
        if state in ("live", "ended"):
            from .teach import question_json  # local import: teach imports this module
            for i, q in enumerate(db.lab_questions(lab_id)):
                d = question_json(q, for_student=True)  # hidden tests stay on the server
                qs.append(d | {"lab_title": comp["title"], "language": comp["language"], "competition": True,
                               "progress": mine["questions"][i] if mine else None})
        return {**settings_json(comp), "now": time.time(), "joined": me is not None, "me": mine,
                "n_players": len(ranked), "board": rows, "questions": qs,
                # in the lobby everyone sees who has arrived, never a ranking
                "lobby": sorted(p.handle for p in ranked) if state == "waiting" else []}

    @r.get("/api/competitions/{lab_id}")
    def view(lab_id: str, student_id: str) -> dict:
        sid = student_or_400(student_id)
        comp = comp_or_404(lab_id)
        if not on_roster(db, lab_id, sid) and state_of(comp) != "ended":
            raise HTTPException(403, "this competition is not open for you")
        return student_view(comp, sid)

    @r.post("/api/competitions/{lab_id}/join")
    def join(lab_id: str, body: JoinIn) -> dict:
        sid = student_or_400(body.student_id)
        comp = comp_or_404(lab_id)
        if not on_roster(db, lab_id, sid):
            raise HTTPException(403, "this competition is not open for you")
        if state_of(comp) not in ("waiting", "live"):
            raise HTTPException(409, "this competition is not taking new players")
        handle = " ".join(body.handle.split()) or sid
        if not HANDLE.match(handle):
            raise HTTPException(400, "pick a name of 2-24 letters, digits, spaces, dots or dashes")
        taken = {h.lower() for s, h in players(db, lab_id).items() if s != sid}
        if handle.lower() in taken:
            raise HTTPException(409, "someone already took that name")
        with db.connect() as conn:
            conn.execute("""INSERT INTO competition_players(lab_id, student_id, handle, joined_at) VALUES (?,?,?,?)
                            ON CONFLICT(lab_id, student_id) DO UPDATE SET handle = excluded.handle""",
                         (lab_id, sid, handle, time.time()))
        return student_view(comp_or_404(lab_id), sid)

    @r.post("/api/sessions/{session_id}/submit")
    def submit(session_id: str, body: SubmitIn) -> dict:
        sess = db.get_session(session_id)
        if sess is None:
            raise HTTPException(404, "unknown session")
        comp = get_comp(db, sess["lab_id"]) if sess["lab_id"] else None
        if comp is None:
            raise HTTPException(400, "this session is not part of a competition")
        if state_of(comp) != "live":
            raise HTTPException(409, "time is up: this competition has ended")
        q = dict(db.get_question(sess["question_id"]))
        graded = grade(q, body.code, comp["language"])
        if not graded or not graded["total"]:
            raise HTTPException(409, "this question has no test cases yet; ask your teacher")
        with db.connect() as conn:
            conn.execute(
                """INSERT INTO submissions(id, lab_id, question_id, student_id, session_id, created_at, code, passed, total)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (uuid.uuid4().hex, comp["lab_id"], q["id"], sess["student_id"], session_id, time.time(), body.code,
                 graded["passed"], graded["total"]))
        view_ = student_view(comp_or_404(comp["lab_id"]), sess["student_id"])
        # grade() already leaves out a hidden test's input and outputs
        results = [{k: r.get(k) for k in ("name", "passed", "hidden", "error_type", "stdout", "expected")}
                   for r in graded["results"]]
        return {"passed": graded["passed"], "total": graded["total"], "results": results, "standing": view_["me"]}

    return r
