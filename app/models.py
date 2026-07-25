"""Моделі бази даних (SQLAlchemy 2.0, типізований стиль)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .enums import Category, DonationStatus, FundStatus, NeedStatus, Role, Urgency


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize(text: str) -> str:
    """Зводить рядок до вигляду, придатного для пошуку через LIKE."""
    return " ".join(text.casefold().split())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64))
    role: Mapped[Role] = mapped_column(String(16), index=True)
    callsign: Mapped[str | None] = mapped_column(String(48), default=None)
    contact: Mapped[str | None] = mapped_column(String(120), default=None)
    about: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Need(Base):
    __tablename__ = "needs"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[Category] = mapped_column(String(16), index=True)
    urgency: Mapped[Urgency] = mapped_column(String(16), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit: Mapped[str] = mapped_column(String(24), default="шт")
    status: Mapped[NeedStatus] = mapped_column(String(16), index=True, default=NeedStatus.OPEN)
    location: Mapped[str | None] = mapped_column(String(120), default=None)

    # LIKE у SQLite нечутливий до регістру лише для латиниці, тож кирилицю
    # шукаємо по власноруч знормалізованій копії тексту.
    search_text: Mapped[str] = mapped_column(Text, default="", index=True)

    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    author: Mapped[User] = relationship(foreign_keys=[author_id], lazy="joined")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")

    def sync_search_text(self) -> None:
        self.search_text = normalize(f"{self.title} {self.description} {self.location or ''}")


class Fund(Base):
    __tablename__ = "funds"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    target_amount: Mapped[int] = mapped_column(Integer)
    # Денормалізована сума. Оновлюється в тій самій транзакції, що й внесок,
    # щоб не рахувати SUM() на кожен показ списку.
    current_amount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[FundStatus] = mapped_column(String(16), index=True, default=FundStatus.ACTIVE)
    requisites: Mapped[str | None] = mapped_column(String(200), default=None)

    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    need_id: Mapped[str | None] = mapped_column(ForeignKey("needs.id"), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    author: Mapped[User] = relationship(lazy="joined")


class Contribution(Base):
    __tablename__ = "contributions"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(lazy="joined")


class ItemDonation(Base):
    """Донат речами: волонтер або цивільний віддає щось конкретне."""

    __tablename__ = "item_donations"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    item: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit: Mapped[str] = mapped_column(String(24), default="шт")
    category: Mapped[Category] = mapped_column(String(16), index=True, default=Category.OTHER)
    contact: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[DonationStatus] = mapped_column(
        String(16), index=True, default=DonationStatus.OFFERED
    )

    donor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    need_id: Mapped[str | None] = mapped_column(ForeignKey("needs.id"), index=True, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    donor: Mapped[User] = relationship(lazy="joined")
    need: Mapped[Need | None] = relationship(lazy="joined")


class Activity(Base):
    """Журнал подій.

    Зберігаємо код події та структуровані дані, а не готовий текст —
    рядок для показу збирає клієнт. Слугує і стрічкою новин,
    і історією конкретного запиту.
    """

    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String(12), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, default=None)
    need_id: Mapped[str | None] = mapped_column(ForeignKey("needs.id"), index=True, default=None)
    fund_id: Mapped[str | None] = mapped_column(ForeignKey("funds.id"), index=True, default=None)
    donation_id: Mapped[str | None] = mapped_column(
        ForeignKey("item_donations.id"), index=True, default=None
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    actor: Mapped[User | None] = relationship(lazy="joined")


__all__ = [
    "User", "Need", "Fund", "Contribution", "ItemDonation", "Activity",
    "new_id", "utcnow", "func",
]
