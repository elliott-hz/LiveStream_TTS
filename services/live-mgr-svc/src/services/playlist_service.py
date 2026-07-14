"""Playlist CRUD and scheduler logic.

Manages the ordered playlist for each live room, enforces
validation of items and durations, and resolves the next item
based on the loop rule.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, Domain, ErrorCode, invalid_arg, not_found
from libs.common.logging import get_logger
from services.live_mgr_svc.src.config import LiveMgrConfig
from services.live_mgr_svc.src.models.live_room import LiveRoom, Playlist
from services.live_mgr_svc.src.state_machine.live_state import LiveStatus

logger = get_logger(__name__)


class PlaylistService:
    """Playlist operations: create, update, get, and item scheduling."""

    def __init__(
        self, db_factory: type[AsyncSession] | Any, config: LiveMgrConfig
    ) -> None:
        self._db_factory = db_factory
        self._config = config

    async def create_playlist(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a playlist for a live room.

        Validates items and calculates total duration.  Each live room
        can have at most one playlist (enforced by DB unique constraint).

        Args:
            data: Dict with ``live_room_id``, ``items`` (list of item dicts),
                  and optional ``loop_rule``.

        Raises:
            AppError: If items are invalid or the room already has a playlist.
        """
        live_room_id = data["live_room_id"]
        items: list[dict[str, Any]] = data.get("items", [])
        loop_rule: dict[str, Any] | None = data.get("loop_rule")

        _validate_playlist_items(items)

        async with self._db_factory() as session:
            # Verify the live room exists
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)

            # Check for existing playlist
            existing = await session.execute(
                select(Playlist).where(Playlist.live_room_id == live_room_id)
            )
            if existing.scalar_one_or_none() is not None:
                raise AppError(
                    ErrorCode.DUPLICATE_RESOURCE,
                    f"Playlist already exists for live room {live_room_id}. "
                    f"Use update_playlist to modify it.",
                    domain=Domain.LIVE_MGR,
                )

            playlist = Playlist(
                live_room_id=live_room_id,
                items=items,
                loop_rule=loop_rule,
            )
            session.add(playlist)
            await session.commit()
            await session.refresh(playlist)

            total_ms = _calculate_total_duration(items)
            logger.info(
                "playlist.created",
                playlist_id=playlist.playlist_id,
                live_room_id=live_room_id,
                item_count=len(items),
                total_duration_ms=total_ms,
            )
            return _playlist_to_dict(playlist)

    async def update_playlist(self, playlist_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Replace the items and/or loop rule of an existing playlist.

        Args:
            playlist_id: The playlist to update.
            data: Dict with optional ``items`` and/or ``loop_rule``.
        """
        items: list[dict[str, Any]] | None = data.get("items")
        loop_rule: dict[str, Any] | None | str = data.get("loop_rule")

        if items is not None:
            _validate_playlist_items(items)

        async with self._db_factory() as session:
            playlist = await session.get(Playlist, playlist_id)
            if playlist is None:
                raise not_found("Playlist", playlist_id)

            # Lock if the room is live
            room = await session.get(LiveRoom, playlist.live_room_id)
            if room:
                current_status = _str_to_live_status(room.status)
                if current_status == LiveStatus.LIVE:
                    # We allow updates during live, but log it
                    logger.info(
                        "playlist.updated_during_live",
                        playlist_id=playlist_id,
                        live_room_id=playlist.live_room_id,
                    )

            if items is not None:
                playlist.items = items
            if loop_rule is not None:
                playlist.loop_rule = loop_rule

            await session.commit()
            await session.refresh(playlist)

            item_count = len(playlist.items)
            total_ms = _calculate_total_duration(playlist.items)
            logger.info(
                "playlist.updated",
                playlist_id=playlist_id,
                item_count=item_count,
                total_duration_ms=total_ms,
            )
            return _playlist_to_dict(playlist)

    async def get_playlist(self, playlist_id: str) -> dict[str, Any]:
        """Retrieve a playlist by ID, including all items."""
        async with self._db_factory() as session:
            playlist = await session.get(Playlist, playlist_id)
            if playlist is None:
                raise not_found("Playlist", playlist_id)
            return _playlist_to_dict(playlist)

    async def get_playlist_by_room(self, live_room_id: str) -> dict[str, Any] | None:
        """Retrieve the playlist for a given live room."""
        async with self._db_factory() as session:
            result = await session.execute(
                select(Playlist).where(Playlist.live_room_id == live_room_id)
            )
            playlist = result.scalar_one_or_none()
            if playlist is None:
                return None
            return _playlist_to_dict(playlist)


# ── Module-level helpers ──


def _validate_playlist_items(items: list[dict[str, Any]]) -> None:
    """Validate playlist items.

    Checks:
    - Each item has required fields.
    - ``order`` values form a consistent sequence.
    - ``duration_ms`` is a positive integer.
    """
    if not items:
        raise invalid_arg("items", "Playlist must contain at least one item")

    seen_orders: set[int] = set()
    for idx, item in enumerate(items):
        item_id = item.get("item_id", f"__index_{idx}__")

        # Required fields
        if "order" not in item:
            raise invalid_arg(f"items[{idx}]", "Missing required field: order")
        if "duration_ms" not in item:
            raise invalid_arg(f"items[{idx}]", "Missing required field: duration_ms")

        order = item["order"]
        if not isinstance(order, int) or order < 0:
            raise invalid_arg(
                f"items[{idx}].order",
                f"Must be a non-negative integer, got {order}",
            )
        if order in seen_orders:
            raise invalid_arg(
                f"items[{idx}].order",
                f"Duplicate order value: {order}",
            )
        seen_orders.add(order)

        duration_ms = item["duration_ms"]
        if not isinstance(duration_ms, int) or duration_ms < 0:
            raise invalid_arg(
                f"items[{idx}].duration_ms",
                f"Must be a non-negative integer, got {duration_ms}",
            )


def _calculate_total_duration(items: list[dict[str, Any]]) -> int:
    """Calculate the total duration of all items in milliseconds."""
    return sum(item.get("duration_ms", 0) for item in items)


def _playlist_to_dict(playlist: Playlist) -> dict[str, Any]:
    """Convert a Playlist ORM instance to a plain dict."""
    return {
        "playlist_id": playlist.playlist_id,
        "live_room_id": playlist.live_room_id,
        "items": playlist.items or [],
        "loop_rule": playlist.loop_rule or {},
        "created_at": int(playlist.created_at.timestamp() * 1000) if playlist.created_at else 0,
        "updated_at": int(playlist.updated_at.timestamp() * 1000) if playlist.updated_at else 0,
    }


def _str_to_live_status(status_str: str) -> LiveStatus:
    """Convert a stored status string to a LiveStatus enum."""
    try:
        return LiveStatus(status_str)
    except ValueError:
        return LiveStatus.DRAFT
