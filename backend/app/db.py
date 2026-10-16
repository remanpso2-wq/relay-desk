import os
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    create_engine,
    event,
    String,
    Text,
    Integer,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str]
    lock_version: Mapped[int] = mapped_column(default=0)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    password: Mapped[str]
    role: Mapped[str]


class AuthSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    csrf: Mapped[str]
    expires: Mapped[int]


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    until: Mapped[int]


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "assignee_id"], ["users.tenant_id", "users.id"]
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    title: Mapped[str]
    customer: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str]
    priority: Mapped[str]
    status: Mapped[str] = mapped_column(default="open")
    assignee_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str] = mapped_column(default=now)


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    title: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str]
    version: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[str] = mapped_column(default=now)


class ArticleRevision(Base):
    __tablename__ = "article_revisions"
    __table_args__ = (
        UniqueConstraint("article_id", "version"),
        ForeignKeyConstraint(
            ["tenant_id", "article_id"], ["articles.tenant_id", "articles.id"]
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id"))
    version: Mapped[int]
    title: Mapped[str]
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(default=now)


class Draft(Base):
    __tablename__ = "drafts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_key"),
        ForeignKeyConstraint(
            ["tenant_id", "ticket_id"], ["tickets.tenant_id", "tickets.id"]
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), index=True)
    ticket_version: Mapped[int]
    request_key: Mapped[str]
    status: Mapped[str] = mapped_column(default="generating")
    provider: Mapped[str]
    model: Mapped[str] = mapped_column(default="")
    original: Mapped[str] = mapped_column(Text, default="")
    reviewed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    warning: Mapped[str] = mapped_column(default="")
    reviewer: Mapped[str | None] = mapped_column(nullable=True)
    review_note: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=now)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor: Mapped[str]
    action: Mapped[str]
    target: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(default=now)


def make_engine(url):
    e = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 15}
        if url.startswith("sqlite")
        else {},
    )
    if url.startswith("sqlite"):

        @event.listens_for(e, "connect")
        def fk(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")

    return e


engine = make_engine(os.getenv("DATABASE_URL", "sqlite:///./relay.db"))
Session = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with Session() as s:
        yield s
