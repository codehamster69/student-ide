import gzip
import os
import sqlite3
import time

from studentide.backup import backup, prune
from studentide.db import Database


def test_backup_is_a_consistent_copy_and_old_ones_are_pruned(tmp_path):
    db = Database(tmp_path / "live.sqlite3")
    db.get_or_create_student("PG25CS07")
    gz = backup(db.path, tmp_path / "b")
    restored = tmp_path / "restored.sqlite3"
    restored.write_bytes(gzip.decompress(gz.read_bytes()))
    assert sqlite3.connect(restored).execute("SELECT id FROM students").fetchall() == [("PG25CS07",)]

    old = tmp_path / "b" / "studentide-20200101-000000.sqlite3.gz"
    old.write_bytes(b"")
    os.utime(old, (time.time() - 30 * 86400,) * 2)
    assert prune(tmp_path / "b", keep_days=14) == [old]
    assert gz.exists()


def test_restore_replaces_newer_data(tmp_path):
    from studentide.backup import restore

    db = Database(tmp_path / "live.sqlite3")
    db.get_or_create_student("BEFORE")
    gz = backup(db.path, tmp_path / "b")
    db.get_or_create_student("AFTER")
    restore(gz, db.path)
    assert [r["id"] for r in db.list_students()] == ["BEFORE"]
