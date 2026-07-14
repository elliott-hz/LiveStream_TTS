"""Tests for the live room state machine.

Verifies all valid transitions succeed and all invalid transitions
raise ``AppError`` with the correct error code.
"""

from __future__ import annotations

import pytest

from libs.common.errors import AppError, ErrorCode
from services.live_mgr_svc.src.state_machine.live_state import (
    LiveStatus,
    validate_transition,
    is_active,
    can_emergency_stop,
)


class TestValidTransitions:
    """Every valid state transition should pass without error."""

    def test_draft_to_ready(self) -> None:
        validate_transition(LiveStatus.DRAFT, LiveStatus.READY)

    def test_ready_to_live(self) -> None:
        validate_transition(LiveStatus.READY, LiveStatus.LIVE, stream_config_set=True)

    def test_live_to_paused(self) -> None:
        validate_transition(LiveStatus.LIVE, LiveStatus.PAUSED)

    def test_live_to_ended(self) -> None:
        validate_transition(LiveStatus.LIVE, LiveStatus.ENDED)

    def test_live_to_error(self) -> None:
        validate_transition(LiveStatus.LIVE, LiveStatus.ERROR)

    def test_paused_to_live(self) -> None:
        validate_transition(LiveStatus.PAUSED, LiveStatus.LIVE, stream_config_set=True)

    def test_paused_to_ended(self) -> None:
        validate_transition(LiveStatus.PAUSED, LiveStatus.ENDED)

    def test_error_to_draft(self) -> None:
        validate_transition(LiveStatus.ERROR, LiveStatus.DRAFT)

    def test_error_to_ready(self) -> None:
        validate_transition(LiveStatus.ERROR, LiveStatus.READY)


class TestInvalidTransitions:
    """Every invalid state transition should raise AppError."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            (LiveStatus.DRAFT, LiveStatus.LIVE),
            (LiveStatus.DRAFT, LiveStatus.PAUSED),
            (LiveStatus.DRAFT, LiveStatus.ENDED),
            (LiveStatus.DRAFT, LiveStatus.DRAFT),      # self-transition also invalid
            (LiveStatus.READY, LiveStatus.DRAFT),
            (LiveStatus.READY, LiveStatus.PAUSED),
            (LiveStatus.READY, LiveStatus.ENDED),
            (LiveStatus.LIVE, LiveStatus.DRAFT),
            (LiveStatus.LIVE, LiveStatus.READY),
            (LiveStatus.PAUSED, LiveStatus.DRAFT),
            (LiveStatus.PAUSED, LiveStatus.READY),
            (LiveStatus.PAUSED, LiveStatus.ERROR),
            # Terminal: ended → anything
            (LiveStatus.ENDED, LiveStatus.DRAFT),
            (LiveStatus.ENDED, LiveStatus.READY),
            (LiveStatus.ENDED, LiveStatus.LIVE),
            (LiveStatus.ENDED, LiveStatus.PAUSED),
            (LiveStatus.ENDED, LiveStatus.ENDED),
            (LiveStatus.ENDED, LiveStatus.ERROR),
        ],
    )
    def test_invalid_transition(self, from_status: LiveStatus, to_status: LiveStatus) -> None:
        with pytest.raises(AppError) as exc_info:
            validate_transition(from_status, to_status)
        assert exc_info.value.code == ErrorCode.LIVE_ROOM_NOT_IN_STATE

    def test_ready_to_live_without_stream_config(self) -> None:
        """ready -> live should fail if no stream_config is set."""
        with pytest.raises(AppError) as exc_info:
            validate_transition(LiveStatus.READY, LiveStatus.LIVE, stream_config_set=False)
        assert exc_info.value.code == ErrorCode.RESOURCE_IN_USE

    def test_draft_to_live_directly(self) -> None:
        """draft -> live should always be invalid."""
        with pytest.raises(AppError) as exc_info:
            validate_transition(LiveStatus.DRAFT, LiveStatus.LIVE)
        assert exc_info.value.code == ErrorCode.LIVE_ROOM_NOT_IN_STATE


class TestStateHelpers:

    def test_is_active(self) -> None:
        assert is_active(LiveStatus.LIVE) is True
        assert is_active(LiveStatus.PAUSED) is True
        assert is_active(LiveStatus.DRAFT) is False
        assert is_active(LiveStatus.READY) is False
        assert is_active(LiveStatus.ENDED) is False
        assert is_active(LiveStatus.ERROR) is False

    def test_can_emergency_stop(self) -> None:
        assert can_emergency_stop(LiveStatus.LIVE) is True
        assert can_emergency_stop(LiveStatus.PAUSED) is True
        assert can_emergency_stop(LiveStatus.DRAFT) is True
        assert can_emergency_stop(LiveStatus.READY) is True
        assert can_emergency_stop(LiveStatus.ERROR) is True
        assert can_emergency_stop(LiveStatus.ENDED) is False
