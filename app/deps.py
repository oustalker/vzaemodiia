"""Спільні залежності: авторизація, перевірка ролей, запис подій."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .enums import ActivityKind, Role
from .models import Activity, User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Потрібен вхід до акаунту")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сесія завершилась, увійдіть знову")
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Акаунт не знайдено")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable:
    """Перевірка ролі на рівні API, а не приховуванням кнопки в інтерфейсі."""

    allowed: set[Role] = set(roles)

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Ця дія доступна іншій ролі",
            )
        return user

    return dependency


async def log_activity(
    session: AsyncSession,
    kind: ActivityKind,
    *,
    actor_id: str | None = None,
    need_id: str | None = None,
    fund_id: str | None = None,
    donation_id: str | None = None,
    **payload,
) -> Activity:
    """Кладе подію в журнал. Коміт лишається на виклику вище."""
    activity = Activity(
        kind=str(kind),
        actor_id=actor_id,
        need_id=need_id,
        fund_id=fund_id,
        donation_id=donation_id,
        payload={k: v for k, v in payload.items() if v is not None},
    )
    session.add(activity)
    return activity


def ensure(condition: bool, code: int, message: str) -> None:
    if not condition:
        raise HTTPException(code, message)


def any_of(value, options: Iterable) -> bool:
    return value in set(options)
