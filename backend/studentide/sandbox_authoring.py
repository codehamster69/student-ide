"""Lab-wizard extras for Sandbox Labs: grading mode and late policy, the
history of changes made to a lab students already have, importing a ready-made
question as an assignment, and turning a teacher's "set up by hand" terminal
session into an environment recipe.

Pure functions only (no routes, no database), so sandbox.py, previews.py and
the grading code (submissions.py) can share them. Format: docs/sandbox-labs.md.
"""

from __future__ import annotations

import json
import math
import re
import shlex

from pydantic import BaseModel, Field

# -- grading mode and late policy

GRADING_MODES = ("tests", "tests_manual", "manual")
GRADING_LABEL = {
    "tests": "Tests only: the score is the share of tests passed",
    "tests_manual": "Tests, then you review and can change the score",
    "manual": "You grade by hand: tests are only a guide",
}
DAY_S = 86_400
SUBMIT_GRACE_S = 120  # same grace as submissions.py: a Submit pressed at the due time still counts


class LatePolicy(BaseModel):
    """What happens to work handed in after the due time.

    closed:  Submit stops at the due time (plus a short grace).
    accept:  late work is taken and marked late, no penalty.
    penalty: late work loses `per_day_pct` percent per started day, and is
             refused after `max_days` days (0 = never refused)."""

    mode: str = Field(default="closed", pattern="^(closed|accept|penalty)$")
    per_day_pct: int = Field(default=10, ge=1, le=100)
    max_days: int = Field(default=3, ge=0, le=60)


def late_of(lab) -> dict:
    """The lab row's late policy as a dict (defaults for labs made before it existed)."""
    raw = lab["late_json"] if "late_json" in lab.keys() else None
    return LatePolicy.model_validate(json.loads(raw) if raw else {}).model_dump()


def grading_of(lab) -> dict:
    mode = (lab["grading_mode"] if "grading_mode" in lab.keys() else None) or "tests"
    return {"mode": mode, "late": late_of(lab)}


def late_policy(lab, submitted_at: float) -> dict:
    """Whether a submission at `submitted_at` is accepted, how many days late it
    is (started days after the grace) and the factor to multiply its score by.
    A lab without a due time is never late. A closed lab takes nothing."""
    if lab["status"] == "closed":
        return {"accepted": False, "days_late": 0, "factor": 0.0, "reason": "the lab is closed"}
    due = lab["due_at"]
    if due is None or submitted_at <= due + SUBMIT_GRACE_S:
        return {"accepted": True, "days_late": 0, "factor": 1.0, "reason": ""}
    days = max(1, math.ceil((submitted_at - due - SUBMIT_GRACE_S) / DAY_S))
    p = late_of(lab)
    if p["mode"] == "closed":
        return {"accepted": False, "days_late": days, "factor": 0.0, "reason": "the due time has passed"}
    if p["mode"] == "accept":
        return {"accepted": True, "days_late": days, "factor": 1.0, "reason": "late"}
    if p["max_days"] and days > p["max_days"]:
        return {"accepted": False, "days_late": days, "factor": 0.0,
                "reason": f"late work is taken for {p['max_days']} day{'s' * (p['max_days'] != 1)} only"}
    return {"accepted": True, "days_late": days, "factor": max(0.0, 1 - days * p["per_day_pct"] / 100),
            "reason": f"late, -{min(100, days * p['per_day_pct'])}%"}


def late_summary(p: dict) -> str:
    """The policy in one sentence, for the publish summary and the student's lab page."""
    if p["mode"] == "closed":
        return "Submissions close at the due time."
    if p["mode"] == "accept":
        return "Late work is accepted and marked late."
    stop = f", not accepted after {p['max_days']} day{'s' * (p['max_days'] != 1)}" if p["max_days"] else ""
    return f"Late work loses {p['per_day_pct']}% per day{stop}."


# -- history of changes to a lab

FIELD_WORDS = {
    "title": "title", "description": "description", "status": "status", "network": "network",
    "assessed": "assessed", "sections_json": "sections", "env_version": "environment version", "opens_at": "open time",
    "due_at": "due time", "min_desktop_version": "app version needed", "grading_mode": "grading",
    "late_json": "late policy", "statement": "statement", "files_json": "starter files", "open_json": "files opened first",
    "run": "Run command", "tests_json": "tests", "solution_json": "reference solution",
}
# Which assignment changes students feel, and how (plan §5.5).
REGRADE_FIELDS = {"tests_json", "run"}          # existing submissions are graded again
NOTE_FIELDS = {"statement", "tests_json", "run"}  # students get a quiet note
STARTER_FIELDS = {"files_json", "open_json"}    # only students who have not opened the assignment get them


def changed(old: dict, new: dict) -> list[str]:
    """Columns of `new` whose value differs from the row `old`."""
    return [k for k, v in new.items() if k in FIELD_WORDS and old[k] != v]


def change_summary(cols: list[str], assignment: str | None = None, status: str | None = None) -> str:
    """One plain sentence for the history list, e.g. 'Fixed the tests of "Insert at head".'"""
    if status == "published":
        return "Published to students."
    if status == "closed":
        return "Closed the lab."
    if status == "draft":
        return "Moved back to draft."
    words = [FIELD_WORDS[c] for c in cols if c in FIELD_WORDS]
    if not words:
        return "Saved without changes."
    what = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    return f"Changed the {what} of “{assignment}”." if assignment else f"Changed the lab's {what}."


# -- importing a ready-made question as an assignment

LANG = {
    # file, run command, run command when the question has a harness appended (as the web grader does)
    "python": ("main.py", "python3 main.py",
               "cat main.py .studentide/harness.py > /tmp/sid-main.py && python3 /tmp/sid-main.py"),
    "c": ("main.c", "gcc -O2 -o main main.c -lm && ./main",
          "cat main.c .studentide/harness.c > /tmp/sid-main.c && gcc -O2 -o /tmp/sid-main /tmp/sid-main.c -lm && /tmp/sid-main"),
    "cpp": ("main.cpp", "g++ -O2 -std=c++17 -o main main.cpp && ./main",
            "cat main.cpp .studentide/harness.cpp > /tmp/sid-main.cpp && g++ -O2 -std=c++17 -o /tmp/sid-main /tmp/sid-main.cpp && /tmp/sid-main"),
    "java": ("Main.java", "javac Main.java && java Main",
             "mkdir -p /tmp/sid && cat Main.java .studentide/harness.java > /tmp/sid/Main.java && javac -d /tmp/sid /tmp/sid/Main.java && java -cp /tmp/sid Main"),
    "javascript": ("main.js", "node main.js",
                   "cat main.js .studentide/harness.js > /tmp/sid-main.js && node /tmp/sid-main.js"),
}
BASE_LANGUAGE = {"c-cpp": "c", "python": "python", "java": "java", "web-node": "javascript"}
EXT = {"python": "py", "c": "c", "cpp": "cpp", "java": "java", "javascript": "js"}


def assignment_from_question(got, language: str) -> tuple[dict, list[str]]:
    """A provider's Imported question -> the dict Store.add_assignment takes, plus
    notes for the teacher about anything that changed on the way."""
    file, run, run_h = LANG[language]
    notes = list(got.notes)
    files = [{"path": file, "content": got.starter_code or ""}]
    if got.harness:
        files.append({"path": f".studentide/harness.{EXT[language]}", "content": got.harness})
        notes.append("This question calls a function: a small test driver is added as .studentide/harness, "
                     "and the Run command joins it to the student's file.")
    cases = []
    for i, t in enumerate(got.tests):
        compare = t.get("compare", "text")
        if compare == "checker":
            compare = "tokens"
        cases.append({"name": t.get("name") or f"Test {i + 1}", "stdin": t.get("stdin", ""),
                      "expected": t.get("expected", ""), "hidden": bool(t.get("hidden")), "compare": compare})
    if any(t.get("compare") == "checker" for t in got.tests):
        notes.append("Some tests accept several right answers; here they compare words and numbers instead. "
                     "Check them before publishing.")
    if not cases:
        notes.append("The source has no tests for this question: add some on the Tests tab.")
    src = got.source or {}
    credit = ""
    if src.get("url") or src.get("attribution"):
        credit = "\n\n---\n*Source: " + " · ".join(x for x in (src.get("attribution"), src.get("url"), src.get("license")) if x) + "*"
    return {
        "title": got.title[:120], "statement": (got.prompt or "") + credit, "files": files, "open": [file],
        "run": run_h if got.harness else run,
        "tests": {"kind": "io", "command": "", "timeout_s": 10, "cases": cases[:200]},
        "solution_files": [],
    }, notes


# -- "set up by hand": the commands a teacher typed become the recipe

SETUP_HISTORY = "/home/student/.studentide-setup-history"
# Put in the preview's home before the terminal opens. bash -l reads ~/.bash_profile
# (then the usual ~/.profile); every command is appended to the history file as soon as it runs.
BASH_PROFILE = f"""# Student IDE "set up by hand": every command you run here is kept for the recipe.
[ -f ~/.profile ] && . ~/.profile
export HISTFILE={SETUP_HISTORY} HISTSIZE=100000 HISTFILESIZE=100000 HISTCONTROL=
shopt -s histappend
PROMPT_COMMAND="history -a${{PROMPT_COMMAND:+; $PROMPT_COMMAND}}"
echo "Set up by hand: install what the subject needs (sudo works). Press Save as environment when you are done."
"""

# Commands that only look around: they change nothing, so the recipe leaves them out.
READ_ONLY = {"ls", "ll", "la", "pwd", "cat", "less", "more", "head", "tail", "man", "help", "which", "whereis", "type",
             "clear", "history", "exit", "logout", "echo", "whoami", "id", "date", "env", "printenv", "df", "du",
             "free", "top", "htop", "ps", "uname", "file", "stat", "tree", "grep", "find", "diff", "wc", "true",
             "apt-cache", "dpkg-query", "lsb_release", "hostname", "uptime", "nproc", "info", "tldr"}
APT_INSTALL = re.compile(r"^(sudo\s+)?(apt|apt-get)\s+(install|upgrade|full-upgrade|dist-upgrade|remove|purge|autoremove)\b")


def _program(cmd: str) -> str:
    try:
        words = shlex.split(cmd, comments=True)
    except ValueError:
        return cmd.split()[0] if cmd.split() else ""
    while words and (words[0] in ("sudo", "time", "nohup") or "=" in words[0] and not words[0].startswith("-")):
        words = words[1:]
    return words[0] if words else ""


def _version_check(cmd: str) -> bool:
    w = cmd.split()
    return len(w) == 2 and w[1] in ("--version", "-v", "-V", "version")


def distill_setup(history: str) -> dict:
    """The teacher's raw shell history -> a setup script that runs as root in the
    image build. Keeps commands that change the system, drops ones that only look
    around, version checks and repeats; `sudo` is dropped (the build is root) and
    apt gets -y (a build cannot answer prompts). Returns {script, kept, dropped}."""
    kept, dropped, seen = [], [], set()
    for raw in history.splitlines():
        cmd = raw.strip()
        if not cmd or cmd.startswith("#"):
            continue
        prog = _program(cmd)
        writes = re.search(r"(^|[^0-9&>])>{1,2}\s*[^&\s]", cmd) or re.search(r"\|\s*(sudo\s+)?tee\b", cmd)
        looks = prog in READ_ONLY or prog in ("vim", "vi", "nano", "emacs") or cmd == "cd" or _version_check(cmd)
        if looks and not writes:
            dropped.append(cmd)
            continue
        if cmd in seen:
            dropped.append(cmd)
            continue
        seen.add(cmd)
        out = re.sub(r"^sudo\s+(-\S+\s+)*", "", cmd)
        if APT_INSTALL.match(out) and not re.search(r"(^|\s)(-y|--yes|--assume-yes)(\s|$)", out):
            out = re.sub(r"^(apt|apt-get)\s+(\S+)", r"\1 \2 -y", out)
        kept.append(out)
    return {"script": "\n".join(kept), "kept": kept, "dropped": dropped}
