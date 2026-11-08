"""Desktop app: config endpoint and the browser sign-in handoff (one-time code + PKCE)."""

import base64
import hashlib
import secrets

import pytest
from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.auth import COOKIE, Config
from studentide.desktop import challenge_of

from test_auth import DOMAIN, fake_google, sign_in


@pytest.fixture
def app(tmp_path):
    cfg = Config(client_id="test-client", secure_cookie=False)
    return create_app(tmp_path / "d.sqlite3", serve_frontend=False, auth_config=cfg, verify_google=fake_google)


def pkce():
    verifier = secrets.token_urlsafe(48)
    return verifier, base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def test_config(app, monkeypatch):
    c = TestClient(app)
    assert c.get("/api/desktop/config").json() == {"min_version": None, "download_url": None, "sign_in": "browser", "updates": False}
    monkeypatch.setenv("STUDENTIDE_DESKTOP_MIN_VERSION", "0.2.0")
    assert c.get("/api/desktop/config").json()["min_version"] == "0.2.0"


def test_handoff_signs_the_app_in(app):
    browser = sign_in(app, "pg25cs07@" + DOMAIN)
    verifier, challenge = pkce()
    assert challenge_of(verifier) == challenge
    code = browser.post("/api/auth/desktop/grant", json={"challenge": challenge}).json()["code"]

    desktop = TestClient(app)  # a fresh cookie jar: the app's own
    assert desktop.get("/api/me").status_code == 401
    r = desktop.post("/api/auth/desktop/exchange", json={"code": code, "verifier": verifier})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["me"]["student_id"] == "PG25CS07" and body["cookie"]["name"] == COOKIE
    desktop.cookies.set(COOKIE, body["cookie"]["value"])
    assert desktop.get("/api/me").json()["email"] == "pg25cs07@" + DOMAIN
    # the code works once
    assert desktop.post("/api/auth/desktop/exchange", json={"code": code, "verifier": verifier}).status_code == 400


def test_handoff_refuses_wrong_verifier_and_strangers(app):
    assert TestClient(app).post("/api/auth/desktop/grant", json={"challenge": pkce()[1]}).status_code == 401
    browser = sign_in(app, "pg25cs07@" + DOMAIN)
    _, challenge = pkce()
    code = browser.post("/api/auth/desktop/grant", json={"challenge": challenge}).json()["code"]
    other_verifier, _ = pkce()
    r = TestClient(app).post("/api/auth/desktop/exchange", json={"code": code, "verifier": other_verifier})
    assert r.status_code == 400
    # a failed try burns the code too
    assert TestClient(app).post("/api/auth/desktop/exchange", json={"code": code, "verifier": other_verifier}).status_code == 400
    assert browser.post("/api/auth/desktop/grant", json={"challenge": "short"}).status_code == 422


def test_dev_mode_needs_no_handoff(tmp_path):
    c = TestClient(create_app(tmp_path / "dev.sqlite3", serve_frontend=False, admin_token="t"))
    assert c.get("/api/desktop/config").json()["sign_in"] == "in-app"
    assert c.post("/api/auth/desktop/exchange", json={"code": "x" * 20, "verifier": "y" * 43}).status_code == 404
