"""The code runner as its own small service, for deployments.

Student programs run here, in a container that holds no database, no
secrets and has no route to the internet (see deploy/docker-compose.yml).
The main server sends code over the internal network when
$STUDENTIDE_RUNNER_URL is set (runner.run / runner.run_many).

    uvicorn studentide.runner_service:app --port 8001
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from . import runner

app = FastAPI(title="Student IDE runner")


class RunIn(BaseModel):
    code: str = Field(max_length=300_000)
    language: str = "python"
    inputs: list[str] = Field(default_factory=lambda: [""], max_length=200)


@app.post("/run")
def run(body: RunIn) -> dict:
    return runner.serve_many(body.code, body.language, body.inputs)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "languages": [l["id"] for l in runner.available_languages() if l["available"]]}
