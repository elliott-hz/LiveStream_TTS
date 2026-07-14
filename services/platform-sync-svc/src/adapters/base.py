"""
Base adapter interface for third-party platform APIs.

All platform-specific adapters (Taobao, Douyin, JD, etc.) must
implement this ABC.
"""

from abc import ABC, abstractmethod
from typing import Any


class BasePlatformAdapter(ABC):
    """Abstract interface for syncing products to/from a platform."""

    @abstractmethod
    async def push_product(self, product_data: dict[str, Any], access_token: str) -> dict[str, Any]:
        """Push a product to the platform.

        Returns:
            dict with keys: platform_product_id (str), and optional error (str).
        """
        ...

    @abstractmethod
    async def pull_product(self, platform_product_id: str, access_token: str) -> dict[str, Any]:
        """Pull product data from the platform.

        Returns:
            dict with product fields from the platform.
        """
        ...

    @abstractmethod
    async def validate_auth_code(self, auth_code: str) -> dict[str, Any]:
        """Exchange an OAuth auth code for an access token (mock).

        Returns:
            dict with keys: access_token (str), expires_in (int),
            platform_store_id (str), platform_store_name (str).
        """
        ...
