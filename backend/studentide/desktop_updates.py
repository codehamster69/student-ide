"""Desktop app updates and downloads, served from GitHub Releases through this server.

CI (.github/workflows/desktop.yml, on a `desktop-v*` tag) publishes each desktop
build to a GitHub release of $STUDENTIDE_UPDATES_REPO. The repository is private,
so the app can't read releases itself, and a token inside the app would leak.
Instead the app's updater (electron-updater, "generic" provider) asks the server
it is locked to:

    GET /api/desktop/updates/latest.yml          Windows feed   (latest-mac.yml, latest-linux.yml)
    GET /api/desktop/updates/<file>              302 to a short-lived signed GitHub download URL
    GET /api/desktop/download?os=windows|mac|linux&arch=x64|arm64   the installer, for the update page
    GET /api/desktop/release                     version + installers, for the public #/download page

The feeds are small and copied through; installers never pass through the VM:
the server only asks GitHub for a signed URL (with $STUDENTIDE_UPDATES_TOKEN, a
read-only token for that one repository) and redirects. Unset
$STUDENTIDE_UPDATES_REPO = updates are off (404), and the app says so quietly.
Only the newest published (not draft, not pre-release) `desktop-v*` release is
served. Builds are unsigned for now; see docs/desktop-installer.md (Signing).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, RedirectResponse

TAG_PREFIX = "desktop-v"
CACHE_S = 300
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")
API = "https://api.github.com"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):  # keep the 302 so we can hand its Location on
        return None


class Releases:
    """The newest desktop release of a GitHub repository, cached for CACHE_S."""

    def __init__(self, repo: str, token: str = "", http: Callable[[str, dict, bool], tuple[int, dict, bytes]] | None = None,
                 clock: Callable[[], float] = time.time):
        self.repo, self.token, self.clock = repo, token, clock
        self.http = http or self._http
        self.lock = threading.Lock()
        self._cached: tuple[float, dict | None] = (0.0, None)

    def _headers(self, accept: str) -> dict:
        h = {"Accept": accept, "User-Agent": "studentide-updates", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    @staticmethod
    def _http(url: str, headers: dict, follow: bool) -> tuple[int, dict, bytes]:
        opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(urllib.request.Request(url, headers=headers), timeout=20) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:  # a refused redirect lands here too
            return e.code, dict(e.headers or {}), b""
        except (urllib.error.URLError, TimeoutError) as e:
            raise HTTPException(502, f"GitHub is not reachable ({e})") from e

    def latest(self) -> dict:
        with self.lock:
            at, rel = self._cached
            if rel is not None and self.clock() - at < CACHE_S:
                return rel
            status, _, body = self.http(f"{API}/repos/{self.repo}/releases?per_page=30",
                                        self._headers("application/vnd.github+json"), True)
            if status != 200:
                raise HTTPException(502, f"could not list releases (GitHub answered {status})")
            ok = [r for r in json.loads(body) if r.get("tag_name", "").startswith(TAG_PREFIX)
                  and not r.get("draft") and not r.get("prerelease")]
            if not ok:
                raise HTTPException(404, "no desktop release has been published yet")
            rel = max(ok, key=lambda r: r.get("published_at") or "")
            self._cached = (self.clock(), rel)
            return rel

    def asset(self, name: str) -> dict:
        a = next((a for a in self.latest().get("assets", []) if a["name"] == name), None)
        if a is None:
            raise HTTPException(404, f"{name} is not in the latest desktop release")
        return a

    def signed_url(self, name: str) -> str:
        a = self.asset(name)
        if not self.token:  # a public repository: the plain download link works for everyone
            return a["browser_download_url"]
        status, headers, _ = self.http(a["url"], self._headers("application/octet-stream"), False)
        loc = headers.get("Location") or headers.get("location")
        if status not in (301, 302, 303, 307) or not loc:
            raise HTTPException(502, f"GitHub did not hand out a download link (answered {status})")
        return loc

    def text(self, name: str) -> str:
        status, _, body = self.http(self.signed_url(name), {"User-Agent": "studentide-updates"}, True)
        if status != 200:
            raise HTTPException(502, f"could not fetch {name} (answered {status})")
        return body.decode()

    def installer(self, os_name: str, arch: str) -> str:
        """The file a person downloads by hand: setup .exe, .dmg for the arch, AppImage."""
        names = [a["name"] for a in self.latest().get("assets", [])]
        want = {"windows": (r"-win-x64\.exe$",), "mac": (rf"-mac-{arch}\.dmg$", r"-mac-arm64\.dmg$"),
                "linux": (rf"-linux-{'x86_64' if arch == 'x64' else arch}\.AppImage$", r"\.AppImage$")}[os_name]
        for pattern in want:
            hit = next((n for n in names if re.search(pattern, n)), None)
            if hit:
                return hit
        raise HTTPException(404, f"the latest desktop release has no {os_name} installer")


# What the download page offers, in order: (os, arch, kind, file-name pattern, label, note)
INSTALLERS = [
    ("windows", "x64", "installer", r"-win-x64\.exe$", "Windows", "Installer for Windows 10 and 11 (64-bit)"),
    ("windows", "x64", "portable", r"-portable\.exe$", "Windows, portable", "Runs without installing, for lab PCs; does not update itself"),
    ("mac", "arm64", "installer", r"-mac-arm64\.dmg$", "Mac with Apple silicon", "M1 and newer"),
    ("mac", "x64", "installer", r"-mac-x64\.dmg$", "Mac with Intel", "Older Macs (2020 and before)"),
    ("linux", "x64", "installer", r"-linux-x86_64\.AppImage$", "Linux (AppImage)", "Any 64-bit distribution"),
    ("linux", "x64", "deb", r"\.deb$", "Linux (.deb)", "Ubuntu and Debian"),
]


def release_info(rel: Releases) -> dict:
    """The newest release as the download page shows it; each href is a server link (302 to GitHub)."""
    latest = rel.latest()
    assets = latest.get("assets", [])
    out = []
    for os_name, arch, kind, pattern, label, note in INSTALLERS:
        a = next((a for a in assets if re.search(pattern, a["name"])), None)
        if a:
            out.append({"os": os_name, "arch": arch, "kind": kind, "label": label, "note": note, "file": a["name"],
                        "size": a.get("size"), "href": f"/api/desktop/updates/{a['name']}"})
    return {"version": latest.get("tag_name", "")[len(TAG_PREFIX):], "published_at": latest.get("published_at"),
            "installers": out}


def releases_from_env() -> Releases | None:
    repo = os.environ.get("STUDENTIDE_UPDATES_REPO", "").strip()
    return Releases(repo, os.environ.get("STUDENTIDE_UPDATES_TOKEN", "").strip()) if repo else None


def router(releases: Releases | None) -> APIRouter:
    r = APIRouter(prefix="/api/desktop")

    def on() -> Releases:
        if releases is None:
            raise HTTPException(404, "desktop updates are not set up on this server (STUDENTIDE_UPDATES_REPO)")
        return releases

    @r.get("/updates/{name}")
    def update_file(name: str):
        if not NAME.match(name):
            raise HTTPException(404, "unknown file")
        rel = on()
        if name.endswith(".yml"):
            return PlainTextResponse(rel.text(name), media_type="text/yaml", headers={"Cache-Control": "no-store"})
        return RedirectResponse(rel.signed_url(name), status_code=302)

    @r.get("/release")
    def release():
        return release_info(on())

    @r.get("/download")
    def download(os: str = Query("windows", pattern="^(windows|mac|linux)$"), arch: str = Query("x64", pattern="^(x64|arm64)$")):
        rel = on()
        return RedirectResponse(rel.signed_url(rel.installer(os, arch)), status_code=302)

    r.releases = releases
    return r
