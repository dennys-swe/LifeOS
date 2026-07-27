from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import BaseUserDatabase
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.db.database import get_db
from app.models.user import User
from app.services.category_seed import seed_default_categories

ACCESS_TOKEN_LIFETIME_SECONDS = 60 * 60 * 24 * 7  # 7 dias


class SyncSQLAlchemyUserDatabase(BaseUserDatabase[User, uuid.UUID]):
    """Adapter do fastapi-users sobre uma Session sync (o projeto não usa asyncpg)."""

    def __init__(self, session: Session):
        self.session = session

    async def get(self, id: uuid.UUID) -> Optional[User]:
        return await run_in_threadpool(self.session.get, User, id)

    async def get_by_email(self, email: str) -> Optional[User]:
        def _query() -> Optional[User]:
            return self.session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()

        return await run_in_threadpool(_query)

    async def create(self, create_dict: dict[str, Any]) -> User:
        def _create() -> User:
            user = User(**create_dict)
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
            return user

        return await run_in_threadpool(_create)

    async def update(self, user: User, update_dict: dict[str, Any]) -> User:
        def _update() -> User:
            for key, value in update_dict.items():
                setattr(user, key, value)
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
            return user

        return await run_in_threadpool(_update)

    async def delete(self, user: User) -> None:
        def _delete() -> None:
            self.session.delete(user)
            self.session.commit()

        await run_in_threadpool(_delete)


def get_user_db(session: Session = Depends(get_db)):
    yield SyncSQLAlchemyUserDatabase(session)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def on_after_register(self, user: User, request: Optional[Request] = None) -> None:
        db: Session = self.user_db.session  # type: ignore[attr-defined]
        await run_in_threadpool(seed_default_categories, db, user.id)


def get_user_manager(user_db: SyncSQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.secret_key, lifetime_seconds=ACCESS_TOKEN_LIFETIME_SECONDS)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
