"""Машинні значення довідників.

Головне правило: у базі зберігаються ТІЛЬКИ ці коди.
Людські підписи живуть у labels.py і віддаються клієнту окремо
через /api/meta. Так інтерфейс можна перекласти, не чіпаючи дані.
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    CIVILIAN = "civilian"
    MILITARY = "military"
    VOLUNTEER = "volunteer"


class NeedStatus(StrEnum):
    OPEN = "open"                  # опубліковано, вільний
    IN_PROGRESS = "in_progress"    # волонтер узяв у роботу
    PENDING = "pending"            # волонтер закрив, чекає підтвердження автора
    COMPLETED = "completed"        # автор підтвердив
    CANCELLED = "cancelled"        # автор скасував


class Urgency(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Category(StrEnum):
    MEDICAL = "medical"
    GEAR = "gear"
    TRANSPORT = "transport"
    COMMS = "comms"
    POWER = "power"
    FOOD = "food"
    REPAIR = "repair"
    OTHER = "other"


class FundStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class DonationStatus(StrEnum):
    OFFERED = "offered"        # запропоновано
    RESERVED = "reserved"      # привʼязано до запиту
    DELIVERED = "delivered"    # передано
    CANCELLED = "cancelled"


class ActivityKind(StrEnum):
    USER_JOINED = "user_joined"
    NEED_CREATED = "need_created"
    NEED_TAKEN = "need_taken"
    NEED_RELEASED = "need_released"
    NEED_SUBMITTED = "need_submitted"
    NEED_CONFIRMED = "need_confirmed"
    NEED_REJECTED = "need_rejected"
    NEED_CANCELLED = "need_cancelled"
    FUND_CREATED = "fund_created"
    FUND_CONTRIBUTED = "fund_contributed"
    FUND_CLOSED = "fund_closed"
    DONATION_OFFERED = "donation_offered"
    DONATION_RESERVED = "donation_reserved"
    DONATION_DELIVERED = "donation_delivered"


# Дозволені переходи станів запиту. Будь-який інший перехід — 409.
NEED_TRANSITIONS: dict[NeedStatus, set[NeedStatus]] = {
    NeedStatus.OPEN: {NeedStatus.IN_PROGRESS, NeedStatus.CANCELLED},
    NeedStatus.IN_PROGRESS: {NeedStatus.OPEN, NeedStatus.PENDING, NeedStatus.CANCELLED},
    NeedStatus.PENDING: {NeedStatus.COMPLETED, NeedStatus.IN_PROGRESS},
    NeedStatus.COMPLETED: set(),
    NeedStatus.CANCELLED: set(),
}
