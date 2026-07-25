"""Схеми запитів і відповідей."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import Category, DonationStatus, FundStatus, NeedStatus, Role, Urgency


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- користувачі ---

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=48, pattern=r"^[\w.\-]+$")
    password: str = Field(min_length=6, max_length=128)
    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    role: Role
    callsign: str | None = Field(default=None, max_length=48)
    contact: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(ORMModel):
    id: str
    username: str
    first_name: str
    last_name: str
    role: Role
    callsign: str | None = None
    contact: str | None = None
    about: str | None = None
    created_at: datetime


class UserBrief(ORMModel):
    id: str
    username: str
    first_name: str
    last_name: str
    role: Role
    callsign: str | None = None


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=64)
    last_name: str | None = Field(default=None, min_length=1, max_length=64)
    callsign: str | None = Field(default=None, max_length=48)
    contact: str | None = Field(default=None, max_length=120)
    about: str | None = Field(default=None, max_length=600)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserStats(BaseModel):
    needs_created: int = 0
    needs_completed: int = 0
    needs_in_progress: int = 0
    contributed_total: int = 0
    contributions_count: int = 0
    donations_offered: int = 0
    funds_created: int = 0


class UserProfileOut(BaseModel):
    user: UserOut
    stats: UserStats


class LeaderRow(BaseModel):
    user: UserBrief
    completed: int
    contributed: int


# --- запити (needs) ---

class NeedCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=3, max_length=4000)
    category: Category = Category.OTHER
    urgency: Urgency = Urgency.NORMAL
    quantity: int = Field(default=1, ge=1, le=1_000_000)
    unit: str = Field(default="шт", max_length=24)
    location: str | None = Field(default=None, max_length=120)


class NeedOut(ORMModel):
    id: str
    title: str
    description: str
    category: Category
    urgency: Urgency
    quantity: int
    unit: str
    status: NeedStatus
    location: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    author: UserBrief
    assignee: UserBrief | None = None


class CommentIn(BaseModel):
    comment: str | None = Field(default=None, max_length=400)


# --- збори (funds) ---

class FundCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=3, max_length=4000)
    target_amount: int = Field(ge=1, le=100_000_000)
    requisites: str | None = Field(default=None, max_length=200)
    need_id: str | None = None


class FundOut(ORMModel):
    id: str
    title: str
    description: str
    target_amount: int
    current_amount: int
    status: FundStatus
    requisites: str | None
    need_id: str | None
    created_at: datetime
    closed_at: datetime | None
    author: UserBrief


class ContributionIn(BaseModel):
    amount: int = Field(ge=1, le=10_000_000)
    comment: str | None = Field(default=None, max_length=200)


class ContributionOut(ORMModel):
    id: str
    amount: int
    comment: str | None
    created_at: datetime
    user: UserBrief


class FundDetailOut(BaseModel):
    fund: FundOut
    contributions: list[ContributionOut]


# --- донати речами ---

class DonationCreate(BaseModel):
    item: str = Field(min_length=2, max_length=160)
    quantity: int = Field(default=1, ge=1, le=1_000_000)
    unit: str = Field(default="шт", max_length=24)
    category: Category = Category.OTHER
    contact: str = Field(min_length=3, max_length=120)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("item", "contact")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


class NeedBrief(ORMModel):
    id: str
    title: str
    status: NeedStatus


class DonationOut(ORMModel):
    id: str
    item: str
    quantity: int
    unit: str
    category: Category
    contact: str
    note: str | None
    status: DonationStatus
    created_at: datetime
    donor: UserBrief
    need: NeedBrief | None = None


class DonationStatusIn(BaseModel):
    status: DonationStatus


# --- стрічка та зведення ---

class ActivityOut(ORMModel):
    id: str
    kind: str
    payload: dict
    created_at: datetime
    need_id: str | None
    fund_id: str | None
    donation_id: str | None
    actor: UserBrief | None = None


class NeedDetailOut(BaseModel):
    need: NeedOut
    history: list[ActivityOut]
    donations: list[DonationOut]
    funds: list[FundOut]


class Overview(BaseModel):
    needs_open: int
    needs_critical: int
    needs_in_progress: int
    needs_completed: int
    funds_active: int
    funds_raised: int
    donations_available: int
    volunteers: int
    by_category: dict[str, int]
