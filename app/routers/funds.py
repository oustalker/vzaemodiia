"""Фінансові збори та внески до них."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep, log_activity, require_roles
from ..enums import ActivityKind, FundStatus, Role
from ..models import Contribution, Fund, Need, User, utcnow
from ..schemas import (
    ContributionIn, ContributionOut, FundCreate, FundDetailOut, FundOut,
)

router = APIRouter(prefix="/api/funds", tags=["funds"])


async def _get_fund(session, fund_id: str) -> Fund:
    fund = await session.get(Fund, fund_id)
    if fund is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Збір не знайдено")
    return fund


@router.get("", response_model=list[FundOut])
async def list_funds(
    session: SessionDep,
    user: CurrentUser,
    scope: Literal["all", "mine"] = "all",
    status_filter: Annotated[FundStatus | None, Query(alias="status")] = None,
) -> list[FundOut]:
    stmt = select(Fund)
    if scope == "mine":
        stmt = stmt.where(Fund.created_by == user.id)
    if status_filter is not None:
        stmt = stmt.where(Fund.status == status_filter)
    stmt = stmt.order_by(Fund.status, Fund.created_at.desc())
    rows = (await session.scalars(stmt)).unique().all()
    return [FundOut.model_validate(f) for f in rows]


@router.post("", response_model=FundOut, status_code=status.HTTP_201_CREATED)
async def create_fund(
    data: FundCreate,
    session: SessionDep,
    user: Annotated[User, Depends(require_roles(Role.MILITARY, Role.VOLUNTEER))],
) -> FundOut:
    if data.need_id is not None:
        need = await session.get(Need, data.need_id)
        if need is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Запит для привʼязки не знайдено")

    fund = Fund(
        title=data.title.strip(),
        description=data.description.strip(),
        target_amount=data.target_amount,
        requisites=data.requisites,
        need_id=data.need_id,
        created_by=user.id,
    )
    session.add(fund)
    await session.flush()
    await log_activity(
        session, ActivityKind.FUND_CREATED, actor_id=user.id, fund_id=fund.id,
        need_id=fund.need_id, title=fund.title, target=fund.target_amount,
    )
    await session.commit()
    await session.refresh(fund)
    return FundOut.model_validate(fund)


@router.get("/{fund_id}", response_model=FundDetailOut)
async def fund_detail(fund_id: str, session: SessionDep, user: CurrentUser) -> FundDetailOut:
    fund = await _get_fund(session, fund_id)
    contributions = (
        await session.scalars(
            select(Contribution)
            .where(Contribution.fund_id == fund_id)
            .order_by(Contribution.created_at.desc())
        )
    ).unique().all()
    return FundDetailOut(
        fund=FundOut.model_validate(fund),
        contributions=[ContributionOut.model_validate(c) for c in contributions],
    )


@router.post("/{fund_id}/contribute", response_model=FundOut)
async def contribute(
    fund_id: str, data: ContributionIn, session: SessionDep, user: CurrentUser
) -> FundOut:
    """Внесок до збору.

    Це облік, а не платіжний шлюз: користувач фіксує суму, яку переказав
    за реквізитами. Підключення реального еквайрингу — окреме завдання.
    """
    fund = await _get_fund(session, fund_id)
    if fund.status != FundStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Збір уже завершено")

    contribution = Contribution(
        fund_id=fund.id, user_id=user.id, amount=data.amount, comment=data.comment
    )
    session.add(contribution)
    # Сума й запис про внесок змінюються в одній транзакції.
    fund.current_amount += data.amount

    await log_activity(
        session, ActivityKind.FUND_CONTRIBUTED, actor_id=user.id, fund_id=fund.id,
        title=fund.title, amount=data.amount,
    )

    if fund.current_amount >= fund.target_amount:
        fund.status = FundStatus.CLOSED
        fund.closed_at = utcnow()
        await log_activity(
            session, ActivityKind.FUND_CLOSED, actor_id=user.id, fund_id=fund.id,
            title=fund.title, total=fund.current_amount, reason="target_reached",
        )

    await session.commit()
    await session.refresh(fund)
    return FundOut.model_validate(fund)


@router.post("/{fund_id}/close", response_model=FundOut)
async def close_fund(fund_id: str, session: SessionDep, user: CurrentUser) -> FundOut:
    fund = await _get_fund(session, fund_id)
    if fund.created_by != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Закрити збір може лише його автор")
    if fund.status != FundStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "Збір уже завершено")

    fund.status = FundStatus.CLOSED
    fund.closed_at = utcnow()
    await log_activity(
        session, ActivityKind.FUND_CLOSED, actor_id=user.id, fund_id=fund.id,
        title=fund.title, total=fund.current_amount, reason="closed_by_author",
    )
    await session.commit()
    await session.refresh(fund)
    return FundOut.model_validate(fund)
