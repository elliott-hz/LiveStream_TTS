"""User CRUD and permission management business logic."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, ErrorCode, invalid_arg, not_found
from libs.common.logging import get_logger
from services.user_svc.src.config import UserServiceConfig
from services.user_svc.src.models.role import Role
from services.user_svc.src.models.store import Store
from services.user_svc.src.models.user import User, UserStoreLink
from services.user_svc.src.services.auth_service import _user_to_dict, _store_to_dict

logger = get_logger(__name__)


class UserService:
    """User and store CRUD, permission checking, and role assignment."""

    def __init__(
        self, db_factory: type[AsyncSession] | Any, config: UserServiceConfig
    ) -> None:
        self._db_factory = db_factory
        self._config = config

    # ── User CRUD ──

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Retrieve a single user by ID."""
        async with self._db_factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                raise not_found("User", user_id)
            await session.refresh(user, attribute_names=["role", "stores"])
            return _user_to_dict(user)

    async def update_user(
        self, user_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update user fields.

        Allowed fields: ``username``, ``email``, ``phone``, ``avatar_url``.
        """
        allowed = {"username", "email", "phone", "avatar_url"}
        sanitised = {k: v for k, v in updates.items() if k in allowed and v is not None}

        if not sanitised:
            raise invalid_arg("updates", "No valid fields to update")

        async with self._db_factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                raise not_found("User", user_id)

            for field, value in sanitised.items():
                setattr(user, field, value)

            await session.commit()
            await session.refresh(user, attribute_names=["role", "stores"])

            logger.info("user.updated", user_id=user_id, fields=list(sanitised.keys()))
            return _user_to_dict(user)

    async def list_users(
        self,
        store_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List users with optional filtering and pagination.

        Returns:
            Dict with ``users`` list, ``page``, ``page_size``, ``total_count``,
            ``total_pages``.
        """
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        async with self._db_factory() as session:
            # Build query
            query = select(User)
            if store_id:
                # Users linked to a store
                query = query.join(UserStoreLink).where(
                    UserStoreLink.store_id == store_id
                )
            if status:
                query = query.where(User.status == status)

            # Count total
            count_query = select(func.count()).select_from(query.subquery())
            total_count = (await session.execute(count_query)).scalar() or 0

            # Paginate
            offset = (page - 1) * page_size
            query = query.offset(offset).limit(page_size).order_by(User.created_at.desc())
            result = await session.execute(query)
            users = result.scalars().all()

            # Fetch relationships
            user_dicts: list[dict[str, Any]] = []
            for u in users:
                await session.refresh(u, attribute_names=["role", "stores"])
                user_dicts.append(_user_to_dict(u))

            return {
                "users": user_dicts,
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": max(1, (total_count + page_size - 1) // page_size),
            }

    # ── Permission ──

    async def check_permission(
        self, user_id: str, permission: str, store_id: str | None = None
    ) -> dict[str, Any]:
        """Check if a user has a specific permission.

        Returns:
            Dict with ``allowed`` (bool) and ``reason`` (str).
        """
        async with self._db_factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                return {"allowed": False, "reason": f"User {user_id} not found"}

            if user.status != "active":
                return {
                    "allowed": False,
                    "reason": f"Account is {user.status}",
                }

            await session.refresh(user, attribute_names=["role"])
            if user.role is None:
                return {
                    "allowed": False,
                    "reason": "User has no role assigned",
                }

            perms = user.role.permissions
            if not isinstance(perms, list):
                return {"allowed": False, "reason": "Invalid permissions format"}

            # super_admin wildcard
            if "*" in perms:
                return {"allowed": True, "reason": "Super admin"}

            if permission in perms:
                return {"allowed": True, "reason": "Permission granted"}

            # Check if store-level permission applies
            if store_id and user.current_store_id != store_id:
                return {
                    "allowed": False,
                    "reason": "Permission not applicable to this store",
                }

            return {"allowed": False, "reason": f"Missing permission: {permission}"}

    async def assign_role(
        self, user_id: str, role_id: str, store_id: str | None = None
    ) -> dict[str, Any]:
        """Assign a role to a user.

        If *store_id* is provided, also ensure the user is linked to that store.
        """
        async with self._db_factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                raise not_found("User", user_id)

            role = await session.get(Role, role_id)
            if role is None:
                raise not_found("Role", role_id)

            user.role_id = role.role_id

            if store_id:
                # Ensure user-store link exists
                link_exists = await session.get(
                    UserStoreLink, (user_id, store_id)
                )
                if link_exists is None:
                    session.add(UserStoreLink(user_id=user_id, store_id=store_id))
                    user.current_store_id = store_id

            await session.commit()
            await session.refresh(user, attribute_names=["role", "stores"])

            logger.info(
                "user.role_assigned",
                user_id=user_id,
                role_id=role_id,
                role_name=role.name,
            )
            return _user_to_dict(user)

    # ── Store ──

    async def list_stores(self, user_id: str) -> list[dict[str, Any]]:
        """List all stores linked to a user."""
        async with self._db_factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                raise not_found("User", user_id)

            await session.refresh(user, attribute_names=["stores"])
            return [_store_to_dict(s) for s in (user.stores or [])]

    async def switch_store(self, user_id: str, store_id: str) -> dict[str, Any]:
        """Switch the user's current active store."""
        async with self._db_factory() as session:
            user = await session.get(User, user_id)
            if user is None:
                raise not_found("User", user_id)

            # Verify store exists and user is linked
            store = await session.get(Store, store_id)
            if store is None:
                raise not_found("Store", store_id)

            link = await session.get(UserStoreLink, (user_id, store_id))
            if link is None:
                raise AppError(
                    ErrorCode.PERMISSION_DENIED,
                    f"User {user_id} is not linked to store {store_id}",
                )

            user.current_store_id = store_id
            await session.commit()
            await session.refresh(store)

            logger.info("user.switched_store", user_id=user_id, store_id=store_id)
            return _store_to_dict(store)
