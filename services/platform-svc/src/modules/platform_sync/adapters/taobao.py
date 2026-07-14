"""
Mock Taobao platform adapter.

Simulates Taobao API calls for product sync and OAuth validation.
"""

from typing import Any

from libs.common.logging import get_logger

from .base import BasePlatformAdapter

logger = get_logger(__name__)


class TaobaoAdapter(BasePlatformAdapter):
    """Mock adapter for Taobao platform."""

    async def push_product(self, product_data: dict[str, Any], access_token: str) -> dict[str, Any]:
        """Simulate pushing a product to Taobao."""
        title = product_data.get("title", "unknown")
        logger.info("taobao.push_product", title=title)
        # Simulate API call — return mock platform product ID
        return {
            "platform_product_id": f"tb_{product_data.get('product_id', 'unknown')}",
            "error": "",
        }

    async def pull_product(self, platform_product_id: str, access_token: str) -> dict[str, Any]:
        """Simulate pulling a product from Taobao."""
        logger.info("taobao.pull_product", platform_product_id=platform_product_id)
        return {
            "product_id": platform_product_id,
            "title": f"Taobao Product {platform_product_id}",
            "price": 9900,
            "description": "Synced from Taobao (mock)",
        }

    async def validate_auth_code(self, auth_code: str) -> dict[str, Any]:
        """Exchange OAuth code for token (mock)."""
        logger.info("taobao.validate_auth_code", auth_code=auth_code[:8])
        return {
            "access_token": f"tb_token_{auth_code[:8]}",
            "expires_in": 7200,
            "platform_store_id": f"tb_store_{auth_code[-4:]}",
            "platform_store_name": f"Taobao Store {auth_code[-4:]}",
        }
