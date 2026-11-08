"""index.html must be revalidated on every load, hashed assets cached for good."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from studentide.app import FrontendFiles


def test_cache_headers(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html>")
    (tmp_path / "assets" / "index-abc.js").write_text("x")
    app = FastAPI()
    app.mount("/", FrontendFiles(directory=tmp_path, html=True))
    c = TestClient(app)
    assert c.get("/").headers["cache-control"] == "no-cache"
    assert c.get("/index.html").headers["cache-control"] == "no-cache"
    assert "immutable" in c.get("/assets/index-abc.js").headers["cache-control"]
    assert "cache-control" not in c.get("/missing.js").headers
