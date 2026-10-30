"""The learning lab: always-open lessons that explain a concept next to code
the student can change and run.

Lessons are Markdown files in the repo, one folder per track:

    learn/<track>/track.json        {"title", "language", "summary", "level", "order"}
    learn/<track>/NN-slug.md        one lesson, in file-name order

A lesson file starts with a small front matter block (`title:`, `summary:`)
and is otherwise Markdown, shown as the lesson text. Fenced code blocks in
the lesson's language stay in the text as examples (the student can load one
into the editor). Three kinds of fenced block are taken out of the text:

    ```c starter      the code the editor opens with (default: the first example)
    ```input          sample input put in the Input box
    ```tests          optional exercise tests, one JSON object per line, in the
                      format grading.py uses ({"name", "stdin", "expected",
                      "hidden", "compare"}); with tests the lesson gets Check
    ```c solution     a model answer, never sent to the browser; tests/test_learn.py
                      checks that it passes the tests and the starter does not

Practice here is recorded like any lab (Rohan, 2026-10-30), but every session
is marked `context = 'learn'`. Database.list_sessions leaves those out by
default, so baselines, the detector, review, the live view and the harness
never see them; `python -m studentide.export` includes them for analysis.
Nothing in the learning lab is graded or shown to teachers.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from . import grading, runner
from .db import Database

LESSONS_DIR = Path(__file__).parent / "learn"
CONTEXT = "learn"
PREFIX = "learn:"

_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_FENCE = re.compile(r"^```[ \t]*([\w+#-]*)[ \t]*(\w*)[ \t]*\n(.*?)^```[ \t]*$\n?", re.M | re.S)
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class LessonError(ValueError):
    pass


def parse_lesson(text: str, language: str) -> dict:
    """A lesson file -> {title, summary, prompt, starter_code, sample_input, tests, solution}."""
    text = text.replace("\r\n", "\n")
    m = _FRONT.match(text)
    if not m:
        raise LessonError("missing front matter (---\\ntitle: ...\\n---)")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    if not meta.get("title"):
        raise LessonError("front matter needs a title")
    body = text[m.end():]
    starter = sample = solution = None
    tests: list[dict] = []
    examples: list[str] = []

    def take(f: re.Match) -> str:
        nonlocal starter, sample, solution, tests
        lang, role, code = f.group(1), f.group(2), f.group(3)
        if role == "starter":
            starter = code
            return ""
        if role == "solution":
            solution = code
            return ""
        if lang == "input":
            sample = code
            return ""
        if lang == "tests":
            lines = [l for l in code.splitlines() if l.strip()]
            try:
                tests = grading.parse_tests([json.loads(l) for l in lines])
            except (ValueError, TypeError) as e:
                raise LessonError(f"bad tests block: {e}") from e
            return ""
        if lang == language:
            examples.append(code)
        return f.group(0)

    prompt = _FENCE.sub(take, body).strip() + "\n"
    if starter is None:
        starter = examples[0] if examples else ""
    return {"title": meta["title"], "summary": meta.get("summary", ""), "prompt": prompt,
            "starter_code": starter, "sample_input": sample or "", "tests": tests, "solution": solution}


@lru_cache(maxsize=1)
def tracks() -> list[dict]:
    """Every track with its lessons in order (read once; lessons ship with the app)."""
    out = []
    if not LESSONS_DIR.is_dir():
        return out
    found = [(json.loads((d / "track.json").read_text(encoding="utf-8")), d)
             for d in LESSONS_DIR.iterdir() if d.is_dir() and (d / "track.json").exists()]
    # beginner to advanced: by "order", then folder name
    for info, d in sorted(found, key=lambda x: (x[0].get("order", 99), x[1].name)):
        language = info["language"]
        if language not in runner.LANGUAGES:
            raise LessonError(f"{d.name}: unknown language {language!r}")
        lessons = []
        for i, f in enumerate(sorted(d.glob("*.md"))):
            if not _SLUG.match(f.stem):
                raise LessonError(f"{f}: file names are lower-case-with-dashes")
            try:
                lesson = parse_lesson(f.read_text(encoding="utf-8"), language)
            except LessonError as e:
                raise LessonError(f"{f}: {e}") from e
            lessons.append(lesson | {"id": f"{PREFIX}{d.name}/{f.stem}", "track": d.name, "position": i,
                                     "language": language, "lab_title": info["title"], "harness": ""})
        out.append({"id": d.name, "title": info["title"], "language": language, "level": info.get("level", ""),
                    "summary": info.get("summary", ""), "lessons": lessons})
    return out


def get_lesson(lesson_id: str) -> dict | None:
    for t in tracks():
        for l in t["lessons"]:
            if l["id"] == lesson_id:
                return l
    return None


def for_student(lesson: dict) -> dict:
    """Hidden tests are counted, never sent (same rule as lab questions)."""
    shown = [t for t in lesson["tests"] if not t["hidden"]]
    return {k: v for k, v in lesson.items() if k not in ("tests", "solution")} | {
        "tests": shown, "n_tests": len(lesson["tests"]), "n_hidden_tests": len(lesson["tests"]) - len(shown),
        "lesson": True}


def snapshot(lesson: dict) -> dict:
    """What a learning-lab session stores as its question_json: the lesson as the
    student saw it, tests included, so Run and Check use the lesson's language and tests."""
    return {k: lesson[k] for k in ("id", "title", "starter_code", "sample_input", "tests", "harness", "language")} | {
        "lab_id": None, "track": lesson["track"], "prompt_sha": hash_text(lesson["prompt"])}


def hash_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def progress(db: Database, student_id: str) -> dict[str, dict]:
    """Per lesson: how often the student opened it and whether it is done. A
    lesson with tests is done once a Check passed them all; one without tests
    once the student ran code in it."""
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT s.question_id AS id, COUNT(*) AS sessions,
                      MAX(EXISTS (SELECT 1 FROM checks c WHERE c.session_id = s.id AND c.total > 0 AND c.passed = c.total))
                        AS passed,
                      MAX(EXISTS (SELECT 1 FROM runs r WHERE r.session_id = s.id)) AS ran
               FROM sessions s WHERE s.student_id = ? AND s.context = ? GROUP BY s.question_id""",
            (student_id, CONTEXT)).fetchall()
    return {r["id"]: dict(r) for r in rows}


def student_tracks(db: Database, student_id: str | None) -> list[dict]:
    done = progress(db, student_id) if student_id else {}
    out = []
    for t in tracks():
        lessons = []
        for l in t["lessons"]:
            d = for_student(l)
            p = done.get(l["id"])
            d["sessions"] = p["sessions"] if p else 0
            d["submitted"] = bool(p and (p["passed"] if l["tests"] else p["ran"]))
            lessons.append(d)
        out.append({k: t[k] for k in ("id", "title", "language", "level", "summary")} | {"lessons": lessons})
    return out


def router(db: Database, auth, student_id_check) -> APIRouter:
    """`student_id_check`: the app's roll-number validator."""
    r = APIRouter()

    @r.get("/api/learn")
    def learn(request: Request, student_id: str | None = None) -> list[dict]:
        if student_id is not None:
            student_id = student_id_check(student_id)
            auth.own_student(request, student_id)
        return student_tracks(db, student_id)

    @r.get("/api/learn/lessons/{track}/{slug}")
    def lesson(track: str, slug: str) -> dict:
        l = get_lesson(f"{PREFIX}{track}/{slug}")
        if l is None:
            raise HTTPException(404, "no such lesson")
        return for_student(l)

    return r
