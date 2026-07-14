"""Live Room CRUD and state machine business logic.

Provides create / get / update / list operations plus lifecycle
transitions (start, pause, resume, stop, emergency stop).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, Domain, ErrorCode, invalid_arg, not_found
from libs.common.logging import get_logger
from libs.kafka import KafkaClient, Topics
from services.live_mgr_svc.src.config import LiveMgrConfig
from services.live_mgr_svc.src.models.live_room import LiveRoom, LiveSession
from services.live_mgr_svc.src.state_machine.live_state import (
    LiveStatus,
    can_emergency_stop,
    is_active,
    live_status_to_proto,
    proto_to_live_status,
    validate_transition,
)

logger = get_logger(__name__)


class LiveRoomService:
    """LiveRoom CRUD and state transition operations."""

    def __init__(
        self,
        db_factory: type[AsyncSession] | Any,
        config: LiveMgrConfig,
        kafka_client: KafkaClient | None = None,
    ) -> None:
        self._db_factory = db_factory
        self._config = config
        self._kafka = kafka_client

    # ── CRUD ──

    async def create_live_room(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new live room (initial status: draft)."""
        async with self._db_factory() as session:
            room = LiveRoom(
                store_id=data["store_id"],
                title=data["title"],
                cover_url=data.get("cover_url"),
                avatar_id=data.get("avatar_id"),
                voice_id=data.get("voice_id"),
                script_id=data.get("script_id"),
                target_platforms=data.get("target_platforms") or [],
                created_by=data.get("created_by"),
                updated_by=data.get("updated_by"),
            )
            session.add(room)
            await session.commit()
            await session.refresh(room)

            logger.info(
                "live_room.created",
                live_room_id=room.live_room_id,
                store_id=room.store_id,
            )
            return _room_to_dict(room)

    async def get_live_room(self, live_room_id: str) -> dict[str, Any]:
        """Retrieve a live room by ID."""
        async with self._db_factory() as session:
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)
            return _room_to_dict(room)

    async def update_live_room(
        self, live_room_id: str, updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Update allowed fields on a live room.

        Only non-ended rooms can be updated.  Allowed fields: title,
        cover_url, avatar_id, voice_id, script_id, target_platforms,
        created_by, updated_by.
        """
        allowed = {
            "title", "cover_url", "avatar_id", "voice_id", "script_id",
            "target_platforms", "created_by", "updated_by",
        }
        sanitised = {k: v for k, v in updates.items() if k in allowed and v is not None}

        if not sanitised:
            raise invalid_arg("updates", "No valid fields to update")

        async with self._db_factory() as session:
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)

            # Lock ended rooms from further updates
            current_status = proto_to_live_status(
                _status_str_to_proto(room.status)
            )
            if current_status == LiveStatus.ENDED:
                raise AppError(
                    ErrorCode.RESOURCE_IN_USE,
                    f"Cannot update live room {live_room_id}: status is ended",
                    domain=Domain.LIVE_MGR,
                )

            for field, value in sanitised.items():
                setattr(room, field, value)

            await session.commit()
            await session.refresh(room)

            logger.info(
                "live_room.updated",
                live_room_id=live_room_id,
                fields=list(sanitised.keys()),
            )
            return _room_to_dict(room)

    async def list_live_rooms(
        self,
        store_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List live rooms with optional filtering and pagination."""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        async with self._db_factory() as session:
            query = select(LiveRoom)
            if store_id:
                query = query.where(LiveRoom.store_id == store_id)
            if status:
                query = query.where(LiveRoom.status == status)

            # Count total
            count_query = select(func.count()).select_from(query.subquery())
            total_count = (await session.execute(count_query)).scalar() or 0

            # Paginate
            offset = (page - 1) * page_size
            query = (
                query.offset(offset)
                .limit(page_size)
                .order_by(LiveRoom.created_at.desc())
            )
            result = await session.execute(query)
            rooms = result.scalars().all()

            return {
                "live_rooms": [_room_to_dict(r) for r in rooms],
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": max(1, (total_count + page_size - 1) // page_size),
            }

    # ── State machine transitions ──

    async def start_live(self, live_room_id: str) -> dict[str, Any]:
        """Transition a room from ready to live.

        Validates that the room is in a ready state with stream_config set,
        creates a LiveSession record, emits a Kafka event, and updates
        the room status to live.
        """
        async with self._db_factory() as session:
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)

            current_status = _str_to_live_status(room.status)
            stream_config_set = room.stream_config is not None
            validate_transition(
                current_status, LiveStatus.LIVE,
                stream_config_set=stream_config_set,
            )

            # Create a new session
            session_record = LiveSession(live_room_id=live_room_id)
            session.add(session_record)

            room.status = LiveStatus.LIVE.value
            await session.commit()
            await session.refresh(room)

            # Emit Kafka event
            await self._emit_live_event(
                "live.started",
                live_room_id=live_room_id,
                session_id=session_record.session_id,
            )

            logger.info(
                "live_room.started",
                live_room_id=live_room_id,
                session_id=session_record.session_id,
            )
            return _room_to_dict(room)

    async def pause_live(self, live_room_id: str) -> dict[str, Any]:
        """Pause a live room (live -> paused)."""
        async with self._db_factory() as session:
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)

            current_status = _str_to_live_status(room.status)
            validate_transition(current_status, LiveStatus.PAUSED)

            room.status = LiveStatus.PAUSED.value
            await session.commit()
            await session.refresh(room)

            await self._emit_live_event(
                "live.paused",
                live_room_id=live_room_id,
            )

            logger.info("live_room.paused", live_room_id=live_room_id)
            return _room_to_dict(room)

    async def resume_live(self, live_room_id: str) -> dict[str, Any]:
        """Resume a paused live room (paused -> live)."""
        async with self._db_factory() as session:
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)

            current_status = _str_to_live_status(room.status)
            validate_transition(current_status, LiveStatus.LIVE,
                                stream_config_set=True)

            room.status = LiveStatus.LIVE.value
            await session.commit()
            await session.refresh(room)

            await self._emit_live_event(
                "live.resumed",
                live_room_id=live_room_id,
            )

            logger.info("live_room.resumed", live_room_id=live_room_id)
            return _room_to_dict(room)

    async def stop_live(self, live_room_id: str) -> dict[str, Any]:
        """Stop a live or paused room (live/paused -> ended).

        Closes the current active session.
        """
        async with self._db_factory() as session:
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)

            current_status = _str_to_live_status(room.status)
            validate_transition(current_status, LiveStatus.ENDED)

            # Close active session
            await self._close_active_session(session, live_room_id)

            room.status = LiveStatus.ENDED.value
            await session.commit()
            await session.refresh(room)

            await self._emit_live_event(
                "live.stopped",
                live_room_id=live_room_id,
            )

            logger.info("live_room.stopped", live_room_id=live_room_id)
            return _room_to_dict(room)

    async def emergency_stop(
        self, live_room_id: str, reason: str = ""
    ) -> dict[str, Any]:
        """Emergency stop for any active room (excluding ended).

        Immediately transitions to ended and closes the session.
        """
        async with self._db_factory() as session:
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)

            current_status = _str_to_live_status(room.status)
            if not can_emergency_stop(current_status):
                raise AppError(
                    ErrorCode.LIVE_ROOM_NOT_IN_STATE,
                    f"Cannot emergency-stop room {live_room_id}: "
                    f"already in {current_status.value} state",
                    domain=Domain.LIVE_MGR,
                )

            # Close active session with emergency reason
            await self._close_active_session(
                session, live_room_id, emergency_reason=reason or "Emergency stop"
            )

            room.status = LiveStatus.ENDED.value
            await session.commit()
            await session.refresh(room)

            await self._emit_live_event(
                "live.emergency_stop",
                live_room_id=live_room_id,
                reason=reason,
            )

            logger.warning(
                "live_room.emergency_stop",
                live_room_id=live_room_id,
                reason=reason,
            )
            return _room_to_dict(room)

    # ── Stream Config ──

    async def get_stream_config(self, live_room_id: str) -> dict[str, Any] | None:
        """Get the stream configuration for a live room."""
        async with self._db_factory() as session:
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)
            return room.stream_config or {}

    async def update_stream_config(
        self, live_room_id: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Update the stream configuration for a live room.

        Once a room is live, stream config cannot be modified.
        """
        async with self._db_factory() as session:
            room = await session.get(LiveRoom, live_room_id)
            if room is None:
                raise not_found("LiveRoom", live_room_id)

            current_status = _str_to_live_status(room.status)
            if current_status in (LiveStatus.LIVE, LiveStatus.PAUSED):
                raise AppError(
                    ErrorCode.RESOURCE_IN_USE,
                    f"Cannot update stream config for room {live_room_id}: "
                    f"status is {room.status}",
                    domain=Domain.LIVE_MGR,
                )

            room.stream_config = config
            await session.commit()
            await session.refresh(room)

            logger.info(
                "live_room.stream_config_updated",
                live_room_id=live_room_id,
            )
            return room.stream_config or {}

    # ── Internal helpers ──

    async def _close_active_session(
        self,
        session: AsyncSession,
        live_room_id: str,
        emergency_reason: str | None = None,
    ) -> None:
        """Find and close the active session for a room."""
        result = await session.execute(
            select(LiveSession)
            .where(
                LiveSession.live_room_id == live_room_id,
                LiveSession.ended_at.is_(None),
            )
            .order_by(LiveSession.started_at.desc())
            .limit(1)
        )
        active_session = result.scalar_one_or_none()
        if active_session:
            active_session.ended_at = datetime.utcnow()
            if emergency_reason:
                active_session.emergency_reason = emergency_reason

    async def _emit_live_event(
        self, event_type: str, **kwargs: Any
    ) -> None:
        """Emit a live event to Kafka (fire-and-forget style)."""
        if not self._kafka:
            logger.debug(
                "live_event.skipped (no kafka client)",
                event_type=event_type,
                **kwargs,
            )
            return
        try:
            payload = json.dumps({"event_type": event_type, **kwargs}).encode()
            await self._kafka.produce(
                Topics.LIVE_EVENTS,
                value=payload,
                key=kwargs.get("live_room_id", "").encode(),
                headers={"event_type": event_type},
            )
        except Exception:
            logger.exception(
                "live_event.emit_failed",
                event_type=event_type,
                **kwargs,
            )


# ── Module-level helpers ──


def _room_to_dict(room: LiveRoom) -> dict[str, Any]:
    """Convert a LiveRoom ORM instance to a plain dict."""
    return {
        "live_room_id": room.live_room_id,
        "store_id": room.store_id,
        "title": room.title,
        "cover_url": room.cover_url or "",
        "status": room.status,
        "avatar_id": room.avatar_id or "",
        "voice_id": room.voice_id or "",
        "script_id": room.script_id or "",
        "stream_config": room.stream_config or {},
        "loop_rule": room.loop_rule or {},
        "target_platforms": room.target_platforms or [],
        "created_by": room.created_by or "",
        "updated_by": room.updated_by or "",
        "created_at": int(room.created_at.timestamp() * 1000) if room.created_at else 0,
        "updated_at": int(room.updated_at.timestamp() * 1000) if room.updated_at else 0,
    }


def _str_to_live_status(status_str: str) -> LiveStatus:
    """Convert a stored status string to a LiveStatus enum."""
    try:
        return LiveStatus(status_str)
    except ValueError:
        return LiveStatus.DRAFT


def _status_str_to_proto(status_str: str) -> int:
    """Convert a stored status string to a proto enum value."""
    status = _str_to_live_status(status_str)
    return live_status_to_proto(status)
