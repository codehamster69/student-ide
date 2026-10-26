"""Teacher authoring: labs (sessions a teacher sets up), their questions, and who
they are assigned to. Mounted by app.py behind the same admin token as the
review timeline.

    GET    /api/teach/labs                       list with counts
    POST   /api/teach/labs                       {title, description}
    GET    /api/teach/labs/{id}                  lab + questions + roster + progress
    PATCH  /api/teach/labs/{id}                  {title?, description?, status?, everyone?}
    DELETE /api/teach/labs/{id}                  only while no session has been recorded
    POST   /api/teach/labs/{id}/questions        {title, prompt, starter_code, sample_input}
    PUT    /api/teach/labs/{id}/order            {question_ids: [...]}
    PUT    /api/teach/labs/{id}/roster           {student_ids: [...], everyone}
    PATCH  /api/teach/questions/{id}             any question field
    DELETE /api/teach/questions/{id}             only while no session has been recorded
    GET    /api/teach/students                   students who have signed in

Recorded sessions keep a copy of the question as the student saw it
(sessions.question_json), so editing a question later never changes what an
old recording was answering.
"""

from __future__ import annotations

import re
import uuid
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .db import Database

STUDENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class LabIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)


class LabPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    status: Literal["draft", "open", "closed"] | None = None
    everyone: bool | None = None


class QuestionIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    prompt: str = Field(default="", max_length=20_000)
    starter_code: str = Field(default="", max_length=50_000)
    sample_input: str = Field(default="", max_length=20_000)


class QuestionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    prompt: str | None = Field(default=None, max_length=20_000)
    starter_code: str | None = Field(default=None, max_length=50_000)
    sample_input: str | None = Field(default=None, max_length=20_000)


class OrderIn(BaseModel):
    question_ids: list[str]


class RosterIn(BaseModel):
    student_ids: list[str] = Field(default_factory=list, max_length=2000)
    everyone: bool = False


def question_json(q) -> dict:
    return {k: q[k] for k in ("id", "lab_id", "position", "title", "prompt", "starter_code", "sample_input", "updated_at")}


def lab_json(lab) -> dict:
    d = dict(lab)
    d["everyone"] = bool(d["everyone"])
    return d


def student_labs(db: Database, student_id: str) -> list[dict]:
    """What a student sees: open labs assigned to them, questions in order,
    and their own progress on each question."""
    out = []
    for lab in db.labs_for_student(student_id):
        done = db.attempts(student_id, lab["id"])
        qs = []
        for q in db.lab_questions(lab["id"]):
            d = question_json(q)
            d.update(lab_title=lab["title"], **done.get(q["id"], {"sessions": 0, "submitted": False}))
            qs.append(d)
        if qs:
            out.append({"id": lab["id"], "title": lab["title"], "description": lab["description"], "questions": qs})
    return out


def router(db: Database, require_admin: Callable) -> APIRouter:
    r = APIRouter(prefix="/api/teach", dependencies=[Depends(require_admin)])

    def lab_or_404(lab_id: str):
        lab = db.get_lab(lab_id)
        if lab is None:
            raise HTTPException(404, "unknown lab")
        return lab

    def question_or_404(question_id: str):
        q = db.get_question(question_id)
        if q is None:
            raise HTTPException(404, "unknown question")
        return q

    def detail(lab_id: str) -> dict:
        lab = lab_json(lab_or_404(lab_id))
        qs = db.lab_questions(lab_id)
        progress = [dict(p) | {"submitted": bool(p["submitted"])} for p in db.lab_progress(lab_id)]
        per_q: dict[str, int] = {}
        for p in progress:
            per_q[p["question_id"]] = per_q.get(p["question_id"], 0) + p["n"]
        lab["questions"] = [question_json(q) | {"n_sessions": per_q.get(q["id"], 0)} for q in qs]
        lab["roster"] = db.lab_roster(lab_id)
        lab["progress"] = progress
        lab["n_sessions"] = sum(per_q.values())
        return lab

    @r.get("/labs")
    def labs() -> list[dict]:
        return [lab_json(l) for l in db.list_labs()]

    @r.post("/labs")
    def create_lab(body: LabIn) -> dict:
        lab_id = "lab_" + uuid.uuid4().hex[:10]
        db.create_lab(lab_id, body.title.strip(), body.description.strip())
        return detail(lab_id)

    @r.get("/labs/{lab_id}")
    def get_lab(lab_id: str) -> dict:
        return detail(lab_id)

    @r.patch("/labs/{lab_id}")
    def patch_lab(lab_id: str, body: LabPatch) -> dict:
        lab_or_404(lab_id)
        fields = body.model_dump(exclude_none=True)
        if fields.get("status") == "open" and not db.lab_questions(lab_id):
            raise HTTPException(409, "add at least one question before opening the lab")
        if "everyone" in fields:
            fields["everyone"] = int(fields["everyone"])
        db.update_lab(lab_id, fields)
        return detail(lab_id)

    @r.delete("/labs/{lab_id}")
    def delete_lab(lab_id: str) -> dict:
        lab_or_404(lab_id)
        if db.count_sessions(lab_id=lab_id):
            raise HTTPException(409, "students have recorded sessions in this lab; close it instead")
        db.delete_lab(lab_id)
        return {"deleted": lab_id}

    @r.post("/labs/{lab_id}/questions")
    def add_question(lab_id: str, body: QuestionIn) -> dict:
        lab_or_404(lab_id)
        qid = "q_" + uuid.uuid4().hex[:10]
        db.add_question(qid, lab_id, body.model_dump() | {"title": body.title.strip()})
        return detail(lab_id)

    @r.put("/labs/{lab_id}/order")
    def reorder(lab_id: str, body: OrderIn) -> dict:
        lab_or_404(lab_id)
        if sorted(body.question_ids) != sorted(q["id"] for q in db.lab_questions(lab_id)):
            raise HTTPException(400, "question_ids must list every question of this lab exactly once")
        db.reorder_questions(lab_id, body.question_ids)
        return detail(lab_id)

    @r.put("/labs/{lab_id}/roster")
    def roster(lab_id: str, body: RosterIn) -> dict:
        lab_or_404(lab_id)
        ids = sorted({s.strip() for s in body.student_ids if s.strip()})
        bad = [s for s in ids if not STUDENT_ID.match(s)]
        if bad:
            raise HTTPException(400, f"not a valid student id: {', '.join(bad[:5])}")
        db.set_roster(lab_id, ids)
        db.update_lab(lab_id, {"everyone": int(body.everyone)})
        return detail(lab_id)

    @r.patch("/questions/{question_id}")
    def patch_question(question_id: str, body: QuestionPatch) -> dict:
        q = question_or_404(question_id)
        db.update_question(question_id, body.model_dump(exclude_none=True))
        return detail(q["lab_id"])

    @r.delete("/questions/{question_id}")
    def delete_question(question_id: str) -> dict:
        q = question_or_404(question_id)
        if db.count_sessions(question_id=question_id):
            raise HTTPException(409, "students have recorded sessions on this question; it can be edited but not removed")
        db.delete_question(question_id)
        return detail(q["lab_id"])

    @r.get("/students")
    def students() -> list[dict]:
        return [{"student_id": s["id"], "consented": s["consented_at"] is not None} for s in db.list_students()]

    return r
