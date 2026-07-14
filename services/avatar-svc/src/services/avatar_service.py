"""
AvatarService — business logic for avatar CRUD and clone task management.

Every public method corresponds to one RPC. Methods raise AppError on failure.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, ErrorCode, not_found, invalid_arg
from libs.common.logging import get_logger

from models.avatar import Avatar, CloneTask

logger = get_logger(__name__)

# ── Constants ──

VALID_AVATAR_TYPES = {"2d_real", "3d_cartoon", "2d_cartoon"}
VALID_AVATAR_STATUSES = {"active", "cloning", "pending_audit", "rejected"}
VALID_CLONE_STATUSES = {"uploading", "processing", "training", "success", "failed"}
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class AvatarService:
    """Avatar business logic — injected with a DB session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────────────────
    #  Avatar CRUD
    # ──────────────────────────────────────────────────────────

    async def create_avatar(
        self,
        store_id: str,
        name: str,
        avatar_type: str = "2d_real",
        custom_params: dict | None = None,
        created_by: str | None = None,
    ) -> Avatar:
        """Create a new avatar in active status."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        if not name or not name.strip():
            raise invalid_arg("name", "must not be empty")
        type_norm = avatar_type.lower().replace("-", "_")
        if type_norm not in VALID_AVATAR_TYPES:
            raise invalid_arg("avatar_type", f"must be one of {VALID_AVATAR_TYPES}")

        avatar = Avatar(
            store_id=store_id,
            name=name.strip(),
            avatar_type=type_norm,
            status="active",
            custom_params=custom_params or {},
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(avatar)
        await self.db.flush()
        await self.db.refresh(avatar)

        logger.info("avatar.created", avatar_id=avatar.avatar_id, store_id=store_id)
        return avatar

    async def get_avatar(self, avatar_id: str) -> Avatar:
        """Fetch a single avatar by ID."""
        if not avatar_id:
            raise invalid_arg("avatar_id", "must not be empty")

        stmt = select(Avatar).where(Avatar.avatar_id == avatar_id)
        result = await self.db.execute(stmt)
        avatar = result.scalars().one_or_none()
        if not avatar:
            raise not_found("Avatar", avatar_id)
        return avatar

    async def update_avatar(
        self,
        avatar_id: str,
        name: str | None = None,
        custom_params: dict | None = None,
        updated_by: str | None = None,
    ) -> Avatar:
        """Partially update an avatar's scalar fields."""
        avatar = await self.get_avatar(avatar_id)

        if name is not None:
            if not name.strip():
                raise invalid_arg("name", "must not be empty")
            avatar.name = name.strip()
        if custom_params is not None:
            avatar.custom_params = custom_params
        if updated_by is not None:
            avatar.updated_by = updated_by

        avatar.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(avatar)
        logger.info("avatar.updated", avatar_id=avatar_id)
        return avatar

    async def delete_avatar(self, avatar_id: str) -> None:
        """Hard-delete an avatar."""
        avatar = await self.get_avatar(avatar_id)
        await self.db.delete(avatar)
        await self.db.flush()
        logger.info("avatar.deleted", avatar_id=avatar_id)

    async def list_avatars(
        self,
        store_id: str,
        avatar_type: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Avatar], int]:
        """Paginated avatar listing with optional filters."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")

        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        conditions = [Avatar.store_id == store_id]

        if avatar_type:
            type_norm = avatar_type.lower().replace("-", "_")
            if type_norm not in VALID_AVATAR_TYPES:
                raise invalid_arg("avatar_type", f"must be one of {VALID_AVATAR_TYPES}")
            conditions.append(Avatar.avatar_type == type_norm)

        # Count
        count_stmt = select(func.count()).select_from(Avatar).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total_count: int = total_result.scalar() or 0

        # Fetch page
        offset = (page - 1) * page_size
        stmt = (
            select(Avatar)
            .where(*conditions)
            .order_by(Avatar.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        avatars = list(result.scalars().all())

        return avatars, total_count

    # ──────────────────────────────────────────────────────────
    #  Clone Task Management
    # ──────────────────────────────────────────────────────────

    async def start_clone(
        self,
        avatar_id: str,
        video_data: bytes | None = None,
        duration_seconds: int = 0,
    ) -> CloneTask:
        """Start an avatar clone task."""
        avatar = await self.get_avatar(avatar_id)

        if avatar.status not in ("active", "rejected"):
            raise AppError(
                ErrorCode.RESOURCE_IN_USE,
                f"Avatar {avatar_id} is not in a clonable status (current: {avatar.status})",
            )

        avatar.status = "cloning"
        avatar.updated_at = datetime.utcnow()

        task = CloneTask(
            avatar_id=avatar_id,
            status="uploading",
            progress_percent=0,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        logger.info("avatar.clone.started", avatar_id=avatar_id, task_id=task.task_id)
        return task

    async def get_clone_task(self, task_id: str) -> CloneTask:
        """Fetch a clone task by ID."""
        if not task_id:
            raise invalid_arg("task_id", "must not be empty")

        stmt = select(CloneTask).where(CloneTask.task_id == task_id)
        result = await self.db.execute(stmt)
        task = result.scalars().one_or_none()
        if not task:
            raise not_found("CloneTask", task_id)
        return task
