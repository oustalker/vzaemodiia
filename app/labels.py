"""Людські підписи до кодів довідників.

Віддаються клієнту одним пакетом через /api/meta, тож інтерфейс
не тримає власних копій і не розʼїжджається з бекендом.
"""
from __future__ import annotations

from .enums import Category, DonationStatus, FundStatus, NeedStatus, Role, Urgency

ROLE_LABELS = {
    Role.CIVILIAN: "Цивільна особа",
    Role.MILITARY: "Військовий",
    Role.VOLUNTEER: "Волонтер",
}

NEED_STATUS_LABELS = {
    NeedStatus.OPEN: "Відкритий",
    NeedStatus.IN_PROGRESS: "В роботі",
    NeedStatus.PENDING: "Чекає підтвердження",
    NeedStatus.COMPLETED: "Виконано",
    NeedStatus.CANCELLED: "Скасовано",
}

URGENCY_LABELS = {
    Urgency.LOW: "Може почекати",
    Urgency.NORMAL: "Звичайний",
    Urgency.HIGH: "Терміново",
    Urgency.CRITICAL: "Критично",
}

CATEGORY_LABELS = {
    Category.MEDICAL: "Медицина",
    Category.GEAR: "Спорядження",
    Category.TRANSPORT: "Транспорт",
    Category.COMMS: "Звʼязок",
    Category.POWER: "Живлення",
    Category.FOOD: "Харчування",
    Category.REPAIR: "Ремонт",
    Category.OTHER: "Інше",
}

# Короткі позначки для лівої стрічки картки — стенсильні мітки на ящику.
CATEGORY_MARKS = {
    Category.MEDICAL: "МЕД",
    Category.GEAR: "СПР",
    Category.TRANSPORT: "ТРН",
    Category.COMMS: "ЗВЯ",
    Category.POWER: "ЖИВ",
    Category.FOOD: "ХРЧ",
    Category.REPAIR: "РЕМ",
    Category.OTHER: "ІНШ",
}

FUND_STATUS_LABELS = {
    FundStatus.ACTIVE: "Триває",
    FundStatus.CLOSED: "Завершено",
}

DONATION_STATUS_LABELS = {
    DonationStatus.OFFERED: "Вільний",
    DonationStatus.RESERVED: "Закріплено",
    DonationStatus.DELIVERED: "Передано",
    DonationStatus.CANCELLED: "Знято",
}


def as_options(labels: dict) -> list[dict[str, str]]:
    return [{"value": str(key), "label": value} for key, value in labels.items()]
