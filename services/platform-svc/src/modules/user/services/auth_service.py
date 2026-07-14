"""Authentication and authorisation service.

Handles user registration, login (JWT issue), token refresh, and logout.
Uses bcrypt via passlib for password hashing and PyJWT for JWTs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, ErrorCode, invalid_arg, not_found
from libs.common.logging import get_logger
from .config import UserServiceConfig, config
from .models.role import Role
from .models.store import Store
from .models.user import User, UserStoreLink

logger = get_logger(__name__)

# Shared bcrypt context (lazy singleton)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return _pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify *plain* against *hashed*."""
    return _pwd_context.verify(plain, hashed)


class AuthService:
    """Authentication business logic."""

    def __init__(
        self, db_factory: type[AsyncSession] | Any, config: UserServiceConfig
    ) -> None:
        # db_factory is a callable that returns an AsyncSession
        self._db_factory = db_factory
        self._config = config

    # ── Public API ──

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        phone: str | None = None,
        store_name: str | None = None,
    ) -> dict[str, Any]:
        """Register a new user with an initial store.

        Returns:
            A dict with ``access_token``, ``refresh_token``, ``expires_in``,
            and ``user`` (serialisable dict).
        """
        # --- Validation ---
        _validate_username(username)
        _validate_email(email)
        _validate_password(password)

        async with self._db_factory() as session:
            # Check uniqueness
            existing = await session.execute(
                select(User).where(
                    (User.username == username) | (User.email == email)
                )
            )
            if existing.scalar_one_or_none():
                raise AppError(
                    ErrorCode.DUPLICATE_RESOURCE,
                    "Username or email already exists",
                )

            # Create user
            now = datetime.utcnow()
            user = User(
                user_id=str(uuid.uuid4()),
                username=username,
                email=email,
                phone=phone,
                password_hash=_hash_password(password),
                status="active",
                created_at=now,
                updated_at=now,
            )

            # Assign default role (merchant_admin)
            role = await self._get_or_create_role(session, "merchant_admin")
            user.role_id = role.role_id

            session.add(user)
            await session.flush()  # get user_id

            # Create default store
            store = Store(
                store_id=str(uuid.uuid4()),
                name=store_name or f"{username}'s Store",
                status="active",
                created_at=datetime.utcnow(),
            )
            session.add(store)
            await session.flush()

            # Link user <-> store
            link = UserStoreLink(user_id=user.user_id, store_id=store.store_id)
            session.add(link)
            user.current_store_id = store.store_id

            await session.commit()

            # Re-fetch with relationships
            await session.refresh(user, attribute_names=["role", "stores"])

            logger.info(
                "user.registered",
                user_id=user.user_id,
                username=username,
                store_id=store.store_id,
            )

        return self._build_auth_response(user)

    async def login(
        self, account: str, password: str
    ) -> dict[str, Any]:
        """Authenticate a user by email or phone.

        Returns:
            Same shape as :meth:`register`.
        """
        async with self._db_factory() as session:
            user = await self._find_user_by_account(session, account)
            if user is None:
                raise not_found("User", account)

            if user.status != "active":
                raise AppError(
                    ErrorCode.PERMISSION_DENIED,
                    f"Account is {user.status}",
                )

            if not _verify_password(password, user.password_hash):
                raise invalid_arg("password", "Incorrect password")

            await session.refresh(user, attribute_names=["role", "stores"])

            logger.info("user.login", user_id=user.user_id)

        return self._build_auth_response(user)

    async def refresh_token(
        self, refresh_token: str
    ) -> dict[str, Any]:
        """Issue a new access token from a valid refresh token.

        Returns:
            Same shape as :meth:`register`.
        """
        try:
            payload = jwt.decode(
                refresh_token,
                self._config.jwt_secret,
                algorithms=[self._config.jwt_algorithm],
                options={"require": ["user_id", "type"]},
            )
        except jwt.ExpiredSignatureError:
            raise AppError(ErrorCode.TOKEN_EXPIRED, "Refresh token expired")
        except jwt.InvalidTokenError as e:
            raise invalid_arg("refresh_token", str(e))

        if payload.get("type") != "refresh":
            raise invalid_arg("refresh_token", "Not a refresh token")

        async with self._db_factory() as session:
            user = await session.get(User, payload["user_id"])
            if user is None:
                raise not_found("User", payload["user_id"])
            if user.status != "active":
                raise AppError(
                    ErrorCode.PERMISSION_DENIED,
                    f"Account is {user.status}",
                )
            await session.refresh(user, attribute_names=["role", "stores"])

        return self._build_auth_response(user)

    async def logout(self, user_id: str) -> None:
        """Log out a user.

        Currently a no-op (client-side token invalidation).  In production
        this would add the refresh token to a Redis blacklist.
        """
        logger.info("user.logout", user_id=user_id)

    # ── JWT helpers ──

    def generate_access_token(self, user: User) -> str:
        """Generate a short-lived access JWT."""
        payload = self._build_jwt_payload(user)
        payload["type"] = "access"
        payload["exp"] = datetime.now(timezone.utc) + timedelta(
            minutes=self._config.access_token_expire_minutes
        )
        return jwt.encode(payload, self._config.jwt_secret, algorithm=self._config.jwt_algorithm)

    def generate_refresh_token(self, user: User) -> str:
        """Generate a long-lived refresh JWT."""
        payload = self._build_jwt_payload(user)
        payload["type"] = "refresh"
        payload["exp"] = datetime.now(timezone.utc) + timedelta(
            days=self._config.refresh_token_expire_days
        )
        return jwt.encode(payload, self._config.jwt_secret, algorithm=self._config.jwt_algorithm)

    def decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT.  Raises ``AppError`` on failure."""
        try:
            return jwt.decode(
                token,
                self._config.jwt_secret,
                algorithms=[self._config.jwt_algorithm],
            )
        except jwt.ExpiredSignatureError:
            raise AppError(ErrorCode.TOKEN_EXPIRED, "Token expired")
        except jwt.InvalidTokenError as e:
            raise invalid_arg("token", str(e))

    # ── Internals ──

    async def _find_user_by_account(
        self, session: AsyncSession, account: str
    ) -> User | None:
        """Look up a user by email or phone."""
        stmt = select(User).where(
            (User.email == account) | (User.phone == account)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_or_create_role(self, session: AsyncSession, name: str) -> Role:
        """Get an existing role or create it with default permissions."""
        result = await session.execute(select(Role).where(Role.name == name))
        role = result.scalar_one_or_none()
        if role is not None:
            return role

        default_permissions = _DEFAULT_ROLE_PERMISSIONS.get(name, [])
        role = Role(
            role_id=str(uuid.uuid4()),
            name=name,
            permissions=default_permissions,
            description=f"Auto-created role: {name}",
        )
        session.add(role)
        await session.flush()
        return role

    def _build_jwt_payload(self, user: User) -> dict[str, Any]:
        """Build the standard JWT claims payload from a user."""
        permissions: list[str] = []
        if user.role:
            permissions = user.role.permissions if isinstance(user.role.permissions, list) else []

        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role.name if user.role else None,
            "role_id": user.role.role_id if user.role else None,
            "store_id": user.current_store_id,
            "permissions": permissions,
            "iat": datetime.now(timezone.utc),
        }

    def _build_auth_response(self, user: User) -> dict[str, Any]:
        """Construct the auth response dict."""
        access_token = self.generate_access_token(user)
        refresh_token = self.generate_refresh_token(user)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": self._config.access_token_expire_minutes * 60,
            "user": _user_to_dict(user),
        }


# ── Role defaults ──

_DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "super_admin": ["*"],
    "platform_operator": [
        "product:read",
        "product:write",
        "user:read",
        "user:write",
        "script:read",
        "script:write",
        "live:read",
        "live:write",
        "analytics:read",
    ],
    "content_reviewer": [
        "product:read",
        "script:read",
        "live:read",
    ],
    "merchant_admin": [
        "product:read",
        "product:write",
        "user:read",
        "user:write",
        "script:read",
        "script:write",
        "live:read",
        "live:write",
        "analytics:read",
        "store:read",
        "store:write",
    ],
    "merchant_editor": [
        "product:read",
        "product:write",
        "script:read",
        "script:write",
        "live:read",
        "analytics:read",
    ],
    "merchant_viewer": [
        "product:read",
        "script:read",
        "live:read",
        "analytics:read",
    ],
}


# ── Validation helpers ──


def _validate_username(username: str) -> None:
    if not username or len(username) < 3:
        raise invalid_arg("username", "Must be at least 3 characters")
    if len(username) > 100:
        raise invalid_arg("username", "Must be at most 100 characters")


def _validate_email(email: str) -> None:
    if not email or "@" not in email or "." not in email:
        raise invalid_arg("email", "Invalid email format")


def _validate_password(password: str) -> None:
    if not password or len(password) < 6:
        raise invalid_arg("password", "Must be at least 6 characters")


def _validate_phone(phone: str | None) -> None:
    if phone is not None and (len(phone) < 5 or len(phone) > 20):
        raise invalid_arg("phone", "Invalid phone number length")


# ── Serialisation helper ──


def _user_to_dict(user: User) -> dict[str, Any]:
    """Convert a ``User`` ORM instance to a plain dict for JSON serialisation."""
    role_dict: dict[str, Any] | None = None
    if user.role:
        role_dict = {
            "role_id": user.role.role_id,
            "name": user.role.name,
            "permissions": user.role.permissions,
            "description": user.role.description,
        }

    stores_list: list[dict[str, Any]] = []
    for store in (user.stores or []):
        stores_list.append(_store_to_dict(store))

    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "role": role_dict,
        "stores": stores_list,
        "current_store_id": user.current_store_id,
        "status": user.status,
        "created_at": int(user.created_at.timestamp() * 1000) if user.created_at else 0,
        "updated_at": int(user.updated_at.timestamp() * 1000) if user.updated_at else 0,
    }


def _store_to_dict(store: Store) -> dict[str, Any]:
    """Convert a ``Store`` ORM instance to a plain dict."""
    return {
        "store_id": store.store_id,
        "name": store.name,
        "logo_url": store.logo_url,
        "platforms": store.platforms,
        "status": store.status,
    }
