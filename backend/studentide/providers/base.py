"""The interface every question provider implements, plus a small cached
HTTP helper they share."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Callable, ClassVar, Literal

USER_AGENT = "StudentIDE/0.1 (lab editor for a thesis study; https://github.com/codehamster69/student-ide)"
TIMEOUT_S = 8.0
CACHE_TTL_S = 3600.0


class ProviderError(Exception):
    """Shown to the teacher as is. `status` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


@dataclass
class Category:
    id: str
    label: str
    count: int


@dataclass
class Summary:
    ref: str  # the provider's id for the question (a slug)
    title: str
    difficulty: str = ""
    categories: list[str] = field(default_factory=list)
    blurb: str = ""


@dataclass
class Imported:
    """A fetched question, in the shape of a lab question."""
    title: str
    prompt: str
    starter_code: str = ""
    sample_input: str = ""
    tests: list[dict] = field(default_factory=list)
    harness: str = ""
    source: dict = field(default_factory=dict)  # provider, ref, url, license, attribution, fetched_at
    notes: list[str] = field(default_factory=list)  # what could not be imported, for the teacher

    def as_dict(self) -> dict:
        return asdict(self)


class Provider:
    id: ClassVar[str]
    name: ClassVar[str]
    # "live": browse and import through an official or openly licensed source.
    # "link_only": no permitted source; the teacher can record a link and type the question themselves.
    status: ClassVar[Literal["live", "link_only"]]
    about: ClassVar[str]  # one or two sentences shown in the picker
    terms_url: ClassVar[str] = ""
    hosts: ClassVar[tuple[str, ...]] = ()  # for link_only: hostnames a source link may point at

    def info(self) -> dict:
        return {"id": self.id, "name": self.name, "status": self.status, "about": self.about,
                "terms_url": self.terms_url, "hosts": list(self.hosts)}

    def categories(self, language: str) -> list[Category]:
        raise ProviderError(f"{self.name} questions cannot be browsed here", 409)

    def search(self, language: str, category: str | None = None, query: str = "") -> list[Summary]:
        raise ProviderError(f"{self.name} questions cannot be browsed here", 409)

    def fetch(self, language: str, ref: str) -> Imported:
        raise ProviderError(f"{self.name} questions cannot be imported here", 409)


Fetcher = Callable[[str], bytes | None]  # url -> body, None on 404


def http_get(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise ProviderError(f"the question source answered {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderError("could not reach the question source; check the server's internet access") from e


class Cached:
    """Live fetches with a short in-memory cache, so browsing a list does not
    refetch the same index on every click. Questions are still fetched at the
    moment the teacher picks them."""

    def __init__(self, fetch: Fetcher = http_get, ttl: float = CACHE_TTL_S):
        self.fetch, self.ttl = fetch, ttl
        self._cache: dict[str, tuple[float, bytes | None]] = {}

    def get(self, url: str, fresh: bool = False) -> bytes | None:
        hit = self._cache.get(url)
        if hit and not fresh and time.time() - hit[0] < self.ttl:
            return hit[1]
        body = self.fetch(url)
        self._cache[url] = (time.time(), body)
        return body

    def text(self, url: str, fresh: bool = False) -> str | None:
        b = self.get(url, fresh)
        return None if b is None else b.decode("utf-8", errors="replace")

    def json(self, url: str, fresh: bool = False):
        t = self.text(url, fresh)
        return None if t is None else json.loads(t)
