"""Sandbox Labs catalogue: subjects with people and rosters, environments and
recipes, labs of assignments, the student lab definition, and the library."""

import json

import pytest

from studentide import sandbox
from studentide.app import create_app
from studentide.auth import Config

from test_auth import DOMAIN, fake_google, sign_in

PRIYA, MEERA, TARA, ADMIN = (f"{n}@{DOMAIN}" for n in ("priya.shah", "meera.rao", "tara.ta", "rohan.admin"))

C_FILES = [{"path": "main.c", "content": "int main(void){return 0;}\n"},
           {"path": "Makefile", "content": "main: main.c\n\tcc -o main main.c\n"}]
TESTS = {"kind": "io", "cases": [{"name": "one", "stdin": "1\n", "expected": "1\n"},
                                 {"name": "secret", "stdin": "2\n", "expected": "2\n", "hidden": True}]}


@pytest.fixture
def app(tmp_path):
    cfg = Config(client_id="test-client", admins=frozenset({ADMIN}), secure_cookie=False)
    return create_app(tmp_path / "s.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google)


@pytest.fixture
def priya(app):
    return sign_in(app, PRIYA)


def make_subject(c, **kw):
    body = {"title": "Data Structures", "code": "cs201", "semester": "Autumn 2026",
            "recipe": {"base": "c-cpp", "tools": ["valgrind"]}} | kw
    r = c.post("/api/sandbox/subjects", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def make_lab(c, subject_id, n=1):
    lab = c.post(f"/api/sandbox/subjects/{subject_id}/labs", json={"title": "Linked lists"}).json()
    for i in range(n):
        r = c.post(f"/api/sandbox/labs/{lab['id']}/assignments", json={
            "title": f"Part {i + 1}", "statement": "Write **it**.", "files": C_FILES, "open": ["main.c"],
            "run": "make -s && ./main", "tests": TESTS,
            "solution_files": [{"path": "main.c", "content": "/* answer */"}]})
        assert r.status_code == 200, r.text
        lab = r.json()
    return lab


def test_subject_with_new_environment(priya):
    s = make_subject(priya)
    assert s["code"] == "CS201" and s["access"] == "owner" and s["color"] in sandbox.COLORS
    assert s["environment"]["base"] == "c-cpp" and s["environment"]["status"] == "queued"
    envs = priya.get("/api/sandbox/environments").json()
    assert len(envs) == 1 and envs[0]["versions"][0]["size_mb"] > 500
    df = priya.get(f"/api/sandbox/environments/{envs[0]['id']}/versions/1/dockerfile").json()
    assert df["image"].endswith(f"studentide-env:{envs[0]['id']}-1")
    text = df["dockerfile"]
    assert "FROM ubuntu:24.04" in text and "valgrind" in text and "useradd -m -u 1000" in text
    assert 'CMD ["sleep", "infinity"]' in text and "util-linux" in text


def test_recipe_rejects_unsafe_names(priya):
    r = priya.post("/api/sandbox/environments", json={"title": "x", "recipe": {"base": "python", "apt": ["gcc; rm -rf /"]}})
    assert r.status_code == 422
    r = priya.post("/api/sandbox/environments", json={"title": "x", "recipe": {"base": "python", "tools": ["nope"]}})
    assert r.status_code == 422
    r = priya.post("/api/sandbox/environments", json={"title": "x", "recipe": {"base": "python", "resources": {"cpus": 64}}})
    assert r.status_code == 422


def test_dockerfile_quotes_and_setup():
    text = sandbox.dockerfile("env_x", 2, {"base": "python", "tools": ["numpy"], "pip": ["requests==2.32"],
                                           "npm": [], "apt": [], "setup": "echo hi > /etc/motd"})
    assert "pip install --no-cache-dir --break-system-packages numpy requests==2.32" in text
    assert "RUN <<'STUDENTIDE_SETUP'" in text and "echo hi > /etc/motd" in text


def test_raw_dockerfile_needs_admin(app, priya):
    admin = sign_in(app, ADMIN)
    env = priya.post("/api/sandbox/environments", json={"title": "raw", "recipe": {"dockerfile": "FROM alpine\n"}}).json()
    assert env["versions"][0]["status"] == "needs_approval"
    assert priya.post(f"/api/sandbox/environments/{env['id']}/versions/1/approve").status_code == 403
    r = admin.post(f"/api/sandbox/environments/{env['id']}/versions/1/approve")
    assert r.json()["versions"][0]["status"] == "queued" and r.json()["versions"][0]["approved_by"] == ADMIN


def test_build_service_flow(priya, monkeypatch):
    from fastapi.testclient import TestClient
    s = make_subject(priya)
    env_id = s["environment"]["id"]
    anon = TestClient(priya.app)
    assert anon.get("/api/sandbox/builds").status_code == 403  # no token configured
    monkeypatch.setenv("STUDENTIDE_BUILD_TOKEN", "bt")
    assert anon.get("/api/sandbox/builds", headers={"x-build-token": "no"}).status_code == 401
    queued = anon.get("/api/sandbox/builds", headers={"x-build-token": "bt"}).json()
    assert [(b["environment_id"], b["version"]) for b in queued] == [(env_id, 1)] and "FROM ubuntu" in queued[0]["dockerfile"]
    h = {"x-build-token": "bt"}
    assert anon.post(f"/api/sandbox/builds/{env_id}/1", json={"status": "ready"}, headers=h).status_code == 400
    r = anon.post(f"/api/sandbox/builds/{env_id}/1", json={"status": "ready", "digest": "sha256:" + "a" * 64}, headers=h)
    assert r.json()["status"] == "ready"
    assert priya.get(f"/api/sandbox/subjects/{s['id']}").json()["environment"]["status"] == "ready"


def test_stale_building_is_handed_out_again(priya, monkeypatch):
    from fastapi.testclient import TestClient
    s = make_subject(priya)
    env_id, h = s["environment"]["id"], {"x-build-token": "bt"}
    monkeypatch.setenv("STUDENTIDE_BUILD_TOKEN", "bt")
    anon = TestClient(priya.app)
    anon.post(f"/api/sandbox/builds/{env_id}/1", json={"status": "building"}, headers=h)
    assert anon.get("/api/sandbox/builds", headers=h).json() == []  # a builder has it
    now = sandbox._now()
    monkeypatch.setattr(sandbox, "_now", lambda: now + 3 * 3600)  # that builder died
    assert [b["version"] for b in anon.get("/api/sandbox/builds", headers=h).json()] == [1]


def test_build_script_reports_digest_and_failures(priya, monkeypatch):
    """sandbox_build.run_once against the real endpoints, with docker faked."""
    from fastapi.testclient import TestClient
    from studentide import sandbox_build
    s = make_subject(priya)
    other = make_subject(priya, title="Databases", code="cs301", recipe={"base": "databases"})
    monkeypatch.setenv("STUDENTIDE_BUILD_TOKEN", "bt")
    anon = TestClient(priya.app)

    def call(server, token, method, path, body=None):
        r = anon.request(method, path, json=body, headers={"x-build-token": token})
        assert r.status_code == 200, r.text
        return r.json()

    seen = []

    def sh(args, stdin=None, timeout=0):
        seen.append(args)
        if args[:3] == ["docker", "buildx", "build"]:
            if "postgresql" in open(args[-1] + "/Dockerfile").read():
                return 1, "E: boom"
            return 0, "built"
        if args[:3] == ["docker", "image", "inspect"]:
            return 0, "sha256:" + "b" * 64 + "\n"
        return 0, ""  # smoke test passes

    monkeypatch.setattr(sandbox_build, "call", call)
    monkeypatch.setattr(sandbox_build, "sh", sh)
    assert sandbox_build.run_once("http://x", "bt", push=False, platforms="linux/amd64") == 2
    env = lambda sub: priya.get(f"/api/sandbox/subjects/{sub['id']}").json()["environment"]
    assert env(s)["status"] == "ready" and env(other)["status"] == "failed"
    assert any(a[:2] == ["docker", "run"] and sandbox_build.SMOKE in a for a in seen)
    assert anon.get("/api/sandbox/builds", headers={"x-build-token": "bt"}).json() == []


def test_ownership_people_and_tas(app, priya):
    meera, tara, admin = sign_in(app, MEERA), sign_in(app, TARA), sign_in(app, ADMIN)
    s = make_subject(priya)
    sid = s["id"]
    assert meera.get(f"/api/sandbox/subjects/{sid}").status_code == 403
    assert meera.get("/api/sandbox/subjects").json() == []
    assert admin.get(f"/api/sandbox/subjects/{sid}").json()["access"] == "admin"
    r = priya.put(f"/api/sandbox/subjects/{sid}/people", json={"co_teachers": [MEERA.upper()], "tas": [TARA]})
    assert r.json()["co_teachers"] == [MEERA] and r.json()["tas"] == [TARA]
    assert meera.get(f"/api/sandbox/subjects/{sid}").json()["access"] == "co_teacher"
    assert meera.post(f"/api/sandbox/subjects/{sid}/labs", json={"title": "by meera"}).status_code == 200
    assert meera.put(f"/api/sandbox/subjects/{sid}/people", json={}).status_code == 403  # only the owner reshares
    assert tara.get(f"/api/sandbox/subjects/{sid}").json()["access"] == "ta"
    assert tara.post(f"/api/sandbox/subjects/{sid}/labs", json={"title": "by tara"}).status_code == 403
    assert priya.patch(f"/api/sandbox/subjects/{sid}", json={"owner_email": MEERA}).status_code == 403
    assert admin.patch(f"/api/sandbox/subjects/{sid}", json={"owner_email": MEERA}).json()["owner_email"] == MEERA


def test_environment_sharing(app, priya):
    meera = sign_in(app, MEERA)
    s = make_subject(priya)
    env_id = s["environment"]["id"]
    assert meera.get(f"/api/sandbox/environments/{env_id}").status_code == 403
    assert meera.post("/api/sandbox/subjects", json={"title": "Mine", "environment_id": env_id}).status_code == 403
    priya.patch(f"/api/sandbox/environments/{env_id}", json={"shared": True})
    assert meera.post("/api/sandbox/subjects", json={"title": "Mine", "environment_id": env_id}).status_code == 200
    assert meera.post(f"/api/sandbox/environments/{env_id}/versions", json={"recipe": {"base": "c-cpp"}}).status_code == 403
    v2 = priya.post(f"/api/sandbox/environments/{env_id}/versions", json={"recipe": {"base": "c-cpp", "tools": ["gdb"]}})
    assert [v["version"] for v in v2.json()["versions"]] == [1, 2]


def test_roster_ranges_sections_and_addresses(priya):
    s = make_subject(priya)
    r = priya.put(f"/api/sandbox/subjects/{s['id']}/roster", json={
        "text": "A: UG24CS001 to UG24CS003\nB: ug24cs010-ug24cs011, pg25cs07@" + DOMAIN})
    roster = r.json()["roster"]
    assert roster == [{"id": "PG25CS07", "section": "B"}, {"id": "UG24CS001", "section": "A"},
                      {"id": "UG24CS002", "section": "A"}, {"id": "UG24CS003", "section": "A"},
                      {"id": "UG24CS010", "section": "B"}, {"id": "UG24CS011", "section": "B"}]
    assert priya.put(f"/api/sandbox/subjects/{s['id']}/roster", json={"text": "UG24CS009 to UG24CS001"}).status_code == 400


def test_lab_publish_rules_and_definition(app, priya):
    s = make_subject(priya)
    empty = priya.post(f"/api/sandbox/subjects/{s['id']}/labs", json={"title": "Empty"}).json()
    r = priya.patch(f"/api/sandbox/labs/{empty['id']}", json={"status": "published"})
    assert r.status_code == 409 and "assignment" in r.json()["detail"]
    lab = make_lab(priya, s["id"], n=2)
    assert lab["problems"] == [] and lab["version"] == 3
    assert priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"network": "open"}).status_code == 400  # assessed
    r = priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"assessed": False, "network": "open"})
    assert r.json()["network"] == "open"
    pub = priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "published", "min_desktop_version": "0.2.0"}).json()
    assert pub["env_version"] == 1 and pub["status"] == "published"

    d = priya.get(f"/api/sandbox/labs/{lab['id']}/definition").json()
    assert d["format"] == sandbox.FORMAT and d["subject"]["code"] == "CS201"
    assert d["instance"]["name"] == f"sid-{{student}}-{s['id']}" and d["min_desktop_version"] == "0.2.0"
    assert d["environment"]["resources"] == sandbox.DEFAULT_RESOURCES and d["environment"]["digest"] is None
    a = d["assignments"][0]
    assert a["workdir"] == f"/home/student/labs/{lab['id']}/{a['id']}"
    assert a["tests"]["visible"] == [{"name": "one", "stdin": "1\n", "expected": "1\n", "compare": "text"}]
    assert a["tests"]["n_hidden"] == 1 and "solution_files" not in a and "cases" not in a["tests"]
    full = priya.get(f"/api/sandbox/labs/{lab['id']}").json()["definition"]["assignments"][0]
    assert full["solution_files"] and len(full["tests"]["cases"]) == 2

    assert priya.delete(f"/api/sandbox/assignments/{a['id']}").status_code == 409
    assert priya.delete(f"/api/sandbox/labs/{lab['id']}").status_code == 409


def test_student_sees_published_labs_of_their_subjects(app, priya):
    s = make_subject(priya)
    lab = make_lab(priya, s["id"])
    draft = make_lab(priya, s["id"])
    sectioned = make_lab(priya, s["id"])
    priya.put(f"/api/sandbox/subjects/{s['id']}/roster", json={"text": "A: PG25CS07\nB: PG25CS08"})
    priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "published"})
    priya.patch(f"/api/sandbox/labs/{sectioned['id']}", json={"status": "published", "sections": ["b"]})
    student, other = sign_in(app, "pg25cs07@" + DOMAIN), sign_in(app, "pg25cs09@" + DOMAIN)
    mine = student.get("/api/sandbox/my/labs").json()
    assert [g["code"] for g in mine] == ["CS201"] and [l["id"] for l in mine[0]["labs"]] == [lab["id"]]
    d = student.get(f"/api/sandbox/my/labs/{lab['id']}").json()
    assert d["assignments"][0]["tests"]["n_hidden"] == 1 and "solution_files" not in d["assignments"][0]
    assert student.get(f"/api/sandbox/my/labs/{draft['id']}").status_code == 404
    assert student.get(f"/api/sandbox/my/labs/{sectioned['id']}").status_code == 404
    assert other.get("/api/sandbox/my/labs").json() == []
    assert student.get("/api/sandbox/subjects").status_code == 403  # teacher routes stay closed


def test_library_share_use_and_update(app, priya):
    meera = sign_in(app, MEERA)
    s = make_subject(priya)
    lab = make_lab(priya, s["id"])
    assert priya.get("/api/sandbox/library").json() == []
    e = priya.post(f"/api/sandbox/labs/{lab['id']}/share",
                   json={"summary": "Pointers practice", "topics": ["pointers"], "difficulty": "intro"}).json()
    assert e["version"] == 1 and e["base"] == "c-cpp"
    found = meera.get("/api/sandbox/library", params={"q": "pointers"}).json()
    assert [x["id"] for x in found] == [e["id"]]
    assert meera.get("/api/sandbox/library", params={"base": "python"}).json() == []
    mine = meera.post("/api/sandbox/subjects", json={"title": "DSA lab", "recipe": {"base": "c-cpp"}}).json()
    copy = meera.post(f"/api/sandbox/library/{e['id']}/use", json={"subject_id": mine["id"]}).json()
    assert copy["based_on"] == e["id"] and copy["status"] == "draft" and copy["update_available"] is False
    assert copy["definition"]["assignments"][0]["solution_files"]  # solutions travel to teachers
    assert meera.post(f"/api/sandbox/library/{e['id']}/use", json={"subject_id": s["id"]}).status_code == 403
    # the author edits and shares again: the copy is told, and stays independent
    priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"title": "Linked lists v2"})
    priya.post(f"/api/sandbox/labs/{lab['id']}/share", json={"summary": "again"})
    again = meera.get(f"/api/sandbox/labs/{copy['id']}").json()
    assert again["update_available"] is True and again["title"] == "Linked lists"
    priya.delete(f"/api/sandbox/labs/{lab['id']}/share")
    assert meera.get("/api/sandbox/library").json() == []
    assert meera.get(f"/api/sandbox/library/{e['id']}").status_code == 404


def test_copy_subject_for_next_semester(priya):
    s = make_subject(priya)
    lab = make_lab(priya, s["id"], n=2)
    priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "published"})
    new = priya.post(f"/api/sandbox/subjects/{s['id']}/copy", json={"semester": "Winter 2027"}).json()
    assert new["semester"] == "Winter 2027" and new["copied_from"] == s["id"] and new["roster"] == []
    assert [(l["status"], l["n_assignments"]) for l in new["labs"]] == [("draft", 2)]
    assert new["environment"]["id"] == s["environment"]["id"]


def test_dev_mode_student_needs_id(tmp_path):
    from fastapi.testclient import TestClient
    app = create_app(tmp_path / "d.sqlite3", serve_frontend=False, admin_token="tok")
    c = TestClient(app)
    h = {"x-admin-token": "tok"}
    s = c.post("/api/sandbox/subjects", json={"title": "OS", "recipe": {"base": "linux"}}, headers=h).json()
    assert s["access"] == "admin"
    assert c.get("/api/sandbox/my/labs").status_code == 400
    c.put(f"/api/sandbox/subjects/{s['id']}/roster", json={"students": [{"id": "S1"}]}, headers=h)
    assert c.get("/api/sandbox/my/labs", params={"student_id": "S1"}).json() == []


def test_session_per_sandbox_assignment(app, priya):
    """The desktop app records each assignment visited as a session (schema v2 events, sitting id)."""
    s = make_subject(priya)
    lab = make_lab(priya, s["id"], n=2)
    priya.put(f"/api/sandbox/subjects/{s['id']}/roster", json={"text": "PG25CS07"})
    priya.patch(f"/api/sandbox/labs/{lab['id']}", json={"status": "published"})
    a1, a2 = (a["id"] for a in priya.get(f"/api/sandbox/labs/{lab['id']}").json()["definition"]["assignments"])
    student = sign_in(app, "pg25cs07@" + DOMAIN)
    student.post("/api/consent", json={"student_id": "PG25CS07"})
    body = {"student_id": "PG25CS07", "sandbox_lab_id": lab["id"], "sitting_id": "sitting_1234", "client_meta": {}}
    r = student.post("/api/sessions", json=body | {"assignment_id": a1})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["lab_id"] == lab["id"] and out["question_id"] == a1 and out["resume_code"] is None
    ev = [{"seq": 0, "t": 0, "type": "snapshot", "data": {"reason": "start", "text": "int main", "path": "main.c"}},
          {"seq": 1, "t": 5, "type": "key", "data": {"action": "down", "code": "KeyA", "cls": "letter", "surface": "terminal"}},
          {"seq": 2, "t": 9, "type": "term_cmd", "data": {"term_id": "t1", "phase": "start", "command": "make", "cwd": "/home/student"}}]
    r = student.post(f"/api/sessions/{out['session_id']}/events", json={"schema_version": 2, "events": ev})
    assert r.status_code == 200 and not r.json().get("rejected"), r.text
    assert student.post("/api/sessions", json=body | {"assignment_id": a2}).json()["question_id"] == a2
    # not on the roster, another lab's assignment, or a draft: refused
    other = sign_in(app, "pg25cs09@" + DOMAIN)
    other.post("/api/consent", json={"student_id": "PG25CS09"})
    assert other.post("/api/sessions", json=body | {"student_id": "PG25CS09", "assignment_id": a1}).status_code == 403
    draft = make_lab(priya, s["id"])
    d1 = priya.get(f"/api/sandbox/labs/{draft['id']}").json()["definition"]["assignments"][0]["id"]
    assert student.post("/api/sessions", json=body | {"sandbox_lab_id": draft["id"], "assignment_id": d1}).status_code == 403
    assert student.post("/api/sessions", json=body | {"assignment_id": d1}).status_code == 403
    with app.state.db.connect() as conn:
        row = conn.execute("SELECT lab_id, question_id, sitting_id, context, question_json FROM sessions WHERE id = ?",
                           (out["session_id"],)).fetchone()
    assert (row["lab_id"], row["question_id"], row["sitting_id"], row["context"]) == (lab["id"], a1, "sitting_1234", None)
    q = json.loads(row["question_json"])
    assert q["kind"] == "sandbox" and q["main_file"] == "main.c" and q["language"] == "c" and q["subject_code"] == "CS201"
