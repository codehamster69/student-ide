"""Google sign-in for one college: roles from the address, cookie sessions,
students act only as themselves, teacher screens need a teacher account."""

import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.auth import Config, parse_address, roster_id

DOMAIN = "iiitsurat.ac.in"


def fake_google(credential: str) -> dict:
    """Test stand-in for Google's token check: the credential is 'email[|hd]'."""
    if credential == "forged":
        raise ValueError("bad signature")
    email, _, hd = credential.partition("|")
    return {"email": email, "email_verified": True, "hd": hd or email.split("@")[1], "name": email.split("@")[0]}


@pytest.fixture
def cfg():
    return Config(client_id="test-client", admins=frozenset({"rohan.admin@" + DOMAIN}), secure_cookie=False)


@pytest.fixture
def app(tmp_path, cfg):
    return create_app(tmp_path / "a.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google)


def sign_in(app, email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/google", json={"credential": email})
    assert r.status_code == 200, r.text
    return c


def test_address_pattern():
    cfg = Config(client_id="x")
    s = parse_address("PG25CS07@" + DOMAIN, cfg)
    assert s == {"role": "student", "student_id": "PG25CS07", "program": "PG", "year": 2025, "branch": "CS", "roll": "07"}
    assert parse_address("ui23ccs112@" + DOMAIN, cfg)["role"] == "teacher"  # "ui" is not ug/pg
    assert parse_address("ug23ccs112@" + DOMAIN, cfg)["branch"] == "CCS"
    assert parse_address("ug24ec05@" + DOMAIN, cfg)["student_id"] == "UG24EC05"
    t = parse_address("priya.shah@" + DOMAIN, cfg)
    assert t["role"] == "teacher" and t["student_id"] == "PRIYA_SHAH"
    # a fixed branch list narrows the pattern (matched case-insensitively)
    narrow = Config(client_id="x", branch_codes=("cs", "ec"))
    assert parse_address("Ug24Ec05@" + DOMAIN, narrow)["role"] == "student"
    assert parse_address("ug24me05@" + DOMAIN, narrow)["role"] == "teacher"
    assert roster_id(" pg25cs07@iiitsurat.ac.in ", cfg) == "PG25CS07"
    assert roster_id("pg25cs07", Config(client_id=None)) == "pg25cs07"  # dev mode leaves ids alone


def test_only_college_accounts(app):
    c = TestClient(app)
    assert c.get("/api/auth/config").json() == {"mode": "google", "client_id": "test-client", "domain": DOMAIN,
                                               "live": "editor", "consent_version": 2}
    assert c.post("/api/auth/google", json={"credential": "someone@gmail.com"}).status_code == 403
    # an address on the domain but from another Workspace (hd) is refused too
    assert c.post("/api/auth/google", json={"credential": f"pg25cs07@{DOMAIN}|evil.com"}).status_code == 403
    assert c.post("/api/auth/google", json={"credential": "forged"}).status_code == 401
    assert c.get("/api/me").status_code == 401
    # roll-number sign-in is off in Google mode
    assert c.post("/api/login", json={"student_id": "PG25CS07"}).status_code == 410


def test_student_flow_acts_only_as_self(app):
    c = sign_in(app, "pg25cs07@" + DOMAIN)
    me = c.get("/api/me").json()
    assert me["role"] == "student" and me["student_id"] == "PG25CS07" and me["consented"] is False
    # consent is still asked for, and only for yourself
    assert c.post("/api/consent", json={"student_id": "PG25CS08"}).status_code == 403
    assert c.post("/api/sessions", json={"student_id": "PG25CS07", "task_id": "free"}).status_code == 403
    assert c.post("/api/consent", json={"student_id": "PG25CS07"}).status_code == 200
    assert c.get("/api/me").json()["consented"] is True
    sid = c.post("/api/sessions", json={"student_id": "PG25CS07", "task_id": "free"}).json()["session_id"]
    assert c.post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": []}).status_code == 200
    assert c.get("/api/students/PG25CS08/labs").status_code == 403
    # another student cannot write into this session; nobody signed out can either
    other = sign_in(app, "pg25cs08@" + DOMAIN)
    assert other.post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": []}).status_code == 403
    assert other.post(f"/api/sessions/{sid}/run", json={"code": "print(1)"}).status_code == 403
    assert TestClient(app).post(f"/api/sessions/{sid}/events", json={"schema_version": 1, "events": []}).status_code == 401
    # students never reach the teacher screens
    assert c.get("/api/review/students").status_code == 403
    assert c.get("/api/teach/labs").status_code == 403
    c.post("/api/auth/logout")
    assert c.get("/api/me").status_code == 401


def test_teachers_and_admin_override(app):
    t = sign_in(app, "priya.shah@" + DOMAIN)
    assert t.get("/api/me").json()["role"] == "teacher"
    assert t.get("/api/review/students").status_code == 200
    assert t.get("/api/teach/labs").status_code == 200
    assert t.get("/api/admin/users").status_code == 403

    admin = sign_in(app, "rohan.admin@" + DOMAIN)
    assert admin.get("/api/me").json()["role"] == "admin"
    # a TA with a student address is made a teacher, and keeps it at the next sign-in
    r = admin.put(f"/api/admin/users/ug23cs11@{DOMAIN}", json={"role": "teacher"})
    assert r.status_code == 200 and r.json()["role_source"] == "admin"
    ta = sign_in(app, "ug23cs11@" + DOMAIN)
    assert ta.get("/api/me").json()["role"] == "teacher"
    assert ta.get("/api/teach/labs").status_code == 200
    # demoting a teacher signs them out everywhere
    assert admin.put(f"/api/admin/users/priya.shah@{DOMAIN}", json={"role": "student"}).status_code == 200
    assert t.get("/api/me").status_code == 401
    # dropping the override puts the pattern back
    assert admin.delete(f"/api/admin/users/priya.shah@{DOMAIN}/role").json()["role"] == "teacher"
    assert admin.put("/api/admin/users/x@gmail.com", json={"role": "teacher"}).status_code == 400
    assert admin.put(f"/api/admin/users/rohan.admin@{DOMAIN}", json={"role": "student"}).status_code == 409
    emails = {u["email"] for u in admin.get("/api/admin/users").json()}
    assert {"priya.shah@" + DOMAIN, "ug23cs11@" + DOMAIN, "rohan.admin@" + DOMAIN} <= emails


def test_roster_accepts_addresses(app):
    t = sign_in(app, "priya.shah@" + DOMAIN)
    lab = t.post("/api/teach/labs", json={"title": "Lab 1"}).json()
    r = t.put(f"/api/teach/labs/{lab['id']}/roster", json={"student_ids": ["pg25cs07@" + DOMAIN, "ug24ec05"]})
    assert r.status_code == 200 and r.json()["roster"] == ["PG25CS07", "UG24EC05"]


def test_cookie_is_httponly(tmp_path):
    cfg = Config(client_id="test-client")  # secure cookie by default
    c = TestClient(create_app(tmp_path / "c.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google))
    r = c.post("/api/auth/google", json={"credential": "pg25cs07@" + DOMAIN})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie
