"""Наповнює базу демонстраційними даними.

    python seed.py            # додати демо-дані
    python seed.py --reset    # спершу видалити файл бази

Усі демо-акаунти мають пароль demo1234.
"""
from __future__ import annotations

import asyncio
import random
import sys
from datetime import timedelta

from app.config import settings
from app.db import SessionLocal, engine, init_models
from app.enums import ActivityKind, Category, DonationStatus, FundStatus, NeedStatus, Role, Urgency
from app.models import Activity, Contribution, Fund, ItemDonation, Need, User, utcnow
from app.security import hash_password

PASSWORD = "demo1234"

PEOPLE = [
    ("kovalenko", "Андрій", "Коваленко", Role.MILITARY, "Граніт", "@kovalenko_a"),
    ("shevchuk", "Ігор", "Шевчук", Role.MILITARY, "Схід", "@shevchuk_i"),
    ("marchenko", "Олена", "Марченко", Role.VOLUNTEER, None, "+380 67 000 11 22"),
    ("bondar", "Дмитро", "Бондар", Role.VOLUNTEER, None, "@bondar_d"),
    ("tkachuk", "Софія", "Ткачук", Role.VOLUNTEER, None, "@tkachuk_s"),
    ("lysenko", "Павло", "Лисенко", Role.CIVILIAN, None, "@lysenko_p"),
    ("hrytsenko", "Марія", "Гриценко", Role.CIVILIAN, None, "@hrytsenko_m"),
]

NEEDS = [
    ("Турнікети CAT Gen7", "Потрібні оригінальні турнікети на групу. Підробки з маркетплейсів не підходять — перевіряємо за партією.", Category.MEDICAL, Urgency.CRITICAL, 24, "шт"),
    ("Ноші складані", "Легкі складані ноші для евакуації. Бажано з кріпленням для фіксації.", Category.MEDICAL, Urgency.HIGH, 4, "шт"),
    ("Ремонт УАЗ: зчеплення", "Розсипався вижимний підшипник. Потрібен комплект зчеплення і, якщо вийде, майстер.", Category.TRANSPORT, Urgency.HIGH, 1, "компл"),
    ("Акумулятори 12V 100Ah", "Живлення для вузла звʼязку. Підійдуть AGM або LiFePO4.", Category.POWER, Urgency.NORMAL, 6, "шт"),
    ("Антени для радіостанцій", "Виносні антени, діапазон 136–174 МГц.", Category.COMMS, Urgency.NORMAL, 8, "шт"),
    ("Спальники до -15", "Зимові спальники, температура комфорту мінімум -10.", Category.GEAR, Urgency.HIGH, 15, "шт"),
    ("Генератор 5 кВт", "Інверторний, бажано з ручним і електростартом.", Category.POWER, Urgency.CRITICAL, 1, "шт"),
    ("Сухпайки та консерви", "Тримке харчування на два тижні для групи з 12 осіб.", Category.FOOD, Urgency.NORMAL, 200, "шт"),
    ("Зварювальний інвертор", "Для польової майстерні, 200 А достатньо.", Category.REPAIR, Urgency.LOW, 1, "шт"),
    ("Тепловізійний монокуляр", "Для нічного спостереження. Розглядаємо будь-які робочі варіанти.", Category.GEAR, Urgency.CRITICAL, 2, "шт"),
    ("Гумові чоботи", "Розміри 42–45, на весь підрозділ.", Category.GEAR, Urgency.LOW, 20, "пар"),
    ("Кабель силовий 3х2.5", "Для розведення живлення в укритті.", Category.POWER, Urgency.NORMAL, 100, "м"),
]

FUNDS = [
    ("Пікап для евакуаційної групи", "Збираємо на Mitsubishi L200 2012 року. Машина оглянута, документи готові — лишилось закрити суму.", 480_000, "Банка: send.monobank.ua/demo1"),
    ("Комплект тепловізорів", "Два монокуляри для нічних чергувань. Перший уже викуплено.", 210_000, "Банка: send.monobank.ua/demo2"),
    ("Ремонт двох УАЗів", "Зчеплення, гальма, гума. Роботи бере на себе наша майстерня.", 95_000, "Банка: send.monobank.ua/demo3"),
    ("Медичні укладки", "Двадцять індивідуальних аптечок повного складу.", 140_000, "Банка: send.monobank.ua/demo4"),
]

DONATIONS = [
    ("Бинти еластичні", 40, "шт", Category.MEDICAL),
    ("Термобілизна, розмір L", 12, "компл", Category.GEAR),
    ("Павербанки 20000 mAh", 6, "шт", Category.POWER),
    ("Каремати", 18, "шт", Category.GEAR),
    ("Консерви мʼясні", 120, "шт", Category.FOOD),
    ("Ліхтарі налобні", 25, "шт", Category.GEAR),
    ("Подовжувачі 10 м", 8, "шт", Category.POWER),
]

CONTRIB_COMMENTS = [
    "Тримайтесь.", "Від нашого відділу.", None, "Дякую за роботу.", None,
    "Перекажу ще наступного тижня.", None, "Разом до перемоги.",
]


async def main() -> None:
    if "--reset" in sys.argv:
        db_path = settings.database_url.split("///")[-1]
        import os
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"Базу видалено: {db_path}")

    await init_models()
    rng = random.Random(2026)
    now = utcnow()

    async with SessionLocal() as session:
        if await session.get(User, "seedcheck") is None:
            pass
        from sqlalchemy import select
        if (await session.scalars(select(User).limit(1))).first() is not None:
            print("У базі вже є дані — пропускаю. Запустіть з --reset, щоб перезаписати.")
            return

        users: dict[str, User] = {}
        for i, (username, first, last, role, callsign, contact) in enumerate(PEOPLE):
            user = User(
                username=username,
                password_hash=hash_password(PASSWORD),
                first_name=first,
                last_name=last,
                role=role,
                callsign=callsign,
                contact=contact,
                created_at=now - timedelta(days=40 - i * 3),
            )
            session.add(user)
            users[username] = user
        await session.flush()

        military = [u for u in users.values() if u.role == Role.MILITARY]
        volunteers = [u for u in users.values() if u.role == Role.VOLUNTEER]
        civilians = [u for u in users.values() if u.role == Role.CIVILIAN]

        for user in users.values():
            session.add(Activity(
                kind=str(ActivityKind.USER_JOINED), actor_id=user.id,
                payload={"role": str(user.role)}, created_at=user.created_at,
            ))

        needs: list[Need] = []
        for i, (title, desc, cat, urg, qty, unit) in enumerate(NEEDS):
            author = military[i % len(military)]
            created = now - timedelta(days=rng.randint(1, 25), hours=rng.randint(0, 23))
            need = Need(
                title=title, description=desc, category=cat, urgency=urg,
                quantity=qty, unit=unit, author_id=author.id,
                status=NeedStatus.OPEN, created_at=created, updated_at=created,
            )
            need.sync_search_text()
            session.add(need)
            needs.append(need)
        await session.flush()

        for need in needs:
            session.add(Activity(
                kind=str(ActivityKind.NEED_CREATED), actor_id=need.author_id, need_id=need.id,
                payload={"title": need.title, "urgency": str(need.urgency),
                         "category": str(need.category)},
                created_at=need.created_at,
            ))

        # Розкидаємо запити по станах, щоб дошка не була порожньою.
        def advance(need: Need, volunteer: User, to: NeedStatus) -> None:
            taken_at = need.created_at + timedelta(hours=rng.randint(2, 30))
            need.assignee_id = volunteer.id
            session.add(Activity(
                kind=str(ActivityKind.NEED_TAKEN), actor_id=volunteer.id, need_id=need.id,
                payload={"title": need.title}, created_at=taken_at,
            ))
            if to in (NeedStatus.PENDING, NeedStatus.COMPLETED):
                done_at = taken_at + timedelta(hours=rng.randint(4, 60))
                session.add(Activity(
                    kind=str(ActivityKind.NEED_SUBMITTED), actor_id=volunteer.id, need_id=need.id,
                    payload={"title": need.title}, created_at=done_at,
                ))
                if to is NeedStatus.COMPLETED:
                    conf_at = done_at + timedelta(hours=rng.randint(1, 20))
                    need.completed_at = conf_at
                    session.add(Activity(
                        kind=str(ActivityKind.NEED_CONFIRMED), actor_id=need.author_id,
                        need_id=need.id,
                        payload={"title": need.title, "assignee_id": volunteer.id},
                        created_at=conf_at,
                    ))
            need.status = to
            need.updated_at = now

        plan = [
            (1, volunteers[0], NeedStatus.IN_PROGRESS),
            (3, volunteers[1], NeedStatus.IN_PROGRESS),
            (5, volunteers[2], NeedStatus.PENDING),
            (7, volunteers[0], NeedStatus.COMPLETED),
            (8, volunteers[0], NeedStatus.COMPLETED),
            (10, volunteers[1], NeedStatus.COMPLETED),
            (11, volunteers[2], NeedStatus.IN_PROGRESS),
        ]
        for index, volunteer, target in plan:
            advance(needs[index], volunteer, target)

        funds: list[Fund] = []
        for i, (title, desc, target, requisites) in enumerate(FUNDS):
            author = (volunteers + military)[i % (len(volunteers) + len(military))]
            created = now - timedelta(days=rng.randint(3, 30))
            fund = Fund(
                title=title, description=desc, target_amount=target,
                requisites=requisites, created_by=author.id, created_at=created,
            )
            session.add(fund)
            funds.append(fund)
        await session.flush()

        for fund in funds:
            session.add(Activity(
                kind=str(ActivityKind.FUND_CREATED), actor_id=fund.created_by, fund_id=fund.id,
                payload={"title": fund.title, "target": fund.target_amount},
                created_at=fund.created_at,
            ))

        donors = list(users.values())
        for fund in funds:
            share = rng.uniform(0.25, 0.85)
            remaining = int(fund.target_amount * share)
            while remaining > 0:
                amount = min(remaining, rng.choice([200, 500, 1000, 2000, 5000, 10_000, 25_000]))
                donor = rng.choice(donors)
                at = fund.created_at + timedelta(
                    hours=rng.randint(1, max(2, int((now - fund.created_at).total_seconds() // 3600)))
                )
                session.add(Contribution(
                    fund_id=fund.id, user_id=donor.id, amount=amount,
                    comment=rng.choice(CONTRIB_COMMENTS), created_at=at,
                ))
                session.add(Activity(
                    kind=str(ActivityKind.FUND_CONTRIBUTED), actor_id=donor.id, fund_id=fund.id,
                    payload={"title": fund.title, "amount": amount}, created_at=at,
                ))
                fund.current_amount += amount
                remaining -= amount
            if fund.current_amount >= fund.target_amount:
                fund.status = FundStatus.CLOSED
                fund.closed_at = now

        givers = volunteers + civilians
        for i, (item, qty, unit, cat) in enumerate(DONATIONS):
            donor = givers[i % len(givers)]
            created = now - timedelta(days=rng.randint(1, 18))
            donation = ItemDonation(
                item=item, quantity=qty, unit=unit, category=cat,
                contact=donor.contact or f"@{donor.username}",
                donor_id=donor.id, created_at=created,
                note="Можу привезти самостійно." if i % 3 == 0 else None,
            )
            if i in (1, 4):
                match = next((n for n in needs if n.category == cat), None)
                if match is not None:
                    donation.need_id = match.id
                    donation.status = DonationStatus.RESERVED
            session.add(donation)
            await session.flush()
            session.add(Activity(
                kind=str(ActivityKind.DONATION_OFFERED), actor_id=donor.id,
                donation_id=donation.id,
                payload={"item": item, "quantity": qty, "unit": unit},
                created_at=created,
            ))

        await session.commit()

    await engine.dispose()
    print("Готово. Демо-акаунти (пароль demo1234):")
    for username, first, last, role, *_ in PEOPLE:
        print(f"  {username:12} {first} {last:12} — {role}")


if __name__ == "__main__":
    asyncio.run(main())
