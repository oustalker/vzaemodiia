"""Реєстрація, вхід, власний профіль."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep, log_activity
from ..enums import ActivityKind
from ..models import User
from ..schemas import LoginIn, ProfileUpdate, RegisterIn, TokenOut, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, session: SessionDep) -> TokenOut:
    exists = await session.scalar(select(User).where(User.username == data.username))
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Це імʼя вже зайняте, оберіть інше")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        role=data.role,
        callsign=(data.callsign or None),
        contact=(data.contact or None),
    )
    session.add(user)
    await session.flush()
    await log_activity(
        session,
        ActivityKind.USER_JOINED,
        actor_id=user.id,
        role=str(user.role),
    )
    await session.commit()

    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
async def login(data: LoginIn, session: SessionDep) -> TokenOut:
    user = await session.scalar(select(User).where(User.username == data.username))
    # Однакова відповідь на неіснуючий логін і хибний пароль —
    # щоб не можна було перебором зʼясувати, хто зареєстрований.
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Невірне імʼя користувача або пароль")
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(data: ProfileUpdate, user: CurrentUser, session: SessionDep) -> UserOut:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
