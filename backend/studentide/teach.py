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
    PUT    /api/teach/labs/{id}/teachers         {co_teachers: [...], owner_email?}  share a lab; owner change is admin only
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

Every lab route is limited to the teacher's own and shared labs (see
auth.Auth.check_lab); admins see every lab.

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

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import grading, runner
from .auth import not_yours, parse_address, roster_id
from .db import Database, has_consent
from .providers import PROVIDERS, ProviderError

Language = Literal["python", "c", "cpp", "java", "javascript"]
LabLanguage = Literal["python", "c", "cpp", "java", "javascript", "any"]  # "any": competitions only (grading.ANY)

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
    language: LabLanguage | None = None


class QuestionIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    prompt: str = Field(default="", max_length=20_000)
    starter_code: str = Field(default="", max_length=50_000)
    sample_input: str = Field(default="", max_length=20_000)
    tests: list[grading.TestCase] = Field(default_factory=list, max_length=grading.MAX_TESTS)
    harness: str = Field(default="", max_length=20_000)
    variants: dict[Language, grading.Variant] = Field(default_factory=dict)  # any-language competitions


class QuestionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    prompt: str | None = Field(default=None, max_length=20_000)
    starter_code: str | None = Field(default=None, max_length=50_000)
    sample_input: str | None = Field(default=None, max_length=20_000)
    tests: list[grading.TestCase] | None = Field(default=None, max_length=grading.MAX_TESTS)
    harness: str | None = Field(default=None, max_length=20_000)
    variants: dict[Language, grading.Variant] | None = None


class ImportIn(BaseModel):
    provider: str
    ref: str = Field(min_length=1, max_length=120)


class LinkIn(BaseModel):
    provider: str
    url: str = Field(min_length=8, max_length=500)
    title: str = Field(min_length=1, max_length=120)


class CodeIn(BaseModel):
    code: str = Field(max_length=200_000)
    language: Language | None = None  # any-language competitions: which language the code is in


class OrderIn(BaseModel):
    question_ids: list[str]


class TeachersIn(BaseModel):
    co_teachers: list[str] = Field(default_factory=list, max_length=50)
    owner_email: str | None = None  # admins only; "" leaves the lab with admins


class RosterIn(BaseModel):
    student_ids: list[str] = Field(default_factory=list, max_length=2000)
    everyone: bool = False


def question_json(q, for_student: bool = False) -> dict:
    """A question row as the API shows it. Students never receive a hidden
    test's input or expected output, only how many hidden tests there are."""
    d = {k: q[k] for k in ("id", "lab_id", "position", "title", "prompt", "starter_code", "sample_input", "harness", "updated_at")}
    tests = grading.parse_tests(q["tests_json"])
    d["source"] = json.loads(q["source_json"]) if q["source_json"] else None
    d["variants"] = grading.variants(q)
    if not for_student:  # the checker stays with the teacher and the server, like hidden tests
        d["checker"] = q["checker"] if "checker" in q.keys() else ""
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
    if "variants" in f:
        f["variants_json"] = json.dumps(f.pop("variants"))
    return f


def switch_language(db: Database, lab_id: str, old: str, new: str) -> None:
    """Moving a competition to or from "any language" keeps each question's
    starter code and harness: they become the old language's variant, or the
    new language's variant becomes the question's own."""
    if old == new or grading.ANY not in (old, new):
        return
    for q in db.lab_questions(lab_id):
        vs = grading.variants(q)
        if new == grading.ANY:
            if q["starter_code"] or q["harness"]:
                vs.setdefault(old, {"starter_code": q["starter_code"], "harness": q["harness"]})
            db.update_question(q["id"], {"variants_json": json.dumps(vs), "starter_code": "", "harness": ""})
        elif new in vs:
            db.update_question(q["id"], {"starter_code": vs[new]["starter_code"], "harness": vs[new]["harness"]})


def import_any(p, ref: str) -> tuple:
    """Fetch a platform question for an any-language competition: once per
    language, keeping each language's starter code and harness. The tests come
    from the first language that works; a language whose tests differ is left
    out (its driver could not carry every test), and so is one the source
    cannot serve. Returns (Imported, variants)."""
    base, vs, skipped = None, {}, []
    for lang in grading.LANGUAGES:
        try:
            got = p.fetch(lang, ref)
        except ProviderError:
            skipped.append(lang)
            continue
        if base is None:
            base = got
        elif got.tests != base.tests:
            skipped.append(lang)
            continue
        vs[lang] = {"starter_code": got.starter_code, "harness": got.harness}
    if base is None:
        raise ProviderError("this source could not serve the question in any language", 404)
    if skipped and any(v["harness"] for v in vs.values()):  # plain stdin/stdout tests work in every language anyway
        names = ", ".join(runner.LANGUAGES[l]["label"] for l in skipped)
        base.notes = [*base.notes, f"Students can't answer this one in {names}: the source has no test driver for it there."]
    return base, vs


def lab_json(lab, co_teachers: list[str] | None = None, me=None) -> dict:
    """`me`: the auth.Teacher asking, to say how they reach this lab."""
    d = dict(lab)
    d["everyone"] = bool(d["everyone"])
    d["co_teachers"] = co_teachers or []
    if me is not None:
        d["access"] = ("owner" if me.email and me.email == lab["owner_email"] else
                       "co_teacher" if me.email in d["co_teachers"] else "admin")
    return d


def is_competition(lab) -> bool:
    # Competitions are built in their own thread as labs with kind = 'competition';
    # until that column exists every lab is an ordinary (effort-only) lab.
    return "kind" in lab.keys() and lab["kind"] == "competition"


def student_labs(db: Database, student_id: str, labs: list | None = None) -> list[dict]:
    """What a student sees: open labs assigned to them, questions in order,
    and their own progress on each question. `labs`: the labs to show instead
    of the student's own ("View as student": a teacher's labs, drafts included)."""
    from .compete import student_card  # compete imports question_json from here

    out = []
    for lab in db.labs_for_student(student_id) if labs is None else labs:
        if lab["kind"] == "competition":
            card = student_card(db, lab, student_id)
            # "View as student" lists draft labs, but a competition not set up yet has no student side
            if card["state"] in ("waiting", "live", "ended"):
                out.append(card)
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
                        "subject": lab["subject"], "language": lab["language"], "questions": qs}
                       | ({"draft": True} if lab["status"] == "draft" else {}))
    return out


def router(db: Database, require_admin: Callable, auth, on_lab_closed: Callable | None = None) -> APIRouter:
    """`auth`: an auth.Auth. It limits every lab to its owner, co-teachers and
    admins; in Google mode roster entries may be full addresses and are upper-cased.
    `on_lab_closed(lab_id, request)`: run when a lab is closed (attendance.py sends
    the lab's attendance to Roll Call); its result is returned as `attendance_sent`."""
    r = APIRouter(prefix="/api/teach", dependencies=[Depends(require_admin)])
    auth_cfg = auth.cfg

    def lab_or_404(lab_id: str, request: Request):
        lab = db.get_lab(lab_id)
        if lab is None:
            raise HTTPException(404, "unknown lab")
        auth.check_lab(request, lab_id)
        return lab

    def question_or_404(question_id: str, request: Request):
        q = db.get_question(question_id)
        if q is None:
            raise HTTPException(404, "unknown question")
        auth.check_lab(request, q["lab_id"])
        return q

    def detail(lab_id: str, request: Request) -> dict:
        lab = lab_json(lab_or_404(lab_id, request), db.lab_teachers(lab_id).get(lab_id), auth.teacher(request))
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
    def labs(request: Request) -> list[dict]:
        me, co = auth.teacher(request), db.lab_teachers()
        return [lab_json(l, co.get(l["id"]), me) for l in db.list_labs(auth.lab_ids(request))]

    @r.post("/labs")
    def create_lab(body: LabIn, request: Request) -> dict:
        lab_id = "lab_" + uuid.uuid4().hex[:10]
        db.create_lab(lab_id, body.title.strip(), body.description.strip(), auth.teacher(request).email)
        db.update_lab(lab_id, {"subject": body.subject.strip(), "language": body.language})
        return detail(lab_id, request)

    @r.get("/labs/{lab_id}")
    def get_lab(lab_id: str, request: Request) -> dict:
        return detail(lab_id, request)

    @r.patch("/labs/{lab_id}")
    def patch_lab(lab_id: str, body: LabPatch, request: Request) -> dict:
        lab_or_404(lab_id, request)
        fields = body.model_dump(exclude_none=True)
        if fields.get("status") == "open" and not db.lab_questions(lab_id):
            raise HTTPException(409, "add at least one question before opening the lab")
        if "subject" in fields:
            fields["subject"] = fields["subject"].strip()
        if "everyone" in fields:
            fields["everyone"] = int(fields["everyone"])
        if "language" in fields:
            lab = db.get_lab(lab_id)
            if fields["language"] == grading.ANY and not is_competition(lab):
                raise HTTPException(400, "any language is for competitions; a lab has one language")
            switch_language(db, lab_id, lab["language"], fields["language"])
        was = db.get_lab(lab_id)["status"]
        db.update_lab(lab_id, fields)
        out = detail(lab_id, request)
        if on_lab_closed and fields.get("status") == "closed" and was != "closed":
            try:
                out["attendance_sent"] = on_lab_closed(lab_id, request)
            except HTTPException as e:  # closing the lab never fails because attendance couldn't be sent
                out["attendance_sent"] = [{"error": e.detail}]
        return out

    @r.delete("/labs/{lab_id}")
    def delete_lab(lab_id: str, request: Request) -> dict:
        lab_or_404(lab_id, request)
        if db.count_sessions(lab_id=lab_id):
            raise HTTPException(409, "students have recorded sessions in this lab; close it instead")
        db.delete_preview_sessions(lab_id=lab_id)
        db.delete_lab(lab_id)
        return {"deleted": lab_id}

    @r.post("/labs/{lab_id}/questions")
    def add_question(lab_id: str, body: QuestionIn, request: Request) -> dict:
        lab_or_404(lab_id, request)
        qid = "q_" + uuid.uuid4().hex[:10]
        db.add_question(qid, lab_id, question_fields(body, False) | {"title": body.title.strip()})
        return detail(lab_id, request)

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
    def import_question(lab_id: str, body: ImportIn, request: Request) -> dict:
        """Fetch the question from the platform now and copy it into the lab."""
        lab = lab_or_404(lab_id, request)
        p = provider_or_404(body.provider)
        vs = {}
        if lab["language"] == grading.ANY:
            got, vs = from_provider(lambda: import_any(p, body.ref))
        else:
            got = from_provider(lambda: p.fetch(lab["language"], body.ref))
        qid = "q_" + uuid.uuid4().hex[:10]
        db.add_question(qid, lab_id, {
            "title": got.title[:120], "prompt": got.prompt, "starter_code": "" if vs else got.starter_code,
            "sample_input": got.sample_input, "tests_json": json.dumps(got.tests), "harness": "" if vs else got.harness,
            "checker": got.checker, "variants_json": json.dumps(vs),
            "source_json": json.dumps(got.source | {"notes": got.notes}),
        })
        return detail(lab_id, request) | {"imported": qid, "notes": got.notes}

    @r.post("/labs/{lab_id}/link")
    def link_question(lab_id: str, body: LinkIn, request: Request) -> dict:
        """For platforms whose questions can't be fetched: keep the link, the teacher writes the question."""
        lab_or_404(lab_id, request)
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
        return detail(lab_id, request) | {"imported": qid}

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
    def reorder(lab_id: str, body: OrderIn, request: Request) -> dict:
        lab_or_404(lab_id, request)
        if sorted(body.question_ids) != sorted(q["id"] for q in db.lab_questions(lab_id)):
            raise HTTPException(400, "question_ids must list every question of this lab exactly once")
        db.reorder_questions(lab_id, body.question_ids)
        return detail(lab_id, request)

    @r.put("/labs/{lab_id}/roster")
    def roster(lab_id: str, body: RosterIn, request: Request) -> dict:
        lab_or_404(lab_id, request)
        clean = lambda s: roster_id(s, auth_cfg)
        ids = sorted({clean(s) for s in body.student_ids if s.strip()})
        bad = [s for s in ids if not STUDENT_ID.match(s)]
        if bad:
            raise HTTPException(400, f"not a valid student id: {', '.join(bad[:5])}")
        db.set_roster(lab_id, ids)
        db.update_lab(lab_id, {"everyone": int(body.everyone)})
        return detail(lab_id, request)

    @r.put("/labs/{lab_id}/teachers")
    def teachers(lab_id: str, body: TeachersIn, request: Request) -> dict:
        """Share a lab with co-teachers. The owner and admins can; only an admin
        can hand the lab to another owner (e.g. a lab from before ownership)."""
        lab = lab_or_404(lab_id, request)
        me = auth.teacher(request)
        owner = lab["owner_email"]
        if not me.admin and me.email != owner:
            raise not_yours("only the lab's owner can change who it is shared with")
        if body.owner_email is not None and (body.owner_email.strip().lower() or None) != owner:
            if not me.admin:
                raise not_yours("only an admin can change a lab's owner")
            owner = teacher_address(body.owner_email) if body.owner_email.strip() else None
        co = sorted({teacher_address(e) for e in body.co_teachers if e.strip()} - {owner})
        db.set_lab_teachers(lab_id, co, owner)
        return detail(lab_id, request)

    def teacher_address(raw: str) -> str:
        """A colleague's college address; student addresses are refused."""
        email = raw.strip().lower()
        if email.count("@") != 1 or (auth_cfg.google and not email.endswith("@" + auth_cfg.domain)):
            raise HTTPException(400, f"not a college address: {raw.strip()}")
        user = auth.get_user(email)
        role = user["role"] if user else parse_address(email, auth_cfg)["role"]
        if role == "student":
            raise HTTPException(400, f"{email} is a student account")
        return email

    @r.patch("/questions/{question_id}")
    def patch_question(question_id: str, body: QuestionPatch, request: Request) -> dict:
        q = question_or_404(question_id, request)
        if body.tests == [] and is_competition(lab_or_404(q["lab_id"], request)):
            raise HTTPException(409, "competition questions need at least one test case")
        db.update_question(question_id, question_fields(body, True))
        return detail(q["lab_id"], request)

    @r.post("/questions/{question_id}/check")
    def check_question(question_id: str, body: CodeIn, request: Request) -> dict:
        """Lets a teacher run a model answer through the tests before students do."""
        q = question_or_404(question_id, request)
        lab = lab_or_404(q["lab_id"], request)
        question, language = question_json(q), lab["language"]
        if language == grading.ANY:
            language = body.language or "python"
            if language not in grading.question_languages(q):
                raise HTTPException(400, f"this question has no test driver for {runner.LANGUAGES[language]['label']}")
            question = grading.for_language(question, language)
        graded = grading.grade(question, body.code, language)
        if graded is None:
            raise HTTPException(409, "this question has no test cases")
        return graded

    @r.delete("/questions/{question_id}")
    def delete_question(question_id: str, request: Request) -> dict:
        q = question_or_404(question_id, request)
        if db.count_sessions(question_id=question_id):
            raise HTTPException(409, "students have recorded sessions on this question; it can be edited but not removed")
        db.delete_preview_sessions(question_id=question_id)
        db.delete_question(question_id)
        return detail(q["lab_id"], request)

    @r.get("/students")
    def students() -> list[dict]:
        return [{"student_id": s["id"], "consented": has_consent(s)} for s in db.list_students()]

    return r
