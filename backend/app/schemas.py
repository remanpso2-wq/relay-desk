from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Strict):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=128)


class TicketCreate(Strict):
    title: str = Field(min_length=2, max_length=150)
    customer: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=5, max_length=6000)
    category: Literal["配送", "請求", "アカウント", "その他"] = "その他"
    priority: Literal["normal", "high"] = "normal"


class TicketUpdate(Strict):
    version: int = Field(ge=1)
    status: Literal["open", "in_progress", "resolved"]
    assignee_id: str | None = None


class ArticleInput(Strict):
    title: str = Field(min_length=2, max_length=150)
    body: str = Field(min_length=10, max_length=12000)
    category: Literal["配送", "請求", "アカウント", "その他"] = "その他"
    active: bool = True
    version: int | None = None


class Generate(Strict):
    version: int = Field(ge=1)
    request_key: UUID
    consent: bool = False
    source_digest: str = Field(min_length=64, max_length=64)


class Review(Strict):
    action: Literal["approved", "rejected"]
    text: str = Field(min_length=1, max_length=6000)
    note: str = Field(min_length=2, max_length=1000)
    checked: bool


class NoteInput(Strict):
    text: str = Field(min_length=2, max_length=4000)
