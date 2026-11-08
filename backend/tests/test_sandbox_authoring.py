"""Lab-wizard extras: grading mode and late policy, the history of changes to
a published lab (with regrade hook and undo), importing and copying
assignments, and "set up by hand" environments."""

import pytest

from studentide.providers.base import Imported
from studentide.sandbox_authoring import (DAY_S, SETUP_HISTORY, SUBMIT_GRACE_S, assignment_from_question,
                                          distill_setup, late_policy, late_summary)

from test_auth import sign_in
from test_previews import env  # noqa: F401  (fixture)
from test_sandbox import PRIYA, app, make_lab, make_subject, priya  # noqa: F401  (fixtures)


def lab_row(status="published", due=1000.0, late=None):
    import json
    return {"status": status, "due_at": due, "late_json": json.dumps(late or {}), "grading_mode": "tests"}


def test_late_policy_modes():
    on_time = 1000 + SUBMIT_GRACE_S
    assert late_policy(lab_row(), on_time) == {"accepted": True, "days_late": 0, "factor": 1.0, "reason": ""}
    assert late_policy(lab_row(due=None), 10**9)["accepted"]
    assert not late_policy(lab_row(), on_time + 1)["accepted"]  # default: closed at the due time
    assert not late_policy(lab_row(status="closed"), 0)["accepted"]
    acc = late_policy(lab_row(late={"mode": "accept"}), on_time + 3 * DAY_S)
    assert acc["accepted"] and acc["days_late"] == 3 and acc["factor"] == 1.0
    pen = {"mode": "penalty", "per_day_pct": 20, "max_days": 2}
    one = late_policy(lab_row(late=pen), on_time + 60)
    assert one["accepted"] and one["days_late"] == 1 and one["factor"] == pytest.approx(0.8)
    assert late_policy(lab_row(late=pen), on_time + 2 * DAY_S)["factor"] == pytest.approx(0.6)
    assert not late_policy(lab_row(late=pen), on_time + 2 * DAY_S + 1)["accepted"]
    assert late_summary({"mode": "penalty", "per_day_pct": 10, "max_days": 0}) == "Late work loses 10% per day."


def test_grading_and_late_in_publish_and_definition(priya):
    s = make_subject(priya)
    lab = make_lab(priya, s["id"])
    assert lab["grading_mode"] == "tests" and lab["late"]["mode"] == "closed"
    r = priya.patch(f"/api/sandbox/labs/{lab['id']}", json={
        "grading_mode": "tests_manual", "late": {"mode": "penalty", "per_day_pct": 15, "max_days": 4}})
    assert r.status_code == 200, r.text
    lab = r.json()
    assert lab["grading_mode"] == "tests_manual" and lab["late"] == {"mode": "penalty", "per_day_pct": 15, "max_days": 4}
    assert lab["late_summary"] == "Late work loses 15% per day, not accepted after 4 days."
    d = priya.get(f"/api/sandbox/labs/{lab['id']}/definition").json()
    assert d["grading"]["mode"] == "tests_manual" and d["grading"]["late"]["per_day_pct"] == 15
    assert priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"grading_mode": "vibes"}).status_code == 422


def test_history_after_publish_with_regrade_and_undo(app, priya):
    calls = []
    app.state.sandbox.on_tests_changed.append(lambda lab_id, a: calls.append((lab_id, a)) or 7)
    s = make_subject(priya)
    lab = make_lab(priya, s["id"])
    aid = lab["definition"]["assignments"][0]["id"]
    priya.patch(f"/api/sandbox/assignments/{aid}", json={"statement": "draft edit"})
    assert priya.get(f"/api/sandbox/labs/{lab['id']}/history").json() == []  # drafts aren't tracked
    priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "published"})
    r = priya.patch(f"/api/sandbox/assignments/{aid}", json={
        "tests": {"kind": "io", "cases": [{"name": "fixed", "stdin": "1\n", "expected": "1"}]}})
    assert "Submissions are graded again with the new tests." in r.json()["effects"]
    r = priya.patch(f"/api/sandbox/assignments/{aid}", json={"files": [{"path": "main.c", "content": "// v2"}]})
    assert any("haven't opened" in e for e in r.json()["effects"])
    h = priya.get(f"/api/sandbox/labs/{lab['id']}/history").json()
    assert [c["summary"] for c in h] == ["Changed the starter files of \u201cPart 1\u201d.",
                                         "Changed the tests of \u201cPart 1\u201d.", "Published to students."]
    assert calls == [(lab["id"], aid)] and h[1]["regraded"] == 7 and h[0]["regraded"] is None
    # undo the starter change: the old files come back, and that is a change too
    r = priya.post(f"/api/sandbox/labs/{lab['id']}/history/{h[0]['id']}/undo")
    assert r.status_code == 200, r.text
    assert r.json()["definition"]["assignments"][0]["files"][0]["content"].startswith("int main")
    assert r.json()["n_changes"] == 4
    assert priya.get(f"/api/sandbox/labs/{lab['id']}/history").json()[0]["summary"].startswith("Undid: ")
    assert priya.post(f"/api/sandbox/labs/{lab['id']}/history/{h[2]['id']}/undo").status_code == 409


def test_failing_regrade_hook_keeps_the_edit(app, priya):
    def boom(lab_id, aid):
        raise RuntimeError("grader down")
    app.state.sandbox.on_tests_changed.append(boom)
    lab = make_lab(priya, make_subject(priya)["id"])
    aid = lab["definition"]["assignments"][0]["id"]
    priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "published"})
    r = priya.patch(f"/api/sandbox/assignments/{aid}", json={"run": "./main"})
    assert r.status_code == 200 and r.json()["definition"]["assignments"][0]["run"] == "./main"


def test_import_question_and_copy(priya):
    s = make_subject(priya)
    lab = make_lab(priya, s["id"])
    r = priya.post(f"/api/sandbox/labs/{lab['id']}/import", json={"provider": "originals", "ref": "c-leap", "language": "c"})
    assert r.status_code == 200, r.text
    got = r.json()
    a = next(x for x in got["definition"]["assignments"] if x["id"] == got["added"])
    assert a["title"] == "Leap Year Detective" and a["files"][0]["path"] == "main.c"
    assert a["run"].startswith("gcc") and a["tests"]["kind"] == "io" and len(a["tests"]["cases"]) >= 3
    assert priya.post(f"/api/sandbox/labs/{lab['id']}/import",
                      json={"provider": "nope", "ref": "x", "language": "c"}).status_code == 404
    # copy from another lab
    other = make_lab(priya, s["id"])
    picks = priya.get("/api/sandbox/assignments").json()
    assert {p["lab_id"] for p in picks} >= {lab["id"], other["id"]}
    r = priya.post(f"/api/sandbox/labs/{other['id']}/assignments/copy", json={"assignment_id": a["id"]})
    assert r.status_code == 200, r.text
    assert [x["title"] for x in r.json()["definition"]["assignments"]] == ["Part 1", "Leap Year Detective"]


def test_copy_needs_access_to_the_source(app, priya):
    s = make_subject(priya)
    lab = make_lab(priya, s["id"])
    aid = lab["definition"]["assignments"][0]["id"]
    meera = sign_in(app, "meera.rao@iiitsurat.ac.in")
    mine = make_lab(meera, make_subject(meera)["id"])
    assert meera.post(f"/api/sandbox/labs/{mine['id']}/assignments/copy", json={"assignment_id": aid}).status_code == 403
    assert all(p["lab_id"] != lab["id"] for p in meera.get("/api/sandbox/assignments").json())


def test_assignment_from_function_question_gets_harness():
    got = Imported(title="Two sum", prompt="Return the indices.", starter_code="def two_sum(a, t):\n    pass\n",
                   tests=[{"stdin": "[[1,2],3]", "expected": "[0,1]", "compare": "json"},
                          {"stdin": "x", "expected": "y", "compare": "checker", "hidden": True}],
                   harness="import json,sys\nprint(json.dumps(two_sum(*json.loads(sys.stdin.read()))))",
                   source={"url": "https://example.org/p/1", "license": "CC BY 4.0"})
    a, notes = assignment_from_question(got, "python")
    assert [f["path"] for f in a["files"]] == ["main.py", ".studentide/harness.py"]
    assert "harness.py" in a["run"] and a["open"] == ["main.py"]
    assert [c["compare"] for c in a["tests"]["cases"]] == ["json", "tokens"] and a["tests"]["cases"][1]["hidden"]
    assert "example.org" in a["statement"] and len(notes) == 2


def test_distill_setup():
    hist = "\n".join(["ls", "sudo apt update", "sudo apt install postgresql", "psql --version", "cd /opt",
                      "sudo apt install postgresql", "cat /etc/os-release", "echo 'x=1' | sudo tee /etc/x.conf",
                      "pip install --break-system-packages pandas", "vim notes.txt", "cat > hello.c", "clear", "cd"])
    out = distill_setup(hist)
    assert out["kept"] == ["apt update", "apt install -y postgresql", "cd /opt", "echo 'x=1' | sudo tee /etc/x.conf",
                           "pip install --break-system-packages pandas", "cat > hello.c"]
    assert "ls" in out["dropped"] and "vim notes.txt" in out["dropped"] and "psql --version" in out["dropped"]
    assert out["script"].splitlines()[1] == "apt install -y postgresql"


def test_set_up_by_hand_preview(env):  # noqa: F811
    app, driver, _ = env
    c = sign_in(app, PRIYA)
    s = make_subject(c)
    env_id = s["environment"]["id"]
    p = c.post("/api/sandbox/previews", json={"environment_id": env_id})
    assert p.status_code == 200, p.text
    p = p.json()
    assert p["status"] == "running" and p["kind"] == "setup" and p["lab"] is None
    files = driver.containers[f"sbxp-{p['id']}"]["files"]
    assert "history -a" in files["/home/student/.bash_profile"]
    assert driver.containers[f"sbxp-{p['id']}"]["spec"]["network"] == "registries"
    assert c.get(f"/api/sandbox/previews/{p['id']}/setup").json()["kept"] == []
    files[SETUP_HISTORY] = "sudo apt-get install -y gdb\nls\n"
    got = c.get(f"/api/sandbox/previews/{p['id']}/setup").json()
    assert got["script"] == "apt-get install -y gdb" and got["environment_id"] == env_id
    # someone else's environment can't be set up by hand
    other = sign_in(app, "meera.rao@iiitsurat.ac.in")
    assert other.post("/api/sandbox/previews", json={"environment_id": env_id}).status_code == 403
