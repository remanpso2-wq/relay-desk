"""Create a consistent SQLite snapshot and prove it can be restored.
No source modifications and no persistent backup files. Use only test data.
"""

import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path


def fingerprint(conn):
    result = {}
    names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for name in names:
        quoted = '"' + name.replace('"', '""') + '"'
        rows = conn.execute("SELECT * FROM " + quoted).fetchall()
        encoded = sorted(
            json.dumps(row, ensure_ascii=False, default=str) for row in rows
        )
        result[name] = {
            "rows": len(rows),
            "sha256": hashlib.sha256("\n".join(encoded).encode()).hexdigest(),
        }
    return result


def verify(source):
    source = Path(source).resolve(strict=True)
    with tempfile.TemporaryDirectory() as directory:
        snapshot = Path(directory) / "snapshot.db"
        restored = Path(directory) / "restored.db"
        with (
            sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original,
            sqlite3.connect(snapshot) as backup,
        ):
            original.backup(backup)
            assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            before = fingerprint(backup)
            with sqlite3.connect(restored) as target:
                backup.backup(target)
        with sqlite3.connect(restored) as target:
            assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert target.execute("PRAGMA foreign_key_check").fetchall() == []
            assert fingerprint(target) == before
    return {
        "status": "passed",
        "tables": before,
        "scope": "SQLite consistent snapshot and restore; no PostgreSQL claim",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    args = parser.parse_args()
    print(json.dumps(verify(args.source), ensure_ascii=False, indent=2))
