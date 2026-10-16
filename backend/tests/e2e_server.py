import os, subprocess, sys, tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
    env = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + str(Path(d) / "e2e.db"),
        "DEMO_PASSWORD": "e2e-only-password-2026",
        "APP_ORIGIN": "http://127.0.0.1:8010",
        "AI_PROVIDER": "demo",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=root,
        env=env,
        check=True,
    )
    subprocess.run([sys.executable, "-m", "app.seed"], cwd=root, env=env, check=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8010",
        ],
        cwd=root,
        env=env,
        check=True,
    )
