"""
Product sync orchestration service.

Manages SyncJob lifecycle:
  Create job -> call platform adapter -> update status.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import not_found, invalid_arg
from libs.common.logging import get_logger

from models.platform import SyncJob, PlatformStoreBinding
from adapters.taobao import TaobaoAdapter
from adapters.douyin import DouyinAdapter

logger = get_logger(__name__)

_ADAPTERS: dict[str, Any] = {
    "taobao": TaobaoAdapter(),
    "douyin": DouyinAdapter(),
}

VALID_DIRECTIONS = {"push", "pull"}
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class SyncService:
    """Orchestrate product sync operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_product(
        self,
        product_id: str,
        platform: str,
        direction: str = "push",
    ) -> SyncJob:
        """Create a sync job and execute it against the platform adapter."""
        if not product_id:
            raise invalid_arg("product_id", "must not be empty")
        if not platform:
            raise invalid_arg("platform", "must not be empty")
        if direction not in VALID_DIRECTIONS:
            raise invalid_arg("direction", f"must be one of {VALID_DIRECTIONS}")

        # Create job
        job = SyncJob(
            product_id=product_id,
            platform=platform,
            direction=direction,
            status="pending",
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)

        # Find a binding for token
        token = await self._get_platform_token(platform)

        # Execute via adapter
        job.status = "in_progress"
        await self.db.flush()

        try:
            adapter = _ADAPTERS.get(platform)
            if not adapter:
                raise ValueError(f"No adapter for platform: {platform}")

            product_data = {"product_id": product_id, "title": f"Product {product_id}"}

            if direction == "push":
                result = await adapter.push_product(product_data, token)
                job.platform_product_id = result.get("platform_product_id", "")
                if result.get("error"):
                    job.status = "failed"
                    job.error_message = result["error"]
                else:
                    job.status = "success"
            else:  # pull
                result = await adapter.pull_product(product_id, token)
                job.platform_product_id = result.get("product_id", "")
                job.status = "success"

        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            logger.warning("sync.job_failed", job_id=job.job_id, error=str(exc))

        job.retry_count = 0
        job.completed_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(job)

        logger.info("sync.job_completed", job_id=job.job_id, status=job.status)
        return job

    async def bulk_sync(
        self,
        product_ids: list[str],
        platforms: list[str],
    ) -> list[SyncJob]:
        """Create and execute sync jobs for multiple products/platforms."""
        jobs: list[SyncJob] = []
        for pid in product_ids:
            for plat in platforms:
                job = await self.sync_product(pid, plat, "push")
                jobs.append(job)
        return jobs

    async def get_sync_job(self, job_id: str) -> SyncJob:
        """Fetch a single sync job."""
        stmt = select(SyncJob).where(SyncJob.job_id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalars().one_or_none()
        if not job:
            raise not_found("SyncJob", job_id)
        return job

    async def list_sync_jobs(
        self,
        store_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[SyncJob], int]:
        """Paginated listing of sync jobs."""
        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        conditions: list[Any] = []

        if status:
            conditions.append(SyncJob.status == status)

        # Count
        count_stmt = select(func.count()).select_from(SyncJob).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total_count: int = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(SyncJob)
            .where(*conditions)
            .order_by(desc(SyncJob.created_at))
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())
        return jobs, total_count

    async def _get_platform_token(self, platform: str) -> str:
        """Get an active access token for the platform."""
        stmt = (
            select(PlatformStoreBinding)
            .where(
                PlatformStoreBinding.platform == platform,
                PlatformStoreBinding.status == "active",
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        binding = result.scalars().first()
        if binding:
            return binding.access_token_encrypted
        return f"mock_token_{platform}"
