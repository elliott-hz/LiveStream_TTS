"""
Data models mirroring interact.v1 proto definitions.

Used when generated protobuf stubs are unavailable for direct marshalling.
Also provides internal ReplyRecord model for pipeline tracking.
"""

from .interaction import (
    Channel,
    ModeratorActionType,
    Session,
    SessionConfig,
    SessionStats,
    SessionStatus,
    ModeratorConfig,
    ModeratorAction,
    ReplyRecord,
    DanmakuEvent,
    RouteResult,
)

__all__ = [
    "Channel",
    "ModeratorActionType",
    "Session",
    "SessionConfig",
    "SessionStats",
    "SessionStatus",
    "ModeratorConfig",
    "ModeratorAction",
    "ReplyRecord",
    "DanmakuEvent",
    "RouteResult",
]
