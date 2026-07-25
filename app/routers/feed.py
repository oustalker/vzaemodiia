"""Стрічка подій, зведення по дошці, дошка пошани, чужі профілі."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from ..deps import CurrentUser, SessionDep
from ..enums import Category, DonationStatus, FundStatus, NeedStatus, Role
from ..labels import (
    CATEGORY_LABELS, CATEGORY_MARKS, DONATION_STATUS_LABELS, FUND_STATUS_LABELS,
    NEED_STATUS_LABELS, ROLE_LABELS, URGENCY_LABELS, as_options,
)
from ..models import Activity, Contribution, Fund, ItemDonation, Need, User
from ..schemas import (
    ActivityOut, ContributionOut, FundOut, LeaderRow, Overview, UserBrief, UserOut,
    UserProfileOut, UserStats,
)

router = APIRouter(prefix="/api", tags=["feed"])


@router.get("/meta")
async def meta() -> dict:
    """Довідники з підписами. Клієнт не тримає власних копій."""
    return {
        "roles": as_options(ROLE_LABELS),
        "need_statuses": as_options(NEED_STATUS_LABELS),
        "urgencies": as_options(URGENCY_LABELS),
        "categories": as_options(CATEGORY_LABELS),
        "category_marks": {str(k): v for k, v in CATEGORY_MARKS.items()},
        "fund_statuses": as_options(FUND_STATUS_LABELS),
        "donation_statuses": as_options(DONATION_STATUS_LABELS),
    }


@router.get("/feed", response_model=list[ActivityOut])
async def feed(
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(default=60, ge=1, le=200),
) -> list[ActivityOut]:
    rows = (
        await session.scalars(
            select(Activity).order_by(Activity.created_at.desc()).limit(limit)
        )
    ).unique().all()
    return [ActivityOut.model_validate(a) for a in rows]


@router.get("/my/contributions")
async def my_contributions(session: SessionDep, user: CurrentUser) -> list[dict]:
    """Внески поточного користувача разом зі збором, до якого вони йшли.

    Потрібно екрану цивільної особи: там головне питання не «скільки
    зібрано взагалі», а «куди пішли саме мої гроші».
    """
    rows = (
        await session.execute(
            select(Contribution, Fund)
            .join(Fund, Fund.id == Contribution.fund_id)
            .where(Contribution.user_id == user.id)
            .order_by(Contribution.created_at.desc())
            .limit(50)
        )
    ).unique().all()
    return [
        {
            "contribution": ContributionOut.model_validate(contribution).model_dump(mode="json"),
            "fund": FundOut.model_validate(fund).model_dump(mode="json"),
        }
        for contribution, fund in rows
    ]


@router.get("/stats/overview", response_model=Overview)
async def overview(session: SessionDep, user: CurrentUser) -> Overview:
    async def count_needs(**where) -> int:
        stmt = select(func.count()).select_from(Need)
        for column, value in where.items():
            stmt = stmt.where(getattr(Need, column) == value)
        return await session.scalar(stmt) or 0

    by_category_rows = (
        await session.execute(
            select(Need.category, func.count())
            .where(Need.status.in_([NeedStatus.OPEN, NeedStatus.IN_PROGRESS]))
            .group_by(Need.category)
        )
    ).all()

    return Overview(
        needs_open=await count_needs(status=NeedStatus.OPEN),
        needs_critical=await session.scalar(
            select(func.count()).select_from(Need)
            .where(Need.urgency == "critical")
            .where(Need.status.in_([NeedStatus.OPEN, NeedStatus.IN_PROGRESS]))
        ) or 0,
        needs_in_progress=await count_needs(status=NeedStatus.IN_PROGRESS),
        needs_completed=await count_needs(status=NeedStatus.COMPLETED),
        funds_active=await session.scalar(
            select(func.count()).select_from(Fund).where(Fund.status == FundStatus.ACTIVE)
        ) or 0,
        funds_raised=await session.scalar(select(func.coalesce(func.sum(Fund.current_amount), 0)))
        or 0,
        donations_available=await session.scalar(
            select(func.count()).select_from(ItemDonation)
            .where(ItemDonation.status == DonationStatus.OFFERED)
        ) or 0,
        volunteers=await session.scalar(
            select(func.count()).select_from(User).where(User.role == Role.VOLUNTEER)
        ) or 0,
        by_category={str(category): count for category, count in by_category_rows},
    )


@router.get("/stats/leaderboard", response_model=list[LeaderRow])
async def leaderboard(session: SessionDep, user: CurrentUser) -> list[LeaderRow]:
    """Волонтери, які закрили найбільше запитів."""
    completed_rows = (
        await session.execute(
            select(Need.assignee_id, func.count())
            .where(Need.status == NeedStatus.COMPLETED)
            .where(Need.assignee_id.is_not(None))
            .group_by(Need.assignee_id)
        )
    ).all()
    contributed_rows = (
        await session.execute(
            select(Contribution.user_id, func.sum(Contribution.amount))
            .group_by(Contribution.user_id)
        )
    ).all()

    completed = dict(completed_rows)
    contributed = dict(contributed_rows)
    user_ids = set(completed) | set(contributed)
    if not user_ids:
        return []

    users = (await session.scalars(select(User).where(User.id.in_(user_ids)))).unique().all()
    rows = [
        LeaderRow(
            user=UserBrief.model_validate(u),
            completed=completed.get(u.id, 0),
            contributed=int(contributed.get(u.id, 0) or 0),
        )
        for u in users
    ]
    rows.sort(key=lambda r: (-r.completed, -r.contributed))
    return rows[:20]


@router.get("/users/{username}", response_model=UserProfileOut)
async def user_profile(username: str, session: SessionDep, viewer: CurrentUser) -> UserProfileOut:
    target = await session.scalar(select(User).where(User.username == username))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Користувача не знайдено")

    async def scalar(stmt) -> int:
        return int(await session.scalar(stmt) or 0)

    stats = UserStats(
        needs_created=await scalar(
            select(func.count()).select_from(Need).where(Need.author_id == target.id)
        ),
        needs_completed=await scalar(
            select(func.count()).select_from(Need)
            .where(Need.assignee_id == target.id, Need.status == NeedStatus.COMPLETED)
        ),
        needs_in_progress=await scalar(
            select(func.count()).select_from(Need)
            .where(Need.assignee_id == target.id, Need.status == NeedStatus.IN_PROGRESS)
        ),
        contributed_total=await scalar(
            select(func.coalesce(func.sum(Contribution.amount), 0))
            .where(Contribution.user_id == target.id)
        ),
        contributions_count=await scalar(
            select(func.count()).select_from(Contribution)
            .where(Contribution.user_id == target.id)
        ),
        donations_offered=await scalar(
            select(func.count()).select_from(ItemDonation)
            .where(ItemDonation.donor_id == target.id)
        ),
        funds_created=await scalar(
            select(func.count()).select_from(Fund).where(Fund.created_by == target.id)
        ),
    )
    return UserProfileOut(user=UserOut.model_validate(target), stats=stats)
