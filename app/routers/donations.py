"""Донати речами: склад вільних позицій і привʼязка їх до запитів."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep, log_activity
from ..enums import ActivityKind, Category, DonationStatus, NeedStatus
from ..models import ItemDonation, Need
from ..schemas import DonationCreate, DonationOut, DonationStatusIn

router = APIRouter(prefix="/api/donations", tags=["donations"])


async def _get_donation(session, donation_id: str) -> ItemDonation:
    donation = await session.get(ItemDonation, donation_id)
    if donation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Донат не знайдено")
    return donation


@router.get("", response_model=list[DonationOut])
async def list_donations(
    session: SessionDep,
    user: CurrentUser,
    scope: Literal["all", "mine", "available"] = "all",
    category: Category | None = None,
) -> list[DonationOut]:
    stmt = select(ItemDonation)
    if scope == "mine":
        stmt = stmt.where(ItemDonation.donor_id == user.id)
    elif scope == "available":
        stmt = stmt.where(ItemDonation.status == DonationStatus.OFFERED)
    if category is not None:
        stmt = stmt.where(ItemDonation.category == category)
    stmt = stmt.order_by(ItemDonation.created_at.desc())
    rows = (await session.scalars(stmt)).unique().all()
    return [DonationOut.model_validate(d) for d in rows]


@router.post("", response_model=DonationOut, status_code=status.HTTP_201_CREATED)
async def create_donation(
    data: DonationCreate, session: SessionDep, user: CurrentUser
) -> DonationOut:
    donation = ItemDonation(
        item=data.item,
        quantity=data.quantity,
        unit=data.unit.strip() or "шт",
        category=data.category,
        contact=data.contact,
        note=data.note,
        donor_id=user.id,
    )
    session.add(donation)
    await session.flush()
    await log_activity(
        session, ActivityKind.DONATION_OFFERED, actor_id=user.id, donation_id=donation.id,
        item=donation.item, quantity=donation.quantity, unit=donation.unit,
    )
    await session.commit()
    await session.refresh(donation)
    return DonationOut.model_validate(donation)


@router.post("/{donation_id}/link/{need_id}", response_model=DonationOut)
async def link_to_need(
    donation_id: str, need_id: str, session: SessionDep, user: CurrentUser
) -> DonationOut:
    """Закріпити донат за конкретним запитом."""
    donation = await _get_donation(session, donation_id)
    if donation.donor_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Це не ваш донат")
    if donation.status not in (DonationStatus.OFFERED, DonationStatus.RESERVED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Донат уже передано або знято")

    need = await session.get(Need, need_id)
    if need is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запит не знайдено")
    if need.status in (NeedStatus.COMPLETED, NeedStatus.CANCELLED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Запит уже закритий")

    donation.need_id = need.id
    donation.status = DonationStatus.RESERVED
    await log_activity(
        session, ActivityKind.DONATION_RESERVED, actor_id=user.id,
        donation_id=donation.id, need_id=need.id, item=donation.item, title=need.title,
    )
    await session.commit()
    await session.refresh(donation)
    return DonationOut.model_validate(donation)


@router.post("/{donation_id}/unlink", response_model=DonationOut)
async def unlink(donation_id: str, session: SessionDep, user: CurrentUser) -> DonationOut:
    donation = await _get_donation(session, donation_id)
    if donation.donor_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Це не ваш донат")
    donation.need_id = None
    donation.status = DonationStatus.OFFERED
    await session.commit()
    await session.refresh(donation)
    return DonationOut.model_validate(donation)


@router.post("/{donation_id}/status", response_model=DonationOut)
async def set_status(
    donation_id: str, data: DonationStatusIn, session: SessionDep, user: CurrentUser
) -> DonationOut:
    donation = await _get_donation(session, donation_id)
    if donation.donor_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Це не ваш донат")
    if donation.status == DonationStatus.DELIVERED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Донат уже позначено переданим")

    donation.status = data.status
    if data.status == DonationStatus.DELIVERED:
        await log_activity(
            session, ActivityKind.DONATION_DELIVERED, actor_id=user.id,
            donation_id=donation.id, need_id=donation.need_id, item=donation.item,
        )
    await session.commit()
    await session.refresh(donation)
    return DonationOut.model_validate(donation)
