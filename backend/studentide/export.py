"""Read recorded sessions for analysis (phase 2 onward).

    python -m studentide.export --db data/studentide.sqlite3 --out export/

writes one JSONL file per session (envelope + payload per line) plus
sessions.json with session metadata. In Python, use load_session() directly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .db import Database


def session_meta(db: Database, session_id: str) -> dict:
    row = db.get_session(session_id)
    if row is None:
        raise KeyError(session_id)
    meta = dict(row)
    meta["client_meta"] = json.loads(meta["client_meta"])
    meta["question_json"] = json.loads(meta["question_json"]) if meta.get("question_json") else None
    return meta


def load_session(db: Database, session_id: str, types: tuple[str, ...] | None = None) -> list[dict]:
    """All events of a session, ordered by seq."""
    return list(db.iter_events(session_id, types))


def export_all(db: Database, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    sessions = []
    for row in db.list_sessions(include_learn=True):  # learning-lab practice too, marked context "learn"
        meta = session_meta(db, row["id"])
        meta["n_events"] = row["n_events"]
        meta["runs"] = [dict(r) for r in db.list_runs(row["id"])]
        sessions.append(meta)
        with open(out / f"{row['id']}.jsonl", "w", encoding="utf-8") as f:
            for ev in db.iter_events(row["id"]):
                f.write(json.dumps(ev) + "\n")
    (out / "sessions.json").write_text(json.dumps(sessions, indent=1), encoding="utf-8")
    return len(sessions)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="data/studentide.sqlite3")
    p.add_argument("--out", default="export")
    a = p.parse_args()
    n = export_all(Database(a.db), Path(a.out))
    print(f"exported {n} sessions to {a.out}")


if __name__ == "__main__":
    main()
