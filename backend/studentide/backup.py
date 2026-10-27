"""Database backups: a consistent copy of the SQLite file, gzipped, old ones pruned.

    python -m studentide.backup --db data/studentide.sqlite3 --dir backups            # one backup now
    python -m studentide.backup --db ... --dir ... --every-hours 24 --keep-days 14    # the deploy's backup service

Uses SQLite's online backup API, so it is safe while the server is writing
(copying the file with cp is not). Each backup is checked with
PRAGMA integrity_check before it is kept. Restore (stop the app first):

    python -m studentide.backup --db data/studentide.sqlite3 --restore backups/studentide-20261101-020000.sqlite3.gz

The backups hold the same personal data as the database. Keep them on the
same India-region VM or college storage, never on a personal laptop.
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

PREFIX = "studentide-"


def backup(db_path: str | Path, out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    raw = out_dir / f"{PREFIX}{stamp}.sqlite3"
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    dst = sqlite3.connect(raw)
    try:
        src.backup(dst)
        ok = dst.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        src.close()
        dst.close()
    if ok != "ok":
        raw.unlink(missing_ok=True)
        raise RuntimeError(f"backup failed the integrity check: {ok}")
    gz = raw.with_suffix(".sqlite3.gz")
    with open(raw, "rb") as f, gzip.open(gz, "wb", compresslevel=6) as g:
        shutil.copyfileobj(f, g)
    raw.unlink()
    os.chmod(gz, 0o600)  # personal data: owner only
    return gz


def restore(gz_path: str | Path, db_path: str | Path) -> None:
    """Replace the database's contents with a backup, through SQLite itself, so
    a leftover -wal file cannot bring back the newer data."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "restore.sqlite3"
        with gzip.open(gz_path, "rb") as g, open(raw, "wb") as f:
            shutil.copyfileobj(g, f)
        src = sqlite3.connect(raw)
        dst = sqlite3.connect(db_path, timeout=30)
        try:
            if src.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError(f"{gz_path} is damaged, not restoring it")
            src.backup(dst)
        finally:
            src.close()
            dst.close()


def prune(out_dir: str | Path, keep_days: float, now: float | None = None) -> list[Path]:
    """Delete backups older than keep_days, always keeping the newest one."""
    now = time.time() if now is None else now
    files = sorted(Path(out_dir).glob(f"{PREFIX}*.sqlite3.gz"))
    gone = [f for f in files[:-1] if f.stat().st_mtime < now - keep_days * 86400]
    for f in gone:
        f.unlink()
    return gone


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="data/studentide.sqlite3")
    ap.add_argument("--dir", default="backups")
    ap.add_argument("--keep-days", type=float, default=14)
    ap.add_argument("--every-hours", type=float, default=0, help="keep running, one backup per interval")
    ap.add_argument("--restore", metavar="FILE", help="replace the database with this backup (stop the app first)")
    a = ap.parse_args()
    if a.restore:
        restore(a.restore, a.db)
        print(f"backup: restored {a.db} from {a.restore}")
        return
    while True:
        wait = a.every_hours * 3600
        if Path(a.db).exists():
            try:
                print(f"backup: wrote {backup(a.db, a.dir)}", flush=True)
                for f in prune(a.dir, a.keep_days):
                    print(f"backup: pruned {f.name}", flush=True)
            except Exception as e:
                print(f"backup: FAILED: {e!r}", file=sys.stderr, flush=True)
                if not a.every_hours:
                    sys.exit(1)
        else:
            print(f"backup: no database at {a.db} yet", flush=True)
            wait = min(wait, 300)  # look again soon rather than a day later
        if not a.every_hours:
            return
        time.sleep(wait)


if __name__ == "__main__":
    main()
