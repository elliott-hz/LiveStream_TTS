"""
User Profile Lookup — Retrieves user profile data for routing decisions.

In production:
  - Redis for hot data (tags, recent behavior)
  - PostgreSQL for cold data (purchase history, membership tier)

For MVP:
  - Mock in-memory store with realistic defaults
"""

from __future__ import annotations

import json
from typing import Any

from libs.common.logging import get_logger

logger = get_logger(__name__)


class ProfileLookup:
    """User profile lookup service.

    Returns structured profile dicts with tags about the user.
    In production, this wraps Redis + PostgreSQL lookups.
    """

    def __init__(self) -> None:
        # Mock data store: {user_id: profile_dict}
        # In production, this would be a Redis client + DB connection
        self._mock_store: dict[str, dict[str, Any]] = {}

    def seed(self, user_id: str, profile: dict[str, Any]) -> None:
        """Seed mock profile data for testing."""
        self._mock_store[user_id] = profile

    async def lookup(self, platform_user_id: str, platform: str = "") -> dict[str, Any]:
        """Look up a user's profile.

        Returns a structured dict with at least:
          - user_id: str
          - is_new: bool (first visit to this live room)
          - is_vip: bool
          - purchase_count: int
          - total_spent: float
          - tags: list[str]
        """
        composite_id = f"{platform}:{platform_user_id}" if platform else platform_user_id

        # Check mock store first
        if composite_id in self._mock_store:
            logger.debug("profile.cache_hit", user_id=composite_id)
            return self._mock_store[composite_id]

        # In production: Redis GET → PostgreSQL fallback
        # For MVP: return sensible defaults
        profile = self._default_profile(composite_id)
        logger.debug("profile.mock_default", user_id=composite_id, is_new=profile["is_new"])
        return profile

    async def batch_lookup(
        self, user_ids: list[tuple[str, str]]
    ) -> dict[str, dict[str, Any]]:
        """Batch lookup multiple users. Each tuple is (platform_user_id, platform)."""
        results: dict[str, dict[str, Any]] = {}
        for platform_user_id, platform in user_ids:
            results[platform_user_id] = await self.lookup(platform_user_id, platform)
        return results

    def _default_profile(self, user_id: str) -> dict[str, Any]:
        """Return a default profile for unknown users."""
        return {
            "user_id": user_id,
            "is_new": True,
            "is_vip": False,
            "purchase_count": 0,
            "total_spent": 0.0,
            "tags": ["new_user", "first_visit"],
            "membership_tier": "normal",
            "platform_username": "",
        }

    def parse_tags(self, tags_json: str) -> dict[str, Any]:
        """Parse JSON tags string from gRPC request."""
        try:
            return json.loads(tags_json) if tags_json else {}
        except json.JSONDecodeError:
            logger.warning("profile.parse_tags_error", raw=tags_json)
            return {}
