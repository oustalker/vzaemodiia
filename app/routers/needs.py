"""Запити військових і робота волонтерів з ними."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep, log_activity, require_roles
from ..enums import ActivityKind, Category, NEED_TRANSITIONS, NeedStatus, Role, Urgency
from ..models import Fund, ItemDonation, Need, User, normalize, utcnow
from ..schemas import (
    ActivityOut, CommentIn, DonationOut, FundOut, NeedCreate, NeedDetailOut, NeedOut,
)
from ..models import Activity

router = APIRouter(prefix="/api/needs", tags=["needs"])

# Порядок сортування за пріоритетом: критичні зверху.
URGENCY_ORDER = {Urgency.CRITICAL: 0, Urgency.HIGH: 1, Urgency.NORMAL: 2, Urgency.LOW: 3}


def _check_transition(need: Need, target: NeedStatus) -> None:
    if target not in NEED_TRANSITIONS[NeedStatus(need.status)]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Запит уже в іншому стані — оновіть сторінку",
        )


async def _get_need(session, need_id: str) -> Need:
    need = await session.get(Need, need_id)
    if need is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Запит не знайдено")
    return need


@router.get("", response_model=list[NeedOut])
async def list_needs(
    session: SessionDep,
    user: CurrentUser,
    scope: Literal["all", "mine", "assigned", "archive"] = "all",
    status_filter: Annotated[NeedStatus | None, Query(alias="status")] = None,
    category: Category | None = None,
    urgency: Urgency | None = None,
    q: str | None = None,
) -> list[NeedOut]:
    stmt = select(Need)

    if scope == "mine":
        stmt = stmt.where(Need.author_id == user.id)
    elif scope == "assigned":
        stmt = stmt.where(Need.assignee_id == user.id)
    elif scope == "archive":
        stmt = stmt.where(Need.status.in_([NeedStatus.COMPLETED, NeedStatus.CANCELLED]))
    else:
        # Загальна дошка — тільки живі запити.
        stmt = stmt.where(Need.status.in_([NeedStatus.OPEN, NeedStatus.IN_PROGRESS, NeedStatus.PENDING]))

    if status_filter is not None:
        stmt = stmt.where(Need.status == status_filter)
    if category is not None:
        stmt = stmt.where(Need.category == category)
    if urgency is not None:
        stmt = stmt.where(Need.urgency == urgency)
    if q and q.strip():
        stmt = stmt.where(Need.search_text.like(f"%{normalize(q)}%"))

    rows = (await session.scalars(stmt)).unique().all()
    rows = sorted(
        rows,
        key=lambda n: (URGENCY_ORDER.get(Urgency(n.urgency), 9), -n.created_at.timestamp()),
    )
    return [NeedOut.model_validate(n) for n in rows]


@router.post("", response_model=NeedOut, status_code=status.HTTP_201_CREATED)
async def create_need(
    data: NeedCreate,
    session: SessionDep,
    user: Annotated[User, Depends(require_roles(Role.MILITARY))],
) -> NeedOut:
    need = Need(
        title=data.title.strip(),
        description=data.description.strip(),
        category=data.category,
        urgency=data.urgency,
        quantity=data.quantity,
        unit=data.unit.strip() or "шт",
        location=data.location,
        author_id=user.id,
        status=NeedStatus.OPEN,
    )
    need.sync_search_text()
    session.add(need)
    await session.flush()
    await log_activity(
        session, ActivityKind.NEED_CREATED, actor_id=user.id, need_id=need.id,
        title=need.title, urgency=str(need.urgency), category=str(need.category),
    )
    await session.commit()
    await session.refresh(need)
    return NeedOut.model_validate(need)


@router.get("/{need_id}", response_model=NeedDetailOut)
async def need_detail(need_id: str, session: SessionDep, user: CurrentUser) -> NeedDetailOut:
    need = await _get_need(session, need_id)

    history = (
        await session.scalars(
            select(Activity).where(Activity.need_id == need_id).order_by(Activity.created_at)
        )
    ).unique().all()
    donations = (
        await session.scalars(select(ItemDonation).where(ItemDonation.need_id == need_id))
    ).unique().all()
    funds = (
        await session.scalars(select(Fund).where(Fund.need_id == need_id))
    ).unique().all()

    return NeedDetailOut(
        need=NeedOut.model_validate(need),
        history=[ActivityOut.model_validate(a) for a in history],
        donations=[DonationOut.model_validate(d) for d in donations],
        funds=[FundOut.model_validate(f) for f in funds],
    )


@router.post("/{need_id}/take", response_model=NeedOut)
async def take_need(
    need_id: str,
    session: SessionDep,
    user: Annotated[User, Depends(require_roles(Role.VOLUNTEER))],
) -> NeedOut:
    need = await _get_need(session, need_id)
    _check_transition(need, NeedStatus.IN_PROGRESS)
    if need.assignee_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Запит уже взяв інший волонтер")

    need.assignee_id = user.id
    need.status = NeedStatus.IN_PROGRESS
    await log_activity(
        session, ActivityKind.NEED_TAKEN, actor_id=user.id, need_id=need.id, title=need.title
    )
    await session.commit()
    await session.refresh(need)
    return NeedOut.model_validate(need)


@router.post("/{need_id}/release", response_model=NeedOut)
async def release_need(need_id: str, session: SessionDep, user: CurrentUser) -> NeedOut:
    """Волонтер відмовляється від запиту — той повертається на дошку."""
    need = await _get_need(session, need_id)
    if need.assignee_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Запит закріплений не за вами")
    _check_transition(need, NeedStatus.OPEN)

    need.assignee_id = None
    need.status = NeedStatus.OPEN
    await log_activity(
        session, ActivityKind.NEED_RELEASED, actor_id=user.id, need_id=need.id, title=need.title
    )
    await session.commit()
    await session.refresh(need)
    return NeedOut.model_validate(need)


@router.post("/{need_id}/submit", response_model=NeedOut)
async def submit_need(
    need_id: str, data: CommentIn, session: SessionDep, user: CurrentUser
) -> NeedOut:
    """Волонтер повідомляє, що виконав. Остаточне слово — за автором."""
    need = await _get_need(session, need_id)
    if need.assignee_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Запит закріплений не за вами")
    _check_transition(need, NeedStatus.PENDING)

    need.status = NeedStatus.PENDING
    await log_activity(
        session, ActivityKind.NEED_SUBMITTED, actor_id=user.id, need_id=need.id,
        title=need.title, comment=data.comment,
    )
    await session.commit()
    await session.refresh(need)
    return NeedOut.model_validate(need)


@router.post("/{need_id}/confirm", response_model=NeedOut)
async def confirm_need(
    need_id: str, data: CommentIn, session: SessionDep, user: CurrentUser
) -> NeedOut:
    need = await _get_need(session, need_id)
    if need.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Підтвердити може лише автор запиту")
    _check_transition(need, NeedStatus.COMPLETED)

    need.status = NeedStatus.COMPLETED
    need.completed_at = utcnow()
    await log_activity(
        session, ActivityKind.NEED_CONFIRMED, actor_id=user.id, need_id=need.id,
        title=need.title, comment=data.comment, assignee_id=need.assignee_id,
    )
    await session.commit()
    await session.refresh(need)
    return NeedOut.model_validate(need)


@router.post("/{need_id}/reject", response_model=NeedOut)
async def reject_need(
    need_id: str, data: CommentIn, session: SessionDep, user: CurrentUser
) -> NeedOut:
    """Автор не приймає роботу — запит лишається за тим самим волонтером."""
    need = await _get_need(session, need_id)
    if need.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Відхилити може лише автор запиту")
    _check_transition(need, NeedStatus.IN_PROGRESS)

    need.status = NeedStatus.IN_PROGRESS
    await log_activity(
        session, ActivityKind.NEED_REJECTED, actor_id=user.id, need_id=need.id,
        title=need.title, comment=data.comment,
    )
    await session.commit()
    await session.refresh(need)
    return NeedOut.model_validate(need)


@router.post("/{need_id}/cancel", response_model=NeedOut)
async def cancel_need(
    need_id: str, data: CommentIn, session: SessionDep, user: CurrentUser
) -> NeedOut:
    need = await _get_need(session, need_id)
    if need.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Скасувати може лише автор запиту")
    _check_transition(need, NeedStatus.CANCELLED)

    need.status = NeedStatus.CANCELLED
    await log_activity(
        session, ActivityKind.NEED_CANCELLED, actor_id=user.id, need_id=need.id,
        title=need.title, comment=data.comment,
    )
    await session.commit()
    await session.refresh(need)
    return NeedOut.model_validate(need)
