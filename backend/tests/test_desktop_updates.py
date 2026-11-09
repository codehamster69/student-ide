"""Desktop auto-update feed and downloads, served from (fake) GitHub Releases."""

import json

from fastapi.testclient import TestClient

from studentide.app import create_app
from studentide.desktop_updates import Releases

RELEASES = [
    {"tag_name": "desktop-v0.3.0", "draft": False, "prerelease": True, "published_at": "2026-11-09T00:00:00Z", "assets": []},
    {"tag_name": "v9.9.9", "draft": False, "prerelease": False, "published_at": "2026-11-09T00:00:00Z", "assets": []},
    {"tag_name": "desktop-v0.1.0", "draft": False, "prerelease": False, "published_at": "2026-11-01T00:00:00Z", "assets": []},
    {"tag_name": "desktop-v0.2.0", "draft": False, "prerelease": False, "published_at": "2026-11-08T00:00:00Z", "assets": [
        {"name": n, "url": f"https://api.github.com/assets/{i}", "browser_download_url": f"https://github.com/dl/{n}"}
        for i, n in enumerate(["latest.yml", "StudentIDE-0.2.0-win-x64.exe", "StudentIDE-0.2.0-win-x64.exe.blockmap",
                               "StudentIDE-0.2.0-mac-arm64.dmg", "StudentIDE-0.2.0-linux-x86_64.AppImage", "latest-linux.yml"])]},
]


class FakeGitHub:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, follow):
        self.calls.append((url, headers.get("Authorization"), follow))
        if url.endswith("/releases?per_page=30"):
            return 200, {}, json.dumps(RELEASES).encode()
        if url.startswith("https://api.github.com/assets/"):
            return 302, {"Location": f"https://objects.example/signed/{url.rsplit('/', 1)[1]}?sig=x"}, b""
        if url.startswith("https://objects.example/signed/0"):
            return 200, {}, b"version: 0.2.0\npath: StudentIDE-0.2.0-win-x64.exe\n"
        return 404, {}, b""


def client(tmp_path, releases):
    return TestClient(create_app(tmp_path / "u.sqlite3", serve_frontend=False, admin_token="tok", update_releases=releases),
                      follow_redirects=False)


def test_feed_and_signed_redirects(tmp_path):
    gh = FakeGitHub()
    c = client(tmp_path, Releases("owner/repo", "secret", http=gh))
    cfg = c.get("/api/desktop/config").json()
    assert cfg["updates"] is True and cfg["download_url"] == "/api/desktop/download"
    r = c.get("/api/desktop/updates/latest.yml")
    assert r.status_code == 200 and "version: 0.2.0" in r.text  # the newest published desktop-v*, not the pre-release
    r = c.get("/api/desktop/updates/StudentIDE-0.2.0-win-x64.exe.blockmap")
    assert r.status_code == 302 and r.headers["location"].startswith("https://objects.example/signed/2")
    assert all(auth == "Bearer secret" for url, auth, _ in gh.calls if "api.github.com" in url)
    assert c.get("/api/desktop/updates/nope.exe").status_code == 404
    assert c.get("/api/desktop/updates/..%2Fsecret").status_code == 404
    r = c.get("/api/desktop/download?os=mac&arch=x64")  # no x64 dmg: falls back to the arm64 one
    assert r.status_code == 302 and r.headers["location"].endswith("/3?sig=x")
    assert c.get("/api/desktop/download?os=linux").headers["location"].endswith("/4?sig=x")
    n = len(gh.calls)
    c.get("/api/desktop/updates/latest.yml")
    assert sum(1 for u, *_ in gh.calls[n:] if u.endswith("per_page=30")) == 0  # release list is cached


def test_public_repo_needs_no_token(tmp_path):
    c = client(tmp_path, Releases("owner/repo", "", http=FakeGitHub()))
    r = c.get("/api/desktop/download?os=windows")
    assert r.status_code == 302 and r.headers["location"] == "https://github.com/dl/StudentIDE-0.2.0-win-x64.exe"


def test_updates_off(tmp_path, monkeypatch):
    monkeypatch.delenv("STUDENTIDE_UPDATES_REPO", raising=False)
    c = client(tmp_path, None)
    assert c.get("/api/desktop/config").json()["updates"] is False
    assert c.get("/api/desktop/updates/latest.yml").status_code == 404


def test_release_lists_installers_for_the_download_page(tmp_path):
    c = client(tmp_path, Releases("owner/repo", "secret", http=FakeGitHub()))
    info = c.get("/api/desktop/release").json()
    assert info["version"] == "0.2.0"
    assert [(i["os"], i["arch"], i["kind"]) for i in info["installers"]] == [
        ("windows", "x64", "installer"), ("mac", "arm64", "installer"), ("linux", "x64", "installer")]
    win = info["installers"][0]
    assert win["href"] == "/api/desktop/updates/StudentIDE-0.2.0-win-x64.exe"  # not the .blockmap
    assert c.get(win["href"]).status_code == 302
    assert client(tmp_path, None).get("/api/desktop/release").status_code == 404
