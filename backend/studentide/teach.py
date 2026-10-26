"""Teacher authoring: labs (sessions a teacher sets up), their questions, and who
they are assigned to. Mounted by app.py behind the same admin token as the
review timeline.

    GET    /api/teach/labs                       list with counts
    POST   /api/teach/labs                       {title, description}
    GET    /api/teach/labs/{id}                  lab + questions + roster + progress
    PATCH  /api/teach/labs/{id}                  {title?, description?, status?, everyone?}
    DELETE /api/teach/labs/{id}                  only while no session has been recorded
    POST   /api/teach/labs/{id}/questions        {title, prompt, starter_code, sample_input, tests?, harness?}
    POST   /api/teach/labs/{id}/import           {provider, ref}  fetch a platform question now and add it
    POST   /api/teach/labs/{id}/link             {provider, url, title}  for platforms that can only be linked
    PUT    /api/teach/labs/{id}/order            {question_ids: [...]}
    PUT    /api/teach/labs/{id}/roster           {student_ids: [...], everyone}
    PATCH  /api/teach/questions/{id}             any question field
    DELETE /api/teach/questions/{id}             only while no session has been recorded
    POST   /api/teach/questions/{id}/check       {code}  try code (e.g. a model answer) against the tests
    GET    /api/teach/students                   students who have signed in
    GET    /api/teach/languages                  languages a lab can use, and which this server can run
    GET    /api/teach/sources                    question platforms and what each supports
    GET    /api/teach/sources/{p}/categories     ?language=
    GET    /api/teach/sources/{p}/questions      ?language=&category=&q=
    GET    /api/teach/sources/{p}/questions/{ref}?language=   preview, fetched live

Test cases are optional (see grading.py): a lab is about effort, and its
tests are only a self-check. Competitions are scored, so a question in a
competition lab must keep at least one test.

Recorded sessions keep a copy of the question as the student saw it
(sessions.question_json), so editing a question later never changes what an
old recording was answering.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Callable, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import grading, runner
from .db import Database
from .providers import PROVIDERS, ProviderError

Language = Literal["python", "c", "cpp", "java", "javascript"]

STUDENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class LabIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    subject: str = Field(default="", max_length=120)
    language: Language = "python"


class LabPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    status: Literal["draft", "open", "closed"] | None = None
    everyone: bool | None = None
    subject: str | None = Field(default=None, max_length=120)
    language: Language | None = None


class QuestionIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    prompt: str = Field(default="", max_length=20_000)
    starter_code: str = Field(default="", max_length=50_000)
    sample_input: str = Field(default="", max_length=20_000)
    tests: list[grading.TestCase] = Field(default_factory=list, max_length=grading.MAX_TESTS)
    harness: str = Field(default="", max_length=20_000)


class QuestionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    prompt: str | None = Field(default=None, max_length=20_000)
    starter_code: str | None = Field(default=None, max_length=50_000)
    sample_input: str | None = Field(default=None, max_length=20_000)
    tests: list[grading.TestCase] | None = Field(default=None, max_length=grading.MAX_TESTS)
    harness: str | None = Field(default=None, max_length=20_000)


class ImportIn(BaseModel):
    provider: str
    ref: str = Field(min_length=1, max_length=120)


class LinkIn(BaseModel):
    provider: str
    url: str = Field(min_length=8, max_length=500)
    title: str = Field(min_length=1, max_length=120)


class CodeIn(BaseModel):
    code: str = Field(max_length=200_000)


class OrderIn(BaseModel):
    question_ids: list[str]


class RosterIn(BaseModel):
    student_ids: list[str] = Field(default_factory=list, max_length=2000)
    everyone: bool = False


def question_json(q, for_student: bool = False) -> dict:
    """A question row as the API shows it. Students never receive a hidden
    test's input or expected output, only how many hidden tests there are."""
    d = {k: q[k] for k in ("id", "lab_id", "position", "title", "prompt", "starter_code", "sample_input", "harness", "updated_at")}
    tests = grading.parse_tests(q["tests_json"])
    d["source"] = json.loads(q["source_json"]) if q["source_json"] else None
    if for_student:
        d["tests"] = [t for t in tests if not t["hidden"]]
        d["n_hidden_tests"] = len(tests) - len(d["tests"])
        d["n_tests"] = len(tests)
    else:
        d["tests"] = tests
    return d


def question_fields(body: BaseModel, exclude_none: bool) -> dict:
    """Request body -> question columns (tests stored as JSON)."""
    f = body.model_dump(exclude_none=exclude_none)
    if "tests" in f:
        f["tests_json"] = json.dumps(f.pop("tests"))
    return f


def lab_json(lab) -> dict:
    d = dict(lab)
    d["everyone"] = bool(d["everyone"])
    return d


def is_competition(lab) -> bool:
    # Competitions are built in their own thread as labs with kind = 'competition';
    # until that column exists every lab is an ordinary (effort-only) lab.
    return "kind" in lab.keys() and lab["kind"] == "competition"


def student_labs(db: Database, student_id: str) -> list[dict]:
    """What a student sees: open labs assigned to them, questions in order,
    and their own progress on each question."""
    from .compete import student_card  # compete imports question_json from here

    out = []
    for lab in db.labs_for_student(student_id):
        if lab["kind"] == "competition":
            out.append(student_card(db, lab, student_id))
            continue
        done = db.attempts(student_id, lab["id"])
        qs = []
        for q in db.lab_questions(lab["id"]):
            d = question_json(q, for_student=True)
            d.update(lab_title=lab["title"], language=lab["language"], subject=lab["subject"],
                     **done.get(q["id"], {"sessions": 0, "submitted": False}))
            qs.append(d)
        if qs:
            out.append({"id": lab["id"], "kind": "lab", "title": lab["title"], "description": lab["description"],
                        "subject": lab["subject"], "language": lab["language"], "questions": qs})
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
        db.update_lab(lab_id, {"subject": body.subject.strip(), "language": body.language})
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
        if "subject" in fields:
            fields["subject"] = fields["subject"].strip()
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
        db.add_question(qid, lab_id, question_fields(body, False) | {"title": body.title.strip()})
        return detail(lab_id)

    def provider_or_404(provider_id: str):
        p = PROVIDERS.get(provider_id)
        if p is None:
            raise HTTPException(404, "unknown question source")
        return p

    def from_provider(fn):
        try:
            return fn()
        except ProviderError as e:
            raise HTTPException(e.status, str(e)) from e

    @r.post("/labs/{lab_id}/import")
    def import_question(lab_id: str, body: ImportIn) -> dict:
        """Fetch the question from the platform now and copy it into the lab."""
        lab = lab_or_404(lab_id)
        p = provider_or_404(body.provider)
        got = from_provider(lambda: p.fetch(lab["language"], body.ref))
        qid = "q_" + uuid.uuid4().hex[:10]
        db.add_question(qid, lab_id, {
            "title": got.title[:120], "prompt": got.prompt, "starter_code": got.starter_code,
            "sample_input": got.sample_input, "tests_json": json.dumps(got.tests), "harness": got.harness,
            "source_json": json.dumps(got.source | {"notes": got.notes}),
        })
        return detail(lab_id) | {"imported": qid, "notes": got.notes}

    @r.post("/labs/{lab_id}/link")
    def link_question(lab_id: str, body: LinkIn) -> dict:
        """For platforms whose questions can't be fetched: keep the link, the teacher writes the question."""
        lab_or_404(lab_id)
        p = provider_or_404(body.provider)
        url = urlparse(body.url.strip())
        host = (url.hostname or "").lower()
        if url.scheme != "https" or not any(host == h or host.endswith("." + h) for h in p.hosts):
            raise HTTPException(400, f"paste an https link to a {p.name} problem")
        qid = "q_" + uuid.uuid4().hex[:10]
        db.add_question(qid, lab_id, {
            "title": body.title.strip(), "prompt": "", "starter_code": "", "sample_input": "",
            "source_json": json.dumps({"provider": p.id, "url": url.geturl(), "linked_only": True}),
        })
        return detail(lab_id) | {"imported": qid}

    @r.get("/languages")
    def languages() -> list[dict]:
        return runner.available_languages()

    @r.get("/sources")
    def sources() -> list[dict]:
        return [p.info() for p in PROVIDERS.values()]

    @r.get("/sources/{provider_id}/categories")
    def source_categories(provider_id: str, language: Language = "python") -> list[dict]:
        p = provider_or_404(provider_id)
        return [c.__dict__ for c in from_provider(lambda: p.categories(language))]

    @r.get("/sources/{provider_id}/questions")
    def source_questions(provider_id: str, language: Language = "python", category: str | None = None, q: str = "") -> list[dict]:
        p = provider_or_404(provider_id)
        return [s.__dict__ for s in from_provider(lambda: p.search(language, category, q))]

    @r.get("/sources/{provider_id}/questions/{ref}")
    def source_question(provider_id: str, ref: str, language: Language = "python") -> dict:
        p = provider_or_404(provider_id)
        return from_provider(lambda: p.fetch(language, ref)).as_dict()

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
        if body.tests == [] and is_competition(lab_or_404(q["lab_id"])):
            raise HTTPException(409, "competition questions need at least one test case")
        db.update_question(question_id, question_fields(body, True))
        return detail(q["lab_id"])

    @r.post("/questions/{question_id}/check")
    def check_question(question_id: str, body: CodeIn) -> dict:
        """Lets a teacher run a model answer through the tests before students do."""
        q = question_or_404(question_id)
        lab = lab_or_404(q["lab_id"])
        graded = grading.grade(question_json(q), body.code, lab["language"])
        if graded is None:
            raise HTTPException(409, "this question has no test cases")
        return graded

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
