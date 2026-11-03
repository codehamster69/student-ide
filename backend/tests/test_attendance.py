"""Attendance from labs (attendance.py): connect Roll Call, attach class groups,
judge effective participation per student and day, send one Roll Call session
per class group, and send automatically when the lab closes."""

import hashlib
import json
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.auth import Config

from test_auth import DOMAIN, fake_google, sign_in
from test_live import ev, open_lab, start

TOKEN = "t" * 24
ADMIN = {"x-admin-token": TOKEN}
KEY_A = "a" * 40
KEY_B = "b" * 40


class FakeRollCall:
    """Just enough of Roll Call's /api/v1 to test against, one workspace per sync key."""

    def __init__(self):
        self.ws = {KEY_A: {"classes": {}, "sessions": {}, "subjects": []}, KEY_B: {"classes": {}, "sessions": {}, "subjects": []}}
        self.calls = []
        self.down = False
        self.codes = []  # (kind, key) behind each one-time sign-in link
        self.moved = {}  # sha256 of a new key -> the register waiting for it (POST /rotate)
        self.retired = set()

    def add_class(self, key, branch, section, group, prefix, start, end, digits=3):
        cid = str(uuid.uuid4())
        students = [f"{prefix}{str(r).zfill(digits)}" for r in range(start, end + 1)]
        self.ws[key]["classes"][cid] = {"id": cid, "branch": branch, "section": section, "group": group,
                                        "label": " · ".join(x for x in (branch, section, group) if x), "students": students}
        return cid

    def __call__(self, method, url, key, body):
        self.calls.append((method, url, key, body))
        if self.down:
            from studentide.attendance import RollCallError
            raise RollCallError("Roll Call is not reachable (test)")
        path = url.split("/api/v1", 1)[1]
        if key.startswith("st_"):  # a student key only asks for its own sign-in link
            if path == "/login-codes" and method == "POST":
                self.codes.append(("student", key))
                return 200, {"code": f"s{len(self.codes)}", "kind": "student"}
            return 401, {"error": "student keys open only /me"}
        if key in self.retired:
            return 410, {"error": "replaced", "replaced": True}
        h = hashlib.sha256(key.encode()).hexdigest()
        if key not in self.ws and h in self.moved:
            self.ws[key] = self.moved.pop(h)
        if key not in self.ws and key != "z" * 40 and len(key) >= 32:  # Roll Call makes a workspace for any new key
            self.ws[key] = {"classes": {}, "sessions": {}, "subjects": []}
        ws = self.ws.get(key)
        if ws is None:
            return 401, {"error": "bad key"}
        if path == "/login-codes" and method == "POST":
            self.codes.append(("teacher", key) + ((body["label"],) if body and body.get("label") else ()))
            return 200, {"code": f"t{len(self.codes)}", "kind": "teacher"}
        if path == "/rotate" and method == "POST":
            self.moved[body["new_workspace"]] = self.ws.pop(key)
            self.retired.add(key)
            return 200, {"ok": True, "moved": {"classes": len(ws["classes"]), "sessions": len(ws["sessions"])}}
        if path == "/viewers" and method == "PUT":
            ws.setdefault("viewers", {})[body["viewer_hash"]] = body["student_id"]
            return 200, {"ok": True}
        if path == "" and method == "GET":
            return 200, {"ok": True, "classes": len(ws["classes"])}
        if path == "/classes" and method == "GET":
            return 200, list(ws["classes"].values())
        if path == "/classes" and method == "POST":
            g = body["roster"]["groups"][0]
            cid = self.add_class(key, body["branch"], body["section"], body["group"], g["prefix"], g["start"], g["end"], g["digits"])
            return 201, ws["classes"][cid]
        if path == "/subjects":
            if method == "POST":
                ws["subjects"].append(body)
            return 200, ws["subjects"]
        if path.startswith("/sessions/") and method == "PUT":
            if body["classId"] not in ws["classes"]:
                return 404, {"error": "no such class"}
            ws["sessions"][path.split("/")[-1]] = body
            return 200, body
        return 404, {"error": "not found"}


@pytest.fixture
def rc():
    return FakeRollCall()


@pytest.fixture
def client(tmp_path, rc):
    return TestClient(create_app(tmp_path / "a.sqlite3", admin_token=TOKEN, serve_frontend=False, attendance_transport=rc))


def typed(seq, t_ms, text, pos=0, origin="input.type"):
    return ev(seq, "edit", {"origin": origin, "changes": [[pos, pos, text]], "len_before": pos, "len_after": pos + len(text)}, t=t_ms)


def work(client, sid, minutes, chars_per_minute=10, origin="input.type", run=False):
    """`minutes` distinct active minutes of typing (or pasting), one edit per minute."""
    events, pos = [ev(0, "session_start", {"wall_clock_ms": 0}, t=0)], 0
    for m in range(minutes):
        events.append(typed(m + 1, m * 60_000 + 1000, "x" * chars_per_minute, pos, origin))
        pos += chars_per_minute
    r = client.post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": events})
    assert r.json()["rejected"] == [], r.text
    if run:
        client.post(f"/api/sessions/{sid}/run", json={"code": "print(1)\n", "stdin": ""})


def today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()


def test_connect_attach_preview_send(client, rc):
    assert client.get("/api/teach/attendance", headers=ADMIN).json()["connected"] is False
    assert client.get("/api/teach/attendance/classes", headers=ADMIN).status_code == 409
    assert client.put("/api/teach/attendance", json={"sync_key": "z" * 40}, headers=ADMIN).status_code == 400
    r = client.put("/api/teach/attendance", json={"sync_key": KEY_A}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["connected"] is True
    assert "sync_key" not in json.dumps(r.json())  # the key never goes back to a browser

    g1 = rc.add_class(KEY_A, "CSE", "A", "G1", "UG23CS", 1, 3)
    made = client.post("/api/teach/attendance/classes", headers=ADMIN, json={
        "branch": "CSE", "section": "a", "group": "g2", "groups": [{"prefix": "ug23cs", "start": 4, "end": 5, "digits": 3}]})
    assert made.status_code == 200 and made.json()["students"] == ["UG23CS004", "UG23CS005"]
    g2 = made.json()["id"]

    lab = open_lab(client, ADMIN, roster=())
    lab_id, qid = lab["id"], lab["questions"][0]["id"]
    r = client.put(f"/api/teach/labs/{lab_id}/classes", json={"class_ids": [g1, g2]}, headers=ADMIN)
    assert [c["label"] for c in r.json()["classes"]] == ["CSE · A · G1", "CSE · A · G2"]
    # attaching puts the classes' students on the lab roster
    assert client.get(f"/api/teach/labs/{lab_id}", headers=ADMIN).json()["roster"] == [f"UG23CS00{i}" for i in range(1, 6)]

    work(client, start(client, "UG23CS001", qid), minutes=12, run=True)        # present
    work(client, start(client, "UG23CS002", qid), minutes=12, origin="input.paste")  # pasted everything: absent
    work(client, start(client, "UG23CS004", qid), minutes=4)                   # too short: absent
    work(client, start(client, "UG23CS005", qid), minutes=10, chars_per_minute=5)  # present in G2
    roster = client.get(f"/api/teach/labs/{lab_id}", headers=ADMIN).json()["roster"]
    client.put(f"/api/teach/labs/{lab_id}/roster", json={"student_ids": roster + ["UG99XX001"]}, headers=ADMIN)
    work(client, start(client, "UG99XX001", qid), minutes=15)                  # on the lab roster, in no class group

    p = client.get(f"/api/teach/labs/{lab_id}/attendance", headers=ADMIN).json()
    assert p["day"] == today() and p["days"] == [today()]
    by = {s["student_id"]: s for c in p["classes"] for s in c["students"]}
    assert by["UG23CS001"]["present"] and by["UG23CS001"]["runs"] == 1 and by["UG23CS001"]["active_minutes"] == 12
    assert not by["UG23CS002"]["present"] and by["UG23CS002"]["typed"] == 0 and by["UG23CS002"]["pasted"] == 120
    assert "typed characters" in by["UG23CS002"]["reason"]
    assert not by["UG23CS004"]["present"] and "4 of 10 active minutes" in by["UG23CS004"]["reason"]
    assert not by["UG23CS003"]["present"] and by["UG23CS003"]["reason"] == "no activity in this lab"
    assert by["UG23CS005"]["present"]
    assert [s["student_id"] for s in p["not_in_any_class"]] == ["UG99XX001"]

    # a teacher override wins over the rule; each student lands in their own class group
    r = client.post(f"/api/teach/labs/{lab_id}/attendance", headers=ADMIN,
                    json={"day": today(), "overrides": {"UG23CS004": "P"}}).json()
    assert [(x["label"], x["present"], x["total"], x["error"]) for x in r["results"]] == [
        ("CSE · A · G1", 1, 3, None), ("CSE · A · G2", 2, 2, None)]
    sessions = rc.ws[KEY_A]["sessions"]
    assert len(sessions) == 2
    g1_marks = next(s for s in sessions.values() if s["classId"] == g1)["marks"]
    assert g1_marks == {"UG23CS001": "P", "UG23CS002": "A", "UG23CS003": "A"}
    sent = next(s for s in sessions.values() if s["classId"] == g2)
    assert sent["marks"] == {"UG23CS004": "P", "UG23CS005": "P"} and sent["date"] == today()
    assert sent["source"]["app"] == "student-ide" and sent["source"]["url"].endswith(f"#/teach/labs/{lab_id}")
    # the override is remembered for the next preview, and re-sending reuses the same Roll Call ids
    p = client.get(f"/api/teach/labs/{lab_id}/attendance", headers=ADMIN).json()
    assert next(s for c in p["classes"] for s in c["students"] if s["student_id"] == "UG23CS004")["override"] == "P"
    client.post(f"/api/teach/labs/{lab_id}/attendance", headers=ADMIN, json={"day": today()})
    assert len(rc.ws[KEY_A]["sessions"]) == 2

    # closing the lab sends nothing more: today was already sent
    n = len(rc.calls)
    closed = client.patch(f"/api/teach/labs/{lab_id}", json={"status": "closed"}, headers=ADMIN).json()
    assert closed["attendance_sent"] == [] and len(rc.calls) == n


def test_closing_the_lab_sends_automatically(client, rc):
    client.put("/api/teach/attendance", json={"sync_key": KEY_A}, headers=ADMIN)
    g1 = rc.add_class(KEY_A, "CSE", "B", "", "UG23CS", 1, 2)
    lab = open_lab(client, ADMIN, roster=())
    client.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [g1]}, headers=ADMIN)
    work(client, start(client, "UG23CS001", lab["questions"][0]["id"]), minutes=11)
    closed = client.patch(f"/api/teach/labs/{lab['id']}", json={"status": "closed"}, headers=ADMIN).json()
    [day] = closed["attendance_sent"]
    assert day["day"] == today() and day["results"][0]["present"] == 1
    assert list(rc.ws[KEY_A]["sessions"].values())[0]["marks"] == {"UG23CS001": "P", "UG23CS002": "A"}


def test_rule_is_configurable_and_auto_send_can_be_off(client, rc):
    client.put("/api/teach/attendance", json={"sync_key": KEY_A}, headers=ADMIN)
    g1 = rc.add_class(KEY_A, "CSE", "C", "", "UG23CS", 1, 1)
    lab = open_lab(client, ADMIN, roster=())
    lab_id = lab["id"]
    client.put(f"/api/teach/labs/{lab_id}/classes", json={"class_ids": [g1]}, headers=ADMIN)
    work(client, start(client, "UG23CS001", lab["questions"][0]["id"]), minutes=5)
    present = lambda: client.get(f"/api/teach/labs/{lab_id}/attendance", headers=ADMIN).json()["classes"][0]["students"][0]["present"]
    assert present() is False
    r = client.put(f"/api/teach/labs/{lab_id}/attendance/rule", headers=ADMIN,
                   json={"min_active_minutes": 5, "min_typed_chars": 40, "require_run": False, "auto_send": False})
    assert r.json()["rule"]["min_active_minutes"] == 5 and r.json()["auto_send"] is False
    assert present() is True
    client.put(f"/api/teach/labs/{lab_id}/attendance/rule", headers=ADMIN,
               json={"min_active_minutes": 5, "min_typed_chars": 40, "require_run": True, "auto_send": False})
    assert present() is False  # never ran
    assert client.patch(f"/api/teach/labs/{lab_id}", json={"status": "closed"}, headers=ADMIN).json()["attendance_sent"] == []
    assert rc.ws[KEY_A]["sessions"] == {}


def test_learning_lab_and_previews_never_count(client, rc):
    client.put("/api/teach/attendance", json={"sync_key": KEY_A}, headers=ADMIN)
    g1 = rc.add_class(KEY_A, "CSE", "D", "", "UG23CS", 1, 1)
    lab = open_lab(client, ADMIN, roster=())
    client.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [g1]}, headers=ADMIN)
    sid = start(client, "UG23CS001", lab["questions"][0]["id"])
    work(client, sid, minutes=12)
    db = client.app.state.db
    with db.connect() as conn:
        conn.execute("UPDATE sessions SET context = 'learn' WHERE id = ?", (sid,))
    p = client.get(f"/api/teach/labs/{lab['id']}/attendance", headers=ADMIN).json()
    assert p["days"] == [] and p["classes"][0]["students"][0]["present"] is False


def test_failed_send_is_recorded_and_closing_still_works(client, rc):
    client.put("/api/teach/attendance", json={"sync_key": KEY_A}, headers=ADMIN)
    g1 = rc.add_class(KEY_A, "CSE", "E", "", "UG23CS", 1, 1)
    lab = open_lab(client, ADMIN, roster=())
    client.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [g1]}, headers=ADMIN)
    work(client, start(client, "UG23CS001", lab["questions"][0]["id"]), minutes=12)
    rc.down = True
    r = client.patch(f"/api/teach/labs/{lab['id']}", json={"status": "closed"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert "not reachable" in r.json()["attendance_sent"][0]["results"][0]["error"]
    rc.down = False
    info = client.get(f"/api/teach/labs/{lab['id']}/classes", headers=ADMIN).json()
    assert info["sent"][0]["error"]
    r = client.post(f"/api/teach/labs/{lab['id']}/attendance", json={"day": today()}, headers=ADMIN).json()
    assert r["results"][0]["error"] is None and len(rc.ws[KEY_A]["sessions"]) == 1


def test_each_teacher_uses_their_own_roll_call(tmp_path, rc):
    cfg = Config(client_id="test-client", secure_cookie=False)
    app = create_app(tmp_path / "g.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google,
                     attendance_transport=rc)
    priya, meera = sign_in(app, "priya.shah@" + DOMAIN), sign_in(app, "meera.rao@" + DOMAIN)
    priya.put("/api/teach/attendance", json={"sync_key": KEY_A})
    assert meera.get("/api/teach/attendance").json()["connected"] is False
    meera.put("/api/teach/attendance", json={"sync_key": KEY_B})
    ga = rc.add_class(KEY_A, "CSE", "A", "", "UG23CS", 1, 1)
    gb = rc.add_class(KEY_B, "CSE", "B", "", "UG23CS", 2, 2)
    assert [c["id"] for c in meera.get("/api/teach/attendance/classes").json()] == [gb]

    lab = open_lab(priya, roster=())
    priya.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [ga]})
    # meera can't attach to priya's lab, nor attach a class from priya's Roll Call to her own
    assert meera.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [gb]}).status_code == 403
    priya.put(f"/api/teach/labs/{lab['id']}/teachers", json={"co_teachers": ["meera.rao@" + DOMAIN]})
    r = meera.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [ga, gb]})
    assert r.status_code == 200, r.text
    assert {c["attached_by"] for c in r.json()["classes"]} == {"priya.shah@" + DOMAIN, "meera.rao@" + DOMAIN}

    student = sign_in(app, "ug23cs002@" + DOMAIN)
    student.post("/api/consent", json={"student_id": "UG23CS002"})
    sid = student.post("/api/sessions", json={"student_id": "UG23CS002", "question_id": lab["questions"][0]["id"]}).json()["session_id"]
    work(student, sid, minutes=12)
    other = sign_in(app, "ug23cs001@" + DOMAIN)  # in priya's group, works too briefly to count
    other.post("/api/consent", json={"student_id": "UG23CS001"})
    work(other, other.post("/api/sessions", json={"student_id": "UG23CS001", "question_id": lab["questions"][0]["id"]}).json()["session_id"], minutes=2)
    r = priya.post(f"/api/teach/labs/{lab['id']}/attendance", json={"day": today()}).json()
    assert all(x["error"] is None for x in r["results"])
    # each class's session went to the Roll Call that holds that class
    assert [s["marks"] for s in rc.ws[KEY_A]["sessions"].values()] == [{"UG23CS001": "A"}]
    assert [s["marks"] for s in rc.ws[KEY_B]["sessions"].values()] == [{"UG23CS002": "P"}]
    assert all(k != KEY_B or c[0] != "PUT" or "/sessions/" in c[1] for c in rc.calls for k in [c[2]])


def test_student_ide_makes_each_teachers_key_and_signs_them_in(tmp_path, rc):
    cfg = Config(client_id="test-client", secure_cookie=False)
    app = create_app(tmp_path / "k.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google,
                     attendance_transport=rc)
    priya, meera = sign_in(app, "priya.shah@" + DOMAIN), sign_in(app, "meera.rao@" + DOMAIN)
    assert priya.get("/api/teach/attendance/key").status_code == 404
    # one press: a new key (a new, empty Roll Call workspace) and a one-time sign-in link
    r = priya.post("/api/teach/attendance/open")
    assert r.status_code == 200 and r.json()["url"].startswith("https://attendance.hokora.xyz/login#code=")
    assert "sync_key" not in r.json()
    key = priya.get("/api/teach/attendance/key").json()["sync_key"]
    assert len(key) == 40 and key in rc.ws and rc.codes[-1] == ("teacher", key)
    conn = priya.get("/api/teach/attendance").json()
    assert conn["connected"] is True and conn["issued"] is True
    # pressing again signs in to the same workspace; a second teacher gets their own
    priya.post("/api/teach/attendance/open")
    assert priya.get("/api/teach/attendance/key").json()["sync_key"] == key
    meera.post("/api/teach/attendance/key")
    other = meera.get("/api/teach/attendance/key").json()["sync_key"]
    assert other != key
    # a teacher who already keeps a register can use that key instead
    meera.put("/api/teach/attendance", json={"sync_key": KEY_B})
    assert meera.get("/api/teach/attendance").json()["issued"] is False
    assert meera.get("/api/teach/attendance/key").json()["sync_key"] == KEY_B
    # students never see a teacher key
    student = sign_in(app, "ug23cs001@" + DOMAIN)
    assert student.get("/api/teach/attendance/key").status_code == 403


def test_students_open_their_own_attendance_read_only(tmp_path, rc):
    cfg = Config(client_id="test-client", secure_cookie=False)
    app = create_app(tmp_path / "s.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google,
                     attendance_transport=rc)
    priya, meera = sign_in(app, "priya.shah@" + DOMAIN), sign_in(app, "meera.rao@" + DOMAIN)
    priya.put("/api/teach/attendance", json={"sync_key": KEY_A})
    meera.put("/api/teach/attendance", json={"sync_key": KEY_B})
    ga = rc.add_class(KEY_A, "CSE", "A", "G1", "UG23CS", 1, 3)
    gb = rc.add_class(KEY_B, "CSE", "A", "", "UG23CS", 1, 6)
    for t, g in ((priya, ga), (meera, gb)):
        lab = open_lab(t, roster=())
        t.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [g]})

    me = sign_in(app, "ug23cs002@" + DOMAIN)
    assert me.get("/api/attendance/UG23CS002").json()["enabled"] is True
    assert me.get("/api/attendance/UG23CS003").status_code == 403  # only yourself
    r = me.post("/api/attendance/UG23CS002/open")
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["key"].startswith("st_") and out["teachers"] == 2 and out["url"].startswith("https://attendance.hokora.xyz/login#code=")
    viewer = hashlib.sha256(out["key"].encode()).hexdigest()
    # both teachers' Roll Calls let this key read UG23CS002's marks, and nothing else was sent
    assert rc.ws[KEY_A]["viewers"] == {viewer: "UG23CS002"} and rc.ws[KEY_B]["viewers"] == {viewer: "UG23CS002"}
    assert rc.codes[-1] == ("student", out["key"])
    assert me.post("/api/attendance/UG23CS002/open").json()["key"] == out["key"]  # the same key every time

    # a student in no attached class group has nothing to open
    lone = sign_in(app, "ug23cs009@" + DOMAIN)
    assert lone.get("/api/attendance/UG23CS009").json()["enabled"] is False
    assert lone.post("/api/attendance/UG23CS009/open").status_code == 404


def test_replacing_the_key_keeps_the_register(client, rc):
    client.post("/api/teach/attendance/key", headers=ADMIN)
    old = client.get("/api/teach/attendance/key", headers=ADMIN).json()["sync_key"]
    g1 = rc.add_class(old, "CSE", "A", "G1", "UG23CS", 1, 3)
    lab = open_lab(client, ADMIN, roster=())
    client.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [g1]}, headers=ADMIN)

    r = client.post("/api/teach/attendance/key/rotate", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["moved"]["classes"] == 1 and r.json()["issued"] is True
    new = client.get("/api/teach/attendance/key", headers=ADMIN).json()["sync_key"]
    assert new != old and len(new) == 40
    # Roll Call only ever saw the new key's hash, and refuses the old key now
    rotate = next(c for c in rc.calls if c[1].endswith("/rotate"))
    assert rotate[2] == old and new not in json.dumps(rotate[3])
    assert rc(("GET"), "http://rc/api/v1", old, None)[0] == 410
    # the same class groups and lab keep working under the new key
    assert [c["id"] for c in client.get("/api/teach/attendance/classes", headers=ADMIN).json()] == [g1]
    work(client, start(client, "UG23CS001", lab["questions"][0]["id"]), minutes=12)
    sent = client.post(f"/api/teach/labs/{lab['id']}/attendance", json={"day": today()}, headers=ADMIN).json()
    assert all(x["error"] is None for x in sent["results"])
    assert list(rc.ws[new]["sessions"].values())[0]["marks"]["UG23CS001"] == "P"


def test_a_key_replaced_elsewhere_says_so(client, rc):
    client.put("/api/teach/attendance", json={"sync_key": KEY_A}, headers=ADMIN)
    rc.retired.add(KEY_A)
    r = client.get("/api/teach/attendance/classes", headers=ADMIN)
    assert r.status_code == 409 and "replaced" in r.json()["detail"]


def test_admins_open_any_teachers_register(tmp_path, rc):
    cfg = Config(client_id="test-client", secure_cookie=False, admins=frozenset({"pg25cs07@" + DOMAIN}))
    app = create_app(tmp_path / "r.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google,
                     attendance_transport=rc)
    priya, meera = sign_in(app, "priya.shah@" + DOMAIN), sign_in(app, "meera.rao@" + DOMAIN)
    admin = sign_in(app, "pg25cs07@" + DOMAIN)
    priya.put("/api/teach/attendance", json={"sync_key": KEY_A})
    meera.post("/api/teach/attendance/key")
    regs = admin.get("/api/teach/attendance/registers").json()
    assert [r["email"] for r in regs] == ["meera.rao@" + DOMAIN, "priya.shah@" + DOMAIN]
    assert "sync_key" not in json.dumps(regs)
    r = admin.post(f"/api/teach/attendance/registers/priya.shah@{DOMAIN}/open")
    assert r.status_code == 200 and "#code=" in r.json()["url"]
    assert rc.codes[-1] == ("teacher", KEY_A, f"priya.shah@{DOMAIN}'s register, opened by admin pg25cs07@{DOMAIN}")
    assert admin.get("/api/teach/attendance/registers").json()[1]["last_opened"] is not None
    # teachers can't list or open each other's registers
    assert meera.get("/api/teach/attendance/registers").status_code == 403
    assert meera.post(f"/api/teach/attendance/registers/priya.shah@{DOMAIN}/open").status_code == 403
    assert admin.post(f"/api/teach/attendance/registers/nobody@{DOMAIN}/open").status_code == 404


def test_one_lab_for_groups_on_different_days(client, rc):
    """G1 sits the lab today, G2 another day: today's send leaves G2 alone."""
    client.put("/api/teach/attendance", json={"sync_key": KEY_A}, headers=ADMIN)
    g1 = rc.add_class(KEY_A, "CSE", "A", "G1", "UG23CS", 1, 2)
    g2 = rc.add_class(KEY_A, "CSE", "A", "G2", "UG23CS", 3, 4)
    lab = open_lab(client, ADMIN, roster=())
    client.put(f"/api/teach/labs/{lab['id']}/classes", json={"class_ids": [g1, g2]}, headers=ADMIN)
    work(client, start(client, "UG23CS001", lab["questions"][0]["id"]), minutes=12)
    p = client.get(f"/api/teach/labs/{lab['id']}/attendance", headers=ADMIN).json()
    assert [c["idle"] for c in p["classes"]] == [False, True]
    r = client.post(f"/api/teach/labs/{lab['id']}/attendance", json={"day": today()}, headers=ADMIN).json()
    assert [x.get("skipped", False) for x in r["results"]] == [False, True]
    assert [s["classId"] for s in rc.ws[KEY_A]["sessions"].values()] == [g1]
    # an override in G2 sends it on purpose (the whole group skipped the lab)
    r = client.post(f"/api/teach/labs/{lab['id']}/attendance", json={"day": today(), "overrides": {"UG23CS003": "A"}},
                    headers=ADMIN).json()
    assert not any(x.get("skipped") for x in r["results"])
    assert sorted(s["classId"] for s in rc.ws[KEY_A]["sessions"].values()) == sorted([g1, g2])


def test_teacher_picks_the_performing_group_when_opening(client, rc):
    client.put("/api/teach/attendance", json={"sync_key": KEY_A}, headers=ADMIN)
    g1 = rc.add_class(KEY_A, "CSE", "A", "G1", "UG23CS", 1, 2)
    g2 = rc.add_class(KEY_A, "CSE", "A", "G2", "UG23CS", 3, 4)
    lab = open_lab(client, ADMIN, roster=())
    lid, qid = lab["id"], lab["questions"][0]["id"]
    client.put(f"/api/teach/labs/{lid}/classes", json={"class_ids": [g1, g2]}, headers=ADMIN)
    client.patch(f"/api/teach/labs/{lid}", json={"status": "draft"}, headers=ADMIN)
    assert client.patch(f"/api/teach/labs/{lid}", json={"status": "open", "performing": ["nope"]}, headers=ADMIN).status_code == 400
    assert client.get(f"/api/teach/labs/{lid}", headers=ADMIN).json()["status"] == "draft"  # nothing changed

    # open for G1: G2's students don't see the lab, G1's do
    client.patch(f"/api/teach/labs/{lid}", json={"status": "open", "performing": [g1]}, headers=ADMIN)
    labs = lambda sid: [l["id"] for l in client.get(f"/api/students/{sid}/labs").json()]
    assert lid in labs("UG23CS001") and lid not in labs("UG23CS003")
    work(client, start(client, "UG23CS001", qid), minutes=12)
    info = client.get(f"/api/teach/labs/{lid}/classes", headers=ADMIN).json()
    assert info["current"]["class_ids"] == [g1] and info["current"]["labels"] == ["CSE · A · G1"]

    # switch to G2 without closing: G1's sitting ends and only G1 is sent
    r = client.patch(f"/api/teach/labs/{lid}", json={"performing": [g2]}, headers=ADMIN).json()
    assert [x["label"] for x in r["attendance_sent"][0]["results"]] == ["CSE · A · G1"]
    assert [s["classId"] for s in rc.ws[KEY_A]["sessions"].values()] == [g1]
    assert lid in labs("UG23CS003") and lid not in labs("UG23CS001")
    work(client, start(client, "UG23CS003", qid), minutes=11)

    # closing ends G2's sitting and sends G2 only; G1's register isn't touched again
    r = client.patch(f"/api/teach/labs/{lid}", json={"status": "closed"}, headers=ADMIN).json()
    assert [x["label"] for x in r["attendance_sent"][0]["results"]] == ["CSE · A · G2"]
    marks = {s["classId"]: s["marks"] for s in rc.ws[KEY_A]["sessions"].values()}
    assert marks == {g1: {"UG23CS001": "P", "UG23CS002": "A"}, g2: {"UG23CS003": "P", "UG23CS004": "A"}}
    sittings = client.get(f"/api/teach/labs/{lid}/classes", headers=ADMIN).json()["sittings"]
    # the first, group-less sitting is open_lab's, before the groups were attached
    assert [s["class_ids"] for s in sittings] == [[], [g1], [g2]] and all(s["closed_at"] for s in sittings)
