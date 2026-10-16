import uuid, os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from app.db import (
    Base,
    make_engine,
    get_db,
    Tenant,
    User,
    Ticket,
    Article,
    Draft,
    AuthSession,
    ArticleRevision,
)
from app.main import app, ph

PW = "test-only-password-2026"


@pytest.fixture
def env(tmp_path):
    e = make_engine(
        os.getenv("TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "test.db"))
    )
    if os.getenv("TEST_DATABASE_URL"):
        from sqlalchemy import text

        with e.begin() as conn:
            conn.execute(
                text(
                    "TRUNCATE tenants, users, sessions, login_attempts, tickets, articles, article_revisions, drafts, audit CASCADE"
                )
            )
    else:
        Base.metadata.create_all(e)
    S = sessionmaker(e, expire_on_commit=False)
    with S() as s:
        a = Tenant(name="A")
        b = Tenant(name="B")
        s.add_all([a, b])
        s.flush()
        us = [
            User(
                tenant_id=a.id,
                name="Admin",
                email="admin@test",
                password=ph.hash(PW),
                role="admin",
            ),
            User(
                tenant_id=a.id,
                name="Agent",
                email="agent@test",
                password=ph.hash(PW),
                role="agent",
            ),
            User(
                tenant_id=b.id,
                name="Other",
                email="other@test",
                password=ph.hash(PW),
                role="admin",
            ),
        ]
        s.add_all(us)
        s.commit()

    def db():
        with S() as s:
            yield s

    app.dependency_overrides[get_db] = db
    with TestClient(app) as c:
        c.headers["Origin"] = "http://localhost:8000"
        login(c, "admin@test")
        yield c, S
    app.dependency_overrides.clear()
    e.dispose()


def login(c, email):
    r = c.post("/api/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf"]


def setup(c):
    a = c.post(
        "/api/articles",
        json={
            "title": "配送先住所の変更",
            "body": "配送先住所の変更は出荷前のみ受け付けます。注文番号と新しい住所を確認してください。",
            "category": "配送",
        },
    )
    assert a.status_code == 201, a.text
    t = c.post(
        "/api/tickets",
        json={
            "title": "配送先住所を変更したい",
            "customer": "架空のお客様",
            "body": "出荷前に配送先住所を変更したいです。",
            "category": "配送",
        },
    )
    assert t.status_code == 201, t.text
    return a.json(), t.json()


def gen(c, t, key=None):
    return c.post(
        "/api/tickets/" + t["id"] + "/drafts",
        json={
            "version": t["version"],
            "source_digest": c.get("/api/tickets/" + t["id"] + "/preview")
            .json()
            .get("source_digest", "0" * 64),
            "consent": True,
            "request_key": key or str(uuid.uuid4()),
        },
    )


def review(c, d):
    return c.post(
        "/api/drafts/" + d["id"] + "/review",
        json={
            "action": "approved",
            "text": "確認済みの返信です。",
            "note": "適用条件を確認",
            "checked": True,
        },
    )


def test_full_workflow(env):
    c, S = env
    a, t = setup(c)
    p = c.get("/api/tickets/" + t["id"] + "/preview").json()
    assert "customer" not in p
    assert p["sources"][0]["id"] == a["id"]
    d = gen(c, t).json()
    assert d["status"] == "draft"
    assert review(c, d).status_code == 200
    r = c.patch(
        "/api/tickets/" + t["id"],
        json={"version": 1, "status": "resolved", "assignee_id": None},
    )
    assert r.status_code == 200
    out = c.get("/api/tickets/" + t["id"]).json()
    assert out["drafts"][0]["original"] != out["drafts"][0]["reviewed_text"]
    assert len(out["history"]) >= 4
    assert review(c, d).status_code == 409


def test_cross_tenant_isolation(env):
    c, S = env
    a, t = setup(c)
    d = gen(c, t).json()
    login(c, "other@test")
    assert c.get("/api/tickets").json() == []
    assert c.get("/api/articles").json() == []
    for url in [
        "/api/tickets/" + t["id"],
        "/api/tickets/" + t["id"] + "/preview",
        "/api/articles/" + a["id"] + "/revisions",
    ]:
        assert c.get(url).status_code == 404
    assert review(c, d).status_code == 404
    assert gen(c, t).status_code == 404
    assert (
        c.put(
            "/api/articles/" + a["id"],
            json={
                **{k: a[k] for k in ["title", "body", "category", "version"]},
                "active": False,
            },
        ).status_code
        == 404
    )


def test_agent_cannot_approve_or_edit_knowledge(env):
    c, S = env
    a, t = setup(c)
    d = gen(c, t).json()
    login(c, "agent@test")
    assert review(c, d).status_code == 403
    assert (
        c.post(
            "/api/articles",
            json={"title": "新資料", "body": "これは十分な長さの資料です。"},
        ).status_code
        == 403
    )
    assert c.get("/api/audit").status_code == 403
    assert gen(c, t).status_code == 200


def test_csrf_origin_and_logout(env):
    c, S = env
    c.headers["X-CSRF-Token"] = "wrong"
    assert c.post("/api/logout", json={}).status_code == 403
    login(c, "admin@test")
    c.headers["Origin"] = "https://evil.test"
    assert c.post("/api/logout", json={}).status_code == 403
    c.headers["Origin"] = "http://localhost:8000"
    assert c.post("/api/logout", json={}).status_code == 200
    assert c.get("/api/tickets").status_code == 401


def test_stale_article_and_revision_preserved(env):
    c, S = env
    a, t = setup(c)
    d = gen(c, t).json()
    r = c.put(
        "/api/articles/" + a["id"],
        json={
            "title": a["title"],
            "body": "変更後の条件は担当者への個別確認が必要です。",
            "category": "配送",
            "version": 1,
        },
    )
    assert r.status_code == 200
    assert review(c, d).status_code == 409
    rev = c.get("/api/articles/" + a["id"] + "/revisions").json()
    assert len(rev) == 2
    assert rev[1]["body"] == a["body"]


def test_stale_ticket_and_optimistic_lock(env):
    c, S = env
    a, t = setup(c)
    d = gen(c, t).json()
    body = {"version": 1, "status": "in_progress", "assignee_id": None}
    assert c.patch("/api/tickets/" + t["id"], json=body).status_code == 200
    assert c.patch("/api/tickets/" + t["id"], json=body).status_code == 409
    assert review(c, d).status_code == 409


def test_idempotence_and_quota(env, monkeypatch):
    c, S = env
    a, t = setup(c)
    key = str(uuid.uuid4())
    d = gen(c, t, key).json()
    assert gen(c, t, key).json()["id"] == d["id"]
    monkeypatch.setenv("AI_DAILY_LIMIT", "1")
    assert gen(c, t).status_code == 429
    with S() as s:
        assert len(list(s.scalars(select(Draft)))) == 1


def test_no_evidence_and_unpublished_article(env):
    c, S = env
    a, t = setup(c)
    c.put(
        "/api/articles/" + a["id"],
        json={
            "title": a["title"],
            "body": a["body"],
            "category": "配送",
            "version": 1,
            "active": False,
        },
    )
    d = gen(c, t).json()
    assert d["status"] == "blocked"
    assert d["original"] == ""
    assert review(c, d).status_code == 409


def test_provider_failure_preserves_ticket(env, monkeypatch):
    from app import ai

    c, S = env
    a, t = setup(c)

    def crash(*_):
        raise RuntimeError("secret provider error")

    monkeypatch.setattr(ai, "generate", crash)
    d = gen(c, t).json()
    assert d["status"] == "failed"
    assert "secret" not in str(d)
    assert c.get("/api/tickets/" + t["id"]).json()["ticket"]["body"] == t["body"]


def test_cross_tenant_assignee(env):
    c, S = env
    a, t = setup(c)
    with S() as s:
        u = s.scalar(select(User).where(User.email == "other@test"))
    assert (
        c.patch(
            "/api/tickets/" + t["id"],
            json={"version": 1, "status": "in_progress", "assignee_id": u.id},
        ).status_code
        == 404
    )


def test_expired_session(env):
    c, S = env
    with S() as s:
        for x in s.scalars(select(AuthSession)):
            x.expires = 0
        s.commit()
    assert c.get("/api/me").status_code == 401


def test_login_throttle(env):
    c, S = env
    for _ in range(8):
        assert (
            c.post(
                "/api/login", json={"email": "missing@test", "password": "bad"}
            ).status_code
            == 401
        )
    assert (
        c.post(
            "/api/login", json={"email": "missing@test", "password": "bad"}
        ).status_code
        == 429
    )


def test_preview_cannot_silently_change(env):
    c, S = env
    a, t = setup(c)
    preview = c.get("/api/tickets/" + t["id"] + "/preview").json()
    c.put(
        "/api/articles/" + a["id"],
        json={
            "title": a["title"],
            "body": "配送先住所を変更する場合は必ず担当部署へ確認してください。",
            "version": 1,
        },
    )
    r = c.post(
        "/api/tickets/" + t["id"] + "/drafts",
        json={
            "version": 1,
            "consent": True,
            "source_digest": preview["source_digest"],
            "request_key": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 409
    with S() as s:
        assert list(s.scalars(select(Draft))) == []


def test_revoked_session_during_generation(env, monkeypatch):
    from app import ai

    c, S = env
    a, t = setup(c)
    original = ai.generate

    def revoke(*args):
        with S() as s:
            for x in s.scalars(select(AuthSession)):
                s.delete(x)
            s.commit()
        return original(*args)

    monkeypatch.setattr(ai, "generate", revoke)
    assert gen(c, t).status_code == 401
    with S() as s:
        assert s.scalar(select(Draft)).status == "draft"


def test_cannot_resolve_without_review(env):
    c, S = env
    a, t = setup(c)
    assert (
        c.patch(
            "/api/tickets/" + t["id"],
            json={"version": 1, "status": "resolved", "assignee_id": None},
        ).status_code
        == 409
    )


def test_internal_note_scope_and_not_sent_to_ai(env):
    c, S = env
    a, t = setup(c)
    marker = "担当者限定の内部メモです"
    assert (
        c.post("/api/tickets/" + t["id"] + "/notes", json={"text": marker}).status_code
        == 201
    )
    history = c.get("/api/tickets/" + t["id"]).json()["history"]
    assert any(x["detail"].get("text") == marker for x in history)
    assert marker not in str(c.get("/api/tickets/" + t["id"] + "/preview").json())
    login(c, "other@test")
    assert (
        c.post("/api/tickets/" + t["id"] + "/notes", json={"text": marker}).status_code
        == 404
    )


def test_recovery_wait_and_role(env):
    from datetime import datetime, timezone, timedelta

    c, S = env
    a, t = setup(c)
    with S() as s:
        ticket = s.get(Ticket, t["id"])
        d = Draft(
            tenant_id=ticket.tenant_id,
            ticket_id=ticket.id,
            ticket_version=1,
            request_key=str(uuid.uuid4()),
            provider="demo",
        )
        s.add(d)
        s.commit()
        did = d.id
    assert c.post("/api/drafts/" + did + "/recover", json={}).status_code == 409
    with S() as s:
        s.get(Draft, did).created_at = (
            datetime.now(timezone.utc) - timedelta(minutes=3)
        ).isoformat()
        s.commit()
    login(c, "agent@test")
    assert c.post("/api/drafts/" + did + "/recover", json={}).status_code == 403
    login(c, "admin@test")
    assert (
        c.post("/api/drafts/" + did + "/recover", json={}).json()["status"] == "failed"
    )
    assert c.post("/api/drafts/" + did + "/recover", json={}).status_code == 409


def test_late_response_does_not_resurrect_recovered_draft(env, monkeypatch):
    from app import ai

    c, S = env
    a, t = setup(c)
    original = ai.generate

    def recover_during_request(*args):
        with S() as s:
            d = s.scalar(select(Draft))
            d.status = "failed"
            d.warning = "recovered"
            s.commit()
        return original(*args)

    monkeypatch.setattr(ai, "generate", recover_during_request)
    d = gen(c, t).json()
    assert (
        d["status"] == "failed" and d["warning"] == "recovered" and d["original"] == ""
    )


def test_concurrent_reviews_only_one_succeeds(env):
    from concurrent.futures import ThreadPoolExecutor

    c, S = env
    a, t = setup(c)
    d = gen(c, t).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: review(c, d).status_code, range(2)))
    assert sorted(results) == [200, 409]


def test_database_rejects_cross_tenant_assignment(env):
    from sqlalchemy.exc import IntegrityError

    c, S = env
    a, t = setup(c)
    with S() as s:
        other = s.scalar(select(User).where(User.email == "other@test"))
        s.get(Ticket, t["id"]).assignee_id = other.id
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
