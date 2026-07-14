"""
Mock Douyin (TikTok) platform adapter.

Simulates Douyin API calls for product sync and OAuth validation.
"""

from typing import Any

from libs.common.logging import get_logger

from .base import BasePlatformAdapter

logger = get_logger(__name__)


class DouyinAdapter(BasePlatformAdapter):
    """Mock adapter for Douyin platform."""

    async def push_product(self, product_data: dict[str, Any], access_token: str) -> dict[str, Any]:
        """Simulate pushing a product to Douyin."""
        title = product_data.get("title", "unknown")
        logger.info("douyin.push_product", title=title)
        return {
            "platform_product_id": f"dy_{product_data.get('product_id', 'unknown')}",
            "error": "",
        }

    async def pull_product(self, platform_product_id: str, access_token: str) -> dict[str, Any]:
        """Simulate pulling a product from Douyin."""
        logger.info("douyin.pull_product", platform_product_id=platform_product_id)
        return {
            "product_id": platform_product_id,
            "title": f"Douyin Product {platform_product_id}",
            "price": 12900,
            "description": "Synced from Douyin (mock)",
        }

    async def validate_auth_code(self, auth_code: str) -> dict[str, Any]:
        """Exchange OAuth code for token (mock)."""
        logger.info("douyin.validate_auth_code", auth_code=auth_code[:8])
        return {
            "access_token": f"dy_token_{auth_code[:8]}",
            "expires_in": 86400,
            "platform_store_id": f"dy_store_{auth_code[-4:]}",
            "platform_store_name": f"Douyin Store {auth_code[-4:]}",
        }
