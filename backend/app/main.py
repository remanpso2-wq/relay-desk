import hashlib, secrets, time, os, json
from pathlib import Path
from sqlalchemy import select, update, func
from fastapi import FastAPI, Depends, Request, Response, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from .db import *
from .schemas import *
from . import ai

app = FastAPI(title="RELAY Desk", version="0.2.0")
ph = PasswordHasher()
DUMMY = ph.hash("not-a-real-user-password")
ORIGIN = os.getenv("APP_ORIGIN", "http://localhost:8000").rstrip("/")
SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
PROVIDER = os.getenv("AI_PROVIDER", "demo")


def fail(code, text):
    raise HTTPException(code, text)


def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()


def row(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def audit(db, u, action, target, detail=None):
    db.add(
        Audit(
            tenant_id=u.tenant_id,
            actor=u.name,
            action=action,
            target=target,
            detail=detail or {},
        )
    )


def lock(db, u):
    db.execute(
        update(Tenant)
        .where(Tenant.id == u.tenant_id)
        .values(lock_version=Tenant.lock_version + 1)
    )


def owned(db, cls, id, u):
    x = db.scalar(select(cls).where(cls.id == id, cls.tenant_id == u.tenant_id))
    if not x:
        fail(404, "対象が見つかりません")
    return x


def identity(req: Request, db=Depends(get_db)):
    token = req.cookies.get("relay_session", "")
    s = db.get(AuthSession, digest(token)) if token else None
    if not s or s.expires < int(time.time()):
        fail(401, "ログインしてください")
    u = db.get(User, s.user_id)
    if not u:
        fail(401, "ログインしてください")
    if req.method not in ("GET", "HEAD", "OPTIONS") and not secrets.compare_digest(
        req.headers.get("x-csrf-token", ""), s.csrf
    ):
        fail(403, "画面を再読み込みしてください")
    return u


def editor(u=Depends(identity)):
    if u.role not in ("admin", "agent", "reviewer"):
        fail(403, "編集権限がありません")
    return u


def reviewer(u=Depends(identity)):
    if u.role not in ("admin", "reviewer"):
        fail(403, "承認権限がありません")
    return u


@app.middleware("http")
async def boundary(req, call_next):
    if req.method not in ("GET", "HEAD", "OPTIONS"):
        if req.headers.get("origin") != ORIGIN:
            return JSONResponse({"detail": "許可されていない送信元です"}, 403)
        try:
            length = int(req.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse({"detail": "不正なリクエスト"}, 400)
        if length > 65536:
            return JSONResponse({"detail": "送信サイズが大きすぎます"}, 413)
        # Bound chunked requests too; Starlette caches the consumed body.
        body = b""
        async for chunk in req.stream():
            body += chunk
            if len(body) > 65536:
                return JSONResponse({"detail": "送信サイズが大きすぎます"}, 413)
        req._body = body
    res = await call_next(req)
    res.headers["X-Content-Type-Options"] = "nosniff"
    res.headers["Referrer-Policy"] = "same-origin"
    res.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if req.url.path.startswith("/api/"):
        res.headers["Cache-Control"] = "no-store"
    return res


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.2.0"}


@app.post("/api/login")
def login(p: Login, req: Request, res: Response, db=Depends(get_db)):
    key = digest(p.email.lower())
    timestamp = int(time.time())
    a = db.get(LoginAttempt, key)
    if a and a.until > timestamp and a.count >= 8:
        fail(429, "時間をおいて再試行してください")
    u = db.scalar(select(User).where(User.email == p.email.lower()))
    try:
        valid = ph.verify(u.password if u else DUMMY, p.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not u or not valid:
        if not a:
            a = LoginAttempt(key=key, count=0, until=timestamp + 900)
            db.add(a)
        if a.until <= timestamp:
            a.count = 0
            a.until = timestamp + 900
        a.count += 1
        db.commit()
        fail(401, "メールまたはパスワードが違います")
    if a:
        db.delete(a)
    old = req.cookies.get("relay_session")
    if old:
        s = db.get(AuthSession, digest(old))
        if s:
            db.delete(s)
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=digest(token), user_id=u.id, csrf=csrf, expires=timestamp + 28800
        )
    )
    audit(db, u, "login", u.id)
    db.commit()
    res.set_cookie(
        "relay_session",
        token,
        httponly=True,
        secure=SECURE,
        samesite="strict",
        max_age=28800,
    )
    return {"csrf": csrf, "user": {"id": u.id, "name": u.name, "role": u.role}}


@app.get("/api/me")
def me(req: Request, u=Depends(identity), db=Depends(get_db)):
    return {
        "user": {"id": u.id, "name": u.name, "role": u.role},
        "tenant": db.get(Tenant, u.tenant_id).name,
        "csrf": db.get(AuthSession, digest(req.cookies["relay_session"])).csrf,
        "provider": PROVIDER,
    }


@app.post("/api/logout")
def logout(req: Request, res: Response, u=Depends(identity), db=Depends(get_db)):
    db.delete(db.get(AuthSession, digest(req.cookies["relay_session"])))
    audit(db, u, "logout", u.id)
    db.commit()
    res.delete_cookie("relay_session")
    return {"ok": True}


@app.get("/api/users")
def users(u=Depends(identity), db=Depends(get_db)):
    return [
        {"id": x.id, "name": x.name, "role": x.role}
        for x in db.scalars(
            select(User).where(User.tenant_id == u.tenant_id).order_by(User.name)
        )
    ]


@app.get("/api/tickets")
def tickets(u=Depends(identity), db=Depends(get_db)):
    return [
        row(x)
        for x in db.scalars(
            select(Ticket)
            .where(Ticket.tenant_id == u.tenant_id)
            .order_by(Ticket.created_at.desc())
            .limit(200)
        )
    ]


@app.post("/api/tickets", status_code=201)
def create_ticket(p: TicketCreate, u=Depends(editor), db=Depends(get_db)):
    t = Ticket(tenant_id=u.tenant_id, **p.model_dump())
    db.add(t)
    db.flush()
    audit(db, u, "ticket.created", t.id)
    db.commit()
    return row(t)


@app.get("/api/tickets/{id}")
def ticket_detail(id: str, u=Depends(identity), db=Depends(get_db)):
    t = owned(db, Ticket, id, u)
    ds = list(
        db.scalars(
            select(Draft)
            .where(Draft.ticket_id == id, Draft.tenant_id == u.tenant_id)
            .order_by(Draft.created_at.desc())
        )
    )
    history = list(
        db.scalars(
            select(Audit)
            .where(Audit.tenant_id == u.tenant_id, Audit.target == id)
            .order_by(Audit.created_at.desc())
        )
    )
    return {
        "ticket": row(t),
        "drafts": [dict(row(d), stale=is_stale(db, d, t, u)) for d in ds],
        "history": [row(x) for x in history],
    }


@app.patch("/api/tickets/{id}")
def update_ticket(id: str, p: TicketUpdate, u=Depends(editor), db=Depends(get_db)):
    lock(db, u)
    t = owned(db, Ticket, id, u)
    if t.version != p.version:
        fail(409, "他の担当者が更新しました。再読み込みしてください")
    if p.assignee_id:
        owned(db, User, p.assignee_id, u)
    if p.status == "resolved":
        approved = db.scalars(
            select(Draft).where(
                Draft.ticket_id == id,
                Draft.tenant_id == u.tenant_id,
                Draft.status == "approved",
            )
        )
        if not any(not is_stale(db, d, t, u) for d in approved):
            fail(409, "最新の記録に基づく返信案を承認してから完了にしてください")
    before = {"status": t.status, "assignee_id": t.assignee_id}
    t.status = p.status
    t.assignee_id = p.assignee_id
    t.version += 1
    audit(db, u, "ticket.updated", id, {"before": before, "after": p.model_dump()})
    db.commit()
    return row(t)


@app.get("/api/articles")
def articles(u=Depends(identity), db=Depends(get_db)):
    return [
        row(a)
        for a in db.scalars(
            select(Article)
            .where(Article.tenant_id == u.tenant_id)
            .order_by(Article.updated_at.desc())
            .limit(500)
        )
    ]


def save_article(p, u, db, id=None):
    lock(db, u)
    if id:
        a = owned(db, Article, id, u)
        if a.version != p.version:
            fail(409, "資料が更新されています。再読み込みしてください")
        a.version += 1
    else:
        a = Article(tenant_id=u.tenant_id, version=1)
        db.add(a)
    for k in ("title", "body", "category", "active"):
        setattr(a, k, getattr(p, k))
    a.updated_at = now()
    db.flush()
    db.add(
        ArticleRevision(
            tenant_id=u.tenant_id,
            article_id=a.id,
            version=a.version,
            title=a.title,
            body=a.body,
        )
    )
    audit(
        db,
        u,
        "article.updated" if id else "article.created",
        a.id,
        {"version": a.version, "active": a.active},
    )
    db.commit()
    return row(a)


@app.post("/api/articles", status_code=201)
def new_article(p: ArticleInput, u=Depends(reviewer), db=Depends(get_db)):
    return save_article(p, u, db)


@app.put("/api/articles/{id}")
def edit_article(id: str, p: ArticleInput, u=Depends(reviewer), db=Depends(get_db)):
    return save_article(p, u, db, id)


@app.get("/api/articles/{id}/revisions")
def revisions(id: str, u=Depends(identity), db=Depends(get_db)):
    owned(db, Article, id, u)
    return [
        row(x)
        for x in db.scalars(
            select(ArticleRevision)
            .where(
                ArticleRevision.article_id == id,
                ArticleRevision.tenant_id == u.tenant_id,
            )
            .order_by(ArticleRevision.version.desc())
        )
    ]


def sources_for(db, t, u):
    return ai.retrieve(
        t.title + " " + t.body,
        db.scalars(
            select(Article)
            .where(Article.tenant_id == u.tenant_id, Article.active == True)
            .limit(500)
        ),
    )


def source_digest(question, sources):
    return digest(
        json.dumps(
            {"question": question, "sources": sources},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def is_stale(db, d, t, u):
    if t.version != d.ticket_version:
        return True
    for s in d.sources:
        a = db.scalar(
            select(Article).where(
                Article.id == s["id"], Article.tenant_id == u.tenant_id
            )
        )
        if not a or not a.active or a.version != s["version"]:
            return True
    return False


@app.get("/api/tickets/{id}/preview")
def preview(id: str, u=Depends(identity), db=Depends(get_db)):
    t = owned(db, Ticket, id, u)
    question = t.title + "\n" + t.body
    src = sources_for(db, t, u)
    return {
        "question": question,
        "sources": src,
        "provider": PROVIDER,
        "ticket_version": t.version,
        "source_digest": source_digest(question, src),
    }


@app.post("/api/tickets/{id}/drafts")
def generate_draft(
    id: str, p: Generate, req: Request, u=Depends(editor), db=Depends(get_db)
):
    lock(db, u)
    t = owned(db, Ticket, id, u)
    prior = db.scalar(
        select(Draft).where(
            Draft.tenant_id == u.tenant_id, Draft.request_key == str(p.request_key)
        )
    )
    if prior:
        if prior.ticket_id != id:
            fail(409, "リクエストIDを別の問い合わせには使用できません")
        return row(prior)
    if t.version != p.version:
        fail(409, "問い合わせが更新されています")
    if t.status == "resolved":
        fail(409, "完了済みです。再開してから生成してください")
    if not p.consent:
        fail(422, "送信内容を確認してください")
    if PROVIDER not in ("demo", "openai"):
        fail(503, "AI生成は無効です")
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    count = db.scalar(
        select(func.count())
        .select_from(Draft)
        .where(Draft.tenant_id == u.tenant_id, Draft.created_at >= cutoff)
    )
    if count >= int(os.getenv("AI_DAILY_LIMIT", "30")):
        fail(429, "過去24時間の生成上限に達しました")
    src = sources_for(db, t, u)
    question = t.title + "\n" + t.body
    if p.source_digest != source_digest(question, src):
        fail(409, "参照資料が更新されました。送信内容をもう一度確認してください")
    d = Draft(
        tenant_id=u.tenant_id,
        ticket_id=id,
        ticket_version=t.version,
        request_key=str(p.request_key),
        provider=PROVIDER,
        sources=src,
    )
    db.add(d)
    db.flush()
    audit(db, u, "draft.requested", id, {"draft_id": d.id})
    db.commit()
    try:
        answer, ids, needs, warning, model = ai.generate(question, src, PROVIDER)
        result = dict(
            original=answer,
            model=model,
            warning=(
                "追加の人手確認が必要です。 " if needs and PROVIDER == "openai" else ""
            )
            + warning,
            sources=[s for s in src if s["id"] in ids] if ids else src,
            status="draft" if answer else "blocked",
        )
    except Exception:
        result = dict(
            status="failed",
            warning="生成できませんでした。設定や接続を確認し、新しい生成操作で再試行してください。",
        )
    # Serialize with explicit timeout recovery. A late provider response cannot
    # resurrect a draft that an operator has already marked as interrupted.
    lock(db, u)
    db.refresh(d)
    if d.status == "generating":
        for key, value in result.items():
            setattr(d, key, value)
        audit(db, u, "draft." + d.status, id, {"draft_id": d.id})
    db.commit()
    # A logout during the external request must not receive a result.
    db.expire_all()
    identity(req, db)
    return row(d)


@app.post("/api/drafts/{id}/review")
def review(id: str, p: Review, u=Depends(reviewer), db=Depends(get_db)):
    lock(db, u)
    d = owned(db, Draft, id, u)
    t = owned(db, Ticket, d.ticket_id, u)
    if d.status != "draft":
        fail(409, "この下書きはすでに処理済みか、承認できない状態です")
    if p.action == "approved":
        if not p.checked:
            fail(422, "根拠と返信文を確認してください")
        if is_stale(db, d, t, u):
            fail(409, "問い合わせまたは資料が更新されました。生成し直してください")
    d.status = p.action
    d.reviewed_text = p.text
    d.review_note = p.note
    d.reviewer = u.name
    audit(db, u, "draft." + p.action, t.id, {"draft_id": id, "note": p.note})
    db.commit()
    return row(d)


@app.post("/api/tickets/{id}/notes", status_code=201)
def add_note(id: str, p: NoteInput, u=Depends(editor), db=Depends(get_db)):
    owned(db, Ticket, id, u)
    audit(db, u, "ticket.note", id, {"text": p.text})
    db.commit()
    return {"ok": True}


@app.post("/api/drafts/{id}/recover")
def recover(id: str, u=Depends(reviewer), db=Depends(get_db)):
    from datetime import datetime, timezone

    lock(db, u)
    d = owned(db, Draft, id, u)
    if d.status != "generating":
        fail(409, "生成中の下書きだけを復旧できます")
    age = (
        datetime.now(timezone.utc) - datetime.fromisoformat(d.created_at)
    ).total_seconds()
    if age < 120:
        fail(409, "開始から2分後に状況を再確認してください")
    d.status = "failed"
    d.warning = "担当者が中断状態として記録しました。外部への自動再送は行っていません。必要に応じて新しい下書きを生成してください。"
    audit(db, u, "draft.recovered", d.ticket_id, {"draft_id": id})
    db.commit()
    return row(d)


@app.get("/api/audit")
def audits(u=Depends(reviewer), db=Depends(get_db)):
    return [
        row(x)
        for x in db.scalars(
            select(Audit)
            .where(Audit.tenant_id == u.tenant_id)
            .order_by(Audit.created_at.desc())
            .limit(150)
        )
    ]


static = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if static.exists():
    app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/")
    def home():
        return FileResponse(static / "index.html")
