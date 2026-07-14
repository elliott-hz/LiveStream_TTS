"""Live room state machine.

Defines the valid state transitions for a LiveRoom lifecycle:

    draft ──► ready ──► live ──► ended
                          │  ▲
                          ▼  │
                        paused

Invalid transitions raise AppError with LIVE_ROOM_NOT_IN_STATE.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from libs.common.errors import AppError, Domain, ErrorCode


class LiveStatus(str, Enum):
    """Domain-level live room status values matching the proto enum."""

    DRAFT = "draft"
    READY = "ready"
    LIVE = "live"
    PAUSED = "paused"
    ENDED = "ended"
    ERROR = "error"


# ── Transition map ──
# Maps a source status to the set of allowed target statuses.

_VALID_TRANSITIONS: Final[dict[LiveStatus, set[LiveStatus]]] = {
    LiveStatus.DRAFT: {LiveStatus.READY},
    LiveStatus.READY: {LiveStatus.LIVE},
    LiveStatus.LIVE: {LiveStatus.PAUSED, LiveStatus.ENDED, LiveStatus.ERROR},
    LiveStatus.PAUSED: {LiveStatus.LIVE, LiveStatus.ENDED},
    LiveStatus.ENDED: set(),
    LiveStatus.ERROR: {LiveStatus.DRAFT, LiveStatus.READY},
}

# Statuses that are considered "active" (i.e., streaming or can stream).
_ACTIVE_STATUSES: Final[set[LiveStatus]] = {
    LiveStatus.LIVE,
    LiveStatus.PAUSED,
}

# ── Proto mapping ──

_LIVE_ROOM_STATUS_PROTO_MAP: Final[dict[LiveStatus, int]] = {
    LiveStatus.DRAFT: 1,   # LIVE_ROOM_STATUS_DRAFT
    LiveStatus.READY: 2,   # LIVE_ROOM_STATUS_READY
    LiveStatus.LIVE: 3,    # LIVE_ROOM_STATUS_LIVE
    LiveStatus.PAUSED: 4,  # LIVE_ROOM_STATUS_PAUSED
    LiveStatus.ENDED: 5,   # LIVE_ROOM_STATUS_ENDED
    LiveStatus.ERROR: 6,   # LIVE_ROOM_STATUS_ERROR
}

_PROTO_TO_LIVE_STATUS: Final[dict[int, LiveStatus]] = {
    v: k for k, v in _LIVE_ROOM_STATUS_PROTO_MAP.items()
}


# ── Public API ──


def validate_transition(
    from_status: LiveStatus,
    to_status: LiveStatus,
    *,
    stream_config_set: bool = False,
) -> None:
    """Validate a state transition.

    Args:
        from_status: Current live room status.
        to_status: Desired target status.
        stream_config_set: Whether a stream config has been configured
                           (required for ready -> live).

    Raises:
        AppError: If the transition is invalid.
    """
    allowed = _VALID_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise AppError(
            ErrorCode.LIVE_ROOM_NOT_IN_STATE,
            f"Cannot transition from {from_status.value} to {to_status.value}. "
            f"Allowed transitions from {from_status.value}: "
            f"{[s.value for s in allowed] if allowed else 'none (terminal state)'}",
            domain=Domain.LIVE_MGR,
        )

    # Special guard: ready -> live requires a stream config
    if from_status == LiveStatus.READY and to_status == LiveStatus.LIVE:
        if not stream_config_set:
            raise AppError(
                ErrorCode.RESOURCE_IN_USE,
                "Cannot start live: stream configuration not set. "
                "Configure RTMP URL and stream key before going live.",
                domain=Domain.LIVE_MGR,
            )


def is_active(status: LiveStatus) -> bool:
    """Return True if the status represents an active/streaming room."""
    return status in _ACTIVE_STATUSES


def can_emergency_stop(status: LiveStatus) -> bool:
    """Return True if the room can be emergency-stopped (any non-ended active state)."""
    return status not in (LiveStatus.ENDED,)


def proto_to_live_status(proto_value: int) -> LiveStatus:
    """Convert a proto enum integer to a LiveStatus."""
    return _PROTO_TO_LIVE_STATUS.get(proto_value, LiveStatus.DRAFT)


def live_status_to_proto(status: LiveStatus) -> int:
    """Convert a LiveStatus to a proto enum integer."""
    return _LIVE_ROOM_STATUS_PROTO_MAP.get(status, 0)
