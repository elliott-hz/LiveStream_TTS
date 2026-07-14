"""
Store binding management service.

Handles OAuth-based binding to third-party platforms.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, ErrorCode, invalid_arg, not_found
from libs.common.logging import get_logger

from models.platform import PlatformStoreBinding
from adapters.taobao import TaobaoAdapter
from adapters.douyin import DouyinAdapter

logger = get_logger(__name__)

# Adapter registry
_ADAPTERS: dict[str, Any] = {
    "taobao": TaobaoAdapter(),
    "douyin": DouyinAdapter(),
}

VALID_PLATFORMS = {"taobao", "douyin", "jd", "kuaishou", "pinduoduo"}
VALID_BINDING_STATUSES = {"active", "expired", "revoked"}


class BindingService:
    """Manage store-to-platform OAuth bindings."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def bind_store(
        self,
        store_id: str,
        platform: str,
        auth_code: str,
    ) -> PlatformStoreBinding:
        """Bind a store to a platform using an OAuth auth code."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        if platform not in VALID_PLATFORMS:
            raise invalid_arg("platform", f"must be one of {VALID_PLATFORMS}")
        if not auth_code:
            raise invalid_arg("auth_code", "must not be empty")

        # Mock OAuth: call platform adapter to validate auth code
        adapter = _ADAPTERS.get(platform)
        if not adapter:
            raise AppError(ErrorCode.INVALID_ARGUMENT, f"No adapter for platform: {platform}")

        oauth_result = await adapter.validate_auth_code(auth_code)
        now_ts = int(datetime.utcnow().timestamp())

        binding = PlatformStoreBinding(
            store_id=store_id,
            platform=platform,
            platform_store_id=oauth_result["platform_store_id"],
            platform_store_name=oauth_result["platform_store_name"],
            status="active",
            access_token_encrypted=oauth_result["access_token"],
            token_expires_at=now_ts + oauth_result["expires_in"],
            bound_at=now_ts,
        )
        self.db.add(binding)
        await self.db.flush()
        await self.db.refresh(binding)
        logger.info("binding.created", binding_id=binding.binding_id, platform=platform)
        return binding

    async def unbind_store(self, binding_id: str) -> None:
        """Revoke a store binding."""
        binding = await self._get_binding(binding_id)
        binding.status = "revoked"
        await self.db.flush()
        logger.info("binding.revoked", binding_id=binding_id)

    async def list_bindings(self, store_id: str) -> list[PlatformStoreBinding]:
        """List all bindings for a store."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        stmt = (
            select(PlatformStoreBinding)
            .where(PlatformStoreBinding.store_id == store_id)
            .order_by(PlatformStoreBinding.bound_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_binding(self, binding_id: str) -> PlatformStoreBinding:
        """Fetch a binding by ID."""
        stmt = select(PlatformStoreBinding).where(
            PlatformStoreBinding.binding_id == binding_id
        )
        result = await self.db.execute(stmt)
        binding = result.scalars().one_or_none()
        if not binding:
            raise not_found("PlatformStoreBinding", binding_id)
        return binding
