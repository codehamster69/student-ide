"""Strict dev/test split by student, and the test-run ledger.

Students, not sessions, are split, so no test student's habits are ever
seen while designing or tuning: ICC weights, the TypeNet-style embedder,
the digraph vocabulary, thresholds h and every hyperparameter come from
dev students only. A student's split is a salted hash of their id, so it
does not depend on who else is in the study or in what order they enrolled,
and adding students later never moves anyone between dev and test.

Inside dev, `folds()` gives cross-fitting folds: population-level pieces
are fitted on k-1 folds and scored on the held-out fold, so dev numbers are
also out-of-sample.

The test split is meant to be scored once per frozen configuration. Every
test run is appended to a ledger (time, git commit, config hash, corpus
fingerprint) so the thesis can state exactly how often the test set was
looked at; running test again on the same corpus and config needs an
explicit reason.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

SALT = "student-ide/v1"
TEST_FRAC = 0.3


def _u(student: str, salt: str) -> float:
    return int(hashlib.sha256(f"{salt}:{student}".encode()).hexdigest()[:12], 16) / 16 ** 12


def assign(students, test_frac: float = TEST_FRAC, salt: str = SALT) -> dict[str, str]:
    """student -> "dev" | "test". Each student independently, by hash."""
    return {s: "test" if _u(s, salt) < test_frac else "dev" for s in students}


def split(students, test_frac: float = TEST_FRAC, salt: str = SALT) -> tuple[list[str], list[str]]:
    a = assign(students, test_frac, salt)
    return sorted(s for s in a if a[s] == "dev"), sorted(s for s in a if a[s] == "test")


def folds(students, k: int = 5, salt: str = SALT) -> list[list[str]]:
    order = sorted(students, key=lambda s: _u(s, salt + "/folds"))
    return [order[i::k] for i in range(k)]


def config_hash(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:12]


def git_state(repo: Path) -> dict:
    def run(*a):
        try:
            return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001 - git missing is fine, the ledger just says so
            return ""
    return {"commit": run("rev-parse", "--short", "HEAD") or "unknown",
            "dirty": bool(run("status", "--porcelain", "--", "backend/studentide"))}


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(ln) for ln in self.path.read_text().splitlines() if ln.strip()]

    def previous(self, fingerprint: str, cfg_hash: str) -> list[dict]:
        return [e for e in self.entries() if e["corpus"] == fingerprint and e["config"] == cfg_hash]

    def record(self, entry: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **entry}
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
