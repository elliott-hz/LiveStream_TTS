"""Tests for the Playlist service.

Uses the shared ``async_db`` fixture (in-memory SQLite) to test
playlist creation, update, validation, and loop rule handling.
"""

from __future__ import annotations

from typing import Any

import pytest

from libs.common.errors import AppError, ErrorCode
from services.live_mgr_svc.src.config import LiveMgrConfig
from services.live_mgr_svc.src.models.live_room import LiveRoom, Playlist
from services.live_mgr_svc.src.services.playlist_service import (
    PlaylistService,
    _validate_playlist_items,
    _calculate_total_duration,
)


@pytest.fixture
def playlist_service(db_factory) -> PlaylistService:
    """Create a PlaylistService with an in-memory database."""
    config = LiveMgrConfig()
    return PlaylistService(db_factory, config)


@pytest.fixture
async def sample_room(async_db) -> dict[str, Any]:
    """Create a sample LiveRoom for playlist tests."""
    from datetime import datetime

    import uuid

    room = LiveRoom(
        live_room_id=str(uuid.uuid4()),
        store_id="store_test_001",
        title="测试直播房间",
        status="draft",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    async_db.add(room)
    await async_db.commit()
    return {
        "live_room_id": room.live_room_id,
        "store_id": room.store_id,
        "title": room.title,
    }


class TestPlaylistCreate:

    async def test_create_playlist_success(
        self, playlist_service: PlaylistService, sample_room: dict[str, Any]
    ) -> None:
        data = {
            "live_room_id": sample_room["live_room_id"],
            "items": [
                {
                    "item_id": "item_001",
                    "order": 1,
                    "script_section_id": "sec_001",
                    "product_id": "prod_001",
                    "duration_ms": 30000,
                    "type": "script_segment",
                },
                {
                    "item_id": "item_002",
                    "order": 2,
                    "script_section_id": "sec_002",
                    "product_id": "prod_002",
                    "duration_ms": 45000,
                    "type": "script_segment",
                },
            ],
            "loop_rule": {"mode": "round_robin"},
        }

        result = await playlist_service.create_playlist(data)

        assert result["playlist_id"] is not None
        assert result["live_room_id"] == sample_room["live_room_id"]
        assert len(result["items"]) == 2
        assert result["items"][0]["order"] == 1
        assert result["items"][1]["order"] == 2
        assert result["items"][0]["duration_ms"] == 30000
        assert result["loop_rule"]["mode"] == "round_robin"

    async def test_create_playlist_invalid_items_empty(
        self, playlist_service: PlaylistService, sample_room: dict[str, Any]
    ) -> None:
        data = {
            "live_room_id": sample_room["live_room_id"],
            "items": [],
        }

        with pytest.raises(AppError) as exc_info:
            await playlist_service.create_playlist(data)
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT

    async def test_create_playlist_missing_duration(
        self, playlist_service: PlaylistService, sample_room: dict[str, Any]
    ) -> None:
        data = {
            "live_room_id": sample_room["live_room_id"],
            "items": [
                {
                    "item_id": "item_001",
                    "order": 1,
                    "product_id": "prod_001",
                    # missing duration_ms
                    "type": "script_segment",
                },
            ],
        }

        with pytest.raises(AppError) as exc_info:
            await playlist_service.create_playlist(data)
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT

    async def test_create_playlist_duplicate_order(
        self, playlist_service: PlaylistService, sample_room: dict[str, Any]
    ) -> None:
        data = {
            "live_room_id": sample_room["live_room_id"],
            "items": [
                {
                    "item_id": "item_001",
                    "order": 1,
                    "duration_ms": 10000,
                    "type": "script_segment",
                },
                {
                    "item_id": "item_002",
                    "order": 1,  # duplicate
                    "duration_ms": 20000,
                    "type": "script_segment",
                },
            ],
        }

        with pytest.raises(AppError) as exc_info:
            await playlist_service.create_playlist(data)
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT
        assert "Duplicate" in str(exc_info.value.message)

    async def test_create_playlist_duplicate_for_room(
        self, playlist_service: PlaylistService, sample_room: dict[str, Any]
    ) -> None:
        """A room can only have one playlist."""
        data = {
            "live_room_id": sample_room["live_room_id"],
            "items": [
                {
                    "item_id": "item_001",
                    "order": 1,
                    "duration_ms": 10000,
                    "type": "script_segment",
                },
            ],
        }

        await playlist_service.create_playlist(data)

        with pytest.raises(AppError) as exc_info:
            await playlist_service.create_playlist(data)
        assert exc_info.value.code == ErrorCode.DUPLICATE_RESOURCE


class TestPlaylistUpdate:

    async def test_update_playlist_replace_items(
        self, playlist_service: PlaylistService, sample_room: dict[str, Any]
    ) -> None:
        # First create
        data = {
            "live_room_id": sample_room["live_room_id"],
            "items": [
                {
                    "item_id": "item_001",
                    "order": 1,
                    "duration_ms": 10000,
                    "type": "script_segment",
                },
            ],
        }
        created = await playlist_service.create_playlist(data)

        # Now update with new items
        update_data = {
            "items": [
                {
                    "item_id": "item_002",
                    "order": 1,
                    "duration_ms": 20000,
                    "type": "warmup",
                },
                {
                    "item_id": "item_003",
                    "order": 2,
                    "duration_ms": 30000,
                    "type": "script_segment",
                },
            ],
            "loop_rule": {"mode": "weighted", "weights": {"prod_001": 3, "prod_002": 1}},
        }
        result = await playlist_service.update_playlist(
            created["playlist_id"], update_data
        )

        assert result["playlist_id"] == created["playlist_id"]
        assert len(result["items"]) == 2
        assert result["items"][0]["item_id"] == "item_002"
        assert result["items"][0]["type"] == "warmup"
        assert result["loop_rule"]["mode"] == "weighted"

    async def test_update_playlist_not_found(
        self, playlist_service: PlaylistService
    ) -> None:
        with pytest.raises(AppError) as exc_info:
            await playlist_service.update_playlist(
                "nonexistent-playlist",
                {"items": [{"item_id": "i1", "order": 1, "duration_ms": 1000}]},
            )
        assert exc_info.value.code == ErrorCode.NOT_FOUND


class TestPlaylistValidation:

    def test_validate_items_empty(self) -> None:
        with pytest.raises(AppError) as exc_info:
            _validate_playlist_items([])
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT

    def test_validate_items_missing_order(self) -> None:
        items = [{"item_id": "i1", "duration_ms": 1000}]
        with pytest.raises(AppError) as exc_info:
            _validate_playlist_items(items)
        assert "order" in str(exc_info.value.message).lower()

    def test_validate_items_negative_duration(self) -> None:
        items = [{"item_id": "i1", "order": 1, "duration_ms": -1}]
        with pytest.raises(AppError) as exc_info:
            _validate_playlist_items(items)
        assert "duration" in str(exc_info.value.message).lower()

    def test_calculate_total_duration(self) -> None:
        items = [
            {"item_id": "i1", "order": 1, "duration_ms": 10000},
            {"item_id": "i2", "order": 2, "duration_ms": 20000},
            {"item_id": "i3", "order": 3, "duration_ms": 30000},
        ]
        assert _calculate_total_duration(items) == 60000

    def test_calculate_total_duration_empty(self) -> None:
        assert _calculate_total_duration([]) == 0
