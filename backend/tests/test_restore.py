import importlib.util
from pathlib import Path
from sqlalchemy.orm import Session
from app.db import Base, make_engine, Tenant


def test_sqlite_restore_preserves_records(tmp_path):
    source = tmp_path / "source.db"
    e = make_engine("sqlite:///" + str(source))
    Base.metadata.create_all(e)
    with Session(e) as s:
        s.add(Tenant(name="復元テスト"))
        s.commit()
    e.dispose()
    spec = importlib.util.spec_from_file_location(
        "restore", Path(__file__).resolve().parents[2] / "ops/check_sqlite_restore.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.verify(source)
    assert result["status"] == "passed"
    assert result["tables"]["tenants"]["rows"] == 1
