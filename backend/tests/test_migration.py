import os, subprocess, sys
from pathlib import Path
from sqlalchemy import create_engine, inspect


def test_initial_migration(tmp_path):
    url = "sqlite:///" + str(tmp_path / "migration.db")
    env = {**os.environ, "DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        check=True,
        capture_output=True,
    )
    e = create_engine(url)
    assert {
        "tenants",
        "users",
        "sessions",
        "tickets",
        "articles",
        "article_revisions",
        "drafts",
        "audit",
    } <= set(inspect(e).get_table_names())
    e.dispose()
