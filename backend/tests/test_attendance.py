"""Attendance from labs (attendance.py): connect Roll Call, attach class groups,
judge effective participation per student and day, send one Roll Call session
per class group, and send automatically when the lab closes."""

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
        ws = self.ws.get(key)
        if ws is None:
            return 401, {"error": "bad key"}
        path = url.split("/api/v1", 1)[1]
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
    r = priya.post(f"/api/teach/labs/{lab['id']}/attendance", json={"day": today()}).json()
    assert all(x["error"] is None for x in r["results"])
    # each class's session went to the Roll Call that holds that class
    assert [s["marks"] for s in rc.ws[KEY_A]["sessions"].values()] == [{"UG23CS001": "A"}]
    assert [s["marks"] for s in rc.ws[KEY_B]["sessions"].values()] == [{"UG23CS002": "P"}]
    assert all(k != KEY_B or c[0] != "PUT" or "/sessions/" in c[1] for c in rc.calls for k in [c[2]])
