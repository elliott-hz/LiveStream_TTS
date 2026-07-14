"""
Profile service — profile lookup, event tracking, segmentation.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import not_found, invalid_arg
from libs.common.logging import get_logger

from models.profile import AudienceProfile, Segment, BehaviorEvent

logger = get_logger(__name__)


class ProfileService:
    """User profile and segmentation business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_profile(self, platform_user_id: str, platform: str) -> dict[str, Any]:
        """Get an audience profile by platform user ID and platform."""
        if not platform_user_id:
            raise invalid_arg("platform_user_id", "must not be empty")
        if not platform:
            raise invalid_arg("platform", "must not be empty")

        stmt = select(AudienceProfile).where(
            AudienceProfile.platform_user_id == platform_user_id,
            AudienceProfile.platform == platform,
        )
        result = await self.db.execute(stmt)
        profile = result.scalars().first()
        if not profile:
            raise not_found("AudienceProfile", f"{platform}:{platform_user_id}")
        return _profile_to_dict(profile)

    async def update_profile(
        self,
        platform_user_id: str,
        platform: str,
        nickname: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update or create an audience profile."""
        if not platform_user_id:
            raise invalid_arg("platform_user_id", "must not be empty")
        if not platform:
            raise invalid_arg("platform", "must not be empty")

        stmt = select(AudienceProfile).where(
            AudienceProfile.platform_user_id == platform_user_id,
            AudienceProfile.platform == platform,
        )
        result = await self.db.execute(stmt)
        profile = result.scalars().first()

        if not profile:
            profile = AudienceProfile(
                platform_user_id=platform_user_id,
                platform=platform,
                nickname=nickname or "",
                tags=tags or [],
                last_seen_at=int(datetime.utcnow().timestamp()),
            )
            self.db.add(profile)
        else:
            if nickname is not None:
                profile.nickname = nickname
            if tags is not None:
                profile.tags = tags
            profile.last_seen_at = int(datetime.utcnow().timestamp())

        await self.db.flush()
        await self.db.refresh(profile)
        logger.info("profile.updated", profile_id=profile.profile_id, platform=platform)
        return _profile_to_dict(profile)

    async def track_event(
        self,
        platform_user_id: str,
        platform: str,
        event_type: str,
        live_room_id: str = "",
        properties: dict[str, str] | None = None,
    ) -> None:
        """Track a user behavior event and update profile counters."""
        if not platform_user_id:
            raise invalid_arg("platform_user_id", "must not be empty")
        if not event_type:
            raise invalid_arg("event_type", "must not be empty")

        # Record the raw event
        event = BehaviorEvent(
            platform_user_id=platform_user_id,
            platform=platform,
            event_type=event_type,
            live_room_id=live_room_id,
            properties_json=properties or {},
        )
        self.db.add(event)

        # Update profile counters
        stmt = select(AudienceProfile).where(
            AudienceProfile.platform_user_id == platform_user_id,
            AudienceProfile.platform == platform,
        )
        result = await self.db.execute(stmt)
        profile = result.scalars().first()

        if profile:
            profile.visit_count += 1
            profile.last_seen_at = int(datetime.utcnow().timestamp())
            if event_type == "purchase":
                profile.purchase_count += 1
                amt = int(properties.get("amount_fen", "0")) if properties else 0
                profile.total_spent_fen += amt
            profile.last_interaction_text = f"{event_type}:{live_room_id}"
            await self.db.flush()

        logger.debug("event.tracked", user_id=platform_user_id, event_type=event_type)
        return None

    async def get_segment(self, segment_id: str) -> Segment:
        """Get a segment definition by ID."""
        stmt = select(Segment).where(Segment.segment_id == segment_id)
        result = await self.db.execute(stmt)
        segment = result.scalars().one_or_none()
        if not segment:
            raise not_found("Segment", segment_id)
        return segment


def _profile_to_dict(p: AudienceProfile) -> dict[str, Any]:
    return {
        "profile_id": p.profile_id,
        "platform_user_id": p.platform_user_id,
        "platform": p.platform,
        "nickname": p.nickname,
        "tags": p.tags or [],
        "visit_count": p.visit_count,
        "purchase_count": p.purchase_count,
        "total_spent_fen": p.total_spent_fen,
        "interest_categories": p.interest_categories or [],
        "last_interaction_text": p.last_interaction_text,
        "last_seen_at": p.last_seen_at,
        "created_at": int(p.created_at.timestamp() * 1000),
    }
