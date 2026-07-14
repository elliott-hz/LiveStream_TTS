from common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LiveRoomStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LIVE_ROOM_STATUS_UNSPECIFIED: _ClassVar[LiveRoomStatus]
    LIVE_ROOM_STATUS_DRAFT: _ClassVar[LiveRoomStatus]
    LIVE_ROOM_STATUS_READY: _ClassVar[LiveRoomStatus]
    LIVE_ROOM_STATUS_LIVE: _ClassVar[LiveRoomStatus]
    LIVE_ROOM_STATUS_PAUSED: _ClassVar[LiveRoomStatus]
    LIVE_ROOM_STATUS_ENDED: _ClassVar[LiveRoomStatus]
    LIVE_ROOM_STATUS_ERROR: _ClassVar[LiveRoomStatus]

class VideoProfile(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    VIDEO_PROFILE_UNSPECIFIED: _ClassVar[VideoProfile]
    VIDEO_PROFILE_BASELINE: _ClassVar[VideoProfile]
    VIDEO_PROFILE_MAIN: _ClassVar[VideoProfile]
    VIDEO_PROFILE_HIGH: _ClassVar[VideoProfile]

class LoopMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LOOP_MODE_UNSPECIFIED: _ClassVar[LoopMode]
    LOOP_MODE_ROUND_ROBIN: _ClassVar[LoopMode]
    LOOP_MODE_WEIGHTED: _ClassVar[LoopMode]
    LOOP_MODE_SCHEDULED: _ClassVar[LoopMode]
    LOOP_MODE_SMART: _ClassVar[LoopMode]

class ItemType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ITEM_TYPE_UNSPECIFIED: _ClassVar[ItemType]
    ITEM_TYPE_SCRIPT_SEGMENT: _ClassVar[ItemType]
    ITEM_TYPE_WARMUP: _ClassVar[ItemType]
    ITEM_TYPE_BREAK: _ClassVar[ItemType]
    ITEM_TYPE_INTERACTIVE_REPLY: _ClassVar[ItemType]
LIVE_ROOM_STATUS_UNSPECIFIED: LiveRoomStatus
LIVE_ROOM_STATUS_DRAFT: LiveRoomStatus
LIVE_ROOM_STATUS_READY: LiveRoomStatus
LIVE_ROOM_STATUS_LIVE: LiveRoomStatus
LIVE_ROOM_STATUS_PAUSED: LiveRoomStatus
LIVE_ROOM_STATUS_ENDED: LiveRoomStatus
LIVE_ROOM_STATUS_ERROR: LiveRoomStatus
VIDEO_PROFILE_UNSPECIFIED: VideoProfile
VIDEO_PROFILE_BASELINE: VideoProfile
VIDEO_PROFILE_MAIN: VideoProfile
VIDEO_PROFILE_HIGH: VideoProfile
LOOP_MODE_UNSPECIFIED: LoopMode
LOOP_MODE_ROUND_ROBIN: LoopMode
LOOP_MODE_WEIGHTED: LoopMode
LOOP_MODE_SCHEDULED: LoopMode
LOOP_MODE_SMART: LoopMode
ITEM_TYPE_UNSPECIFIED: ItemType
ITEM_TYPE_SCRIPT_SEGMENT: ItemType
ITEM_TYPE_WARMUP: ItemType
ITEM_TYPE_BREAK: ItemType
ITEM_TYPE_INTERACTIVE_REPLY: ItemType

class LiveRoom(_message.Message):
    __slots__ = ("live_room_id", "store_id", "title", "cover_url", "status", "avatar_id", "voice_id", "script_id", "stream_config", "loop_rule", "target_platforms", "current_session", "audit_info")
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    COVER_URL_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    VOICE_ID_FIELD_NUMBER: _ClassVar[int]
    SCRIPT_ID_FIELD_NUMBER: _ClassVar[int]
    STREAM_CONFIG_FIELD_NUMBER: _ClassVar[int]
    LOOP_RULE_FIELD_NUMBER: _ClassVar[int]
    TARGET_PLATFORMS_FIELD_NUMBER: _ClassVar[int]
    CURRENT_SESSION_FIELD_NUMBER: _ClassVar[int]
    AUDIT_INFO_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    store_id: str
    title: str
    cover_url: str
    status: LiveRoomStatus
    avatar_id: str
    voice_id: str
    script_id: str
    stream_config: StreamConfig
    loop_rule: LoopRule
    target_platforms: _containers.RepeatedScalarFieldContainer[str]
    current_session: LiveSession
    audit_info: _common_pb2.AuditInfo
    def __init__(self, live_room_id: _Optional[str] = ..., store_id: _Optional[str] = ..., title: _Optional[str] = ..., cover_url: _Optional[str] = ..., status: _Optional[_Union[LiveRoomStatus, str]] = ..., avatar_id: _Optional[str] = ..., voice_id: _Optional[str] = ..., script_id: _Optional[str] = ..., stream_config: _Optional[_Union[StreamConfig, _Mapping]] = ..., loop_rule: _Optional[_Union[LoopRule, _Mapping]] = ..., target_platforms: _Optional[_Iterable[str]] = ..., current_session: _Optional[_Union[LiveSession, _Mapping]] = ..., audit_info: _Optional[_Union[_common_pb2.AuditInfo, _Mapping]] = ...) -> None: ...

class LiveSession(_message.Message):
    __slots__ = ("session_id", "started_at", "ended_at", "viewer_peak", "total_interactions")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    ENDED_AT_FIELD_NUMBER: _ClassVar[int]
    VIEWER_PEAK_FIELD_NUMBER: _ClassVar[int]
    TOTAL_INTERACTIONS_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    started_at: int
    ended_at: int
    viewer_peak: int
    total_interactions: int
    def __init__(self, session_id: _Optional[str] = ..., started_at: _Optional[int] = ..., ended_at: _Optional[int] = ..., viewer_peak: _Optional[int] = ..., total_interactions: _Optional[int] = ...) -> None: ...

class StreamConfig(_message.Message):
    __slots__ = ("rtmp_url", "stream_key", "video_profile", "width", "height", "fps", "video_bitrate_kbps", "audio_bitrate_kbps")
    RTMP_URL_FIELD_NUMBER: _ClassVar[int]
    STREAM_KEY_FIELD_NUMBER: _ClassVar[int]
    VIDEO_PROFILE_FIELD_NUMBER: _ClassVar[int]
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    FPS_FIELD_NUMBER: _ClassVar[int]
    VIDEO_BITRATE_KBPS_FIELD_NUMBER: _ClassVar[int]
    AUDIO_BITRATE_KBPS_FIELD_NUMBER: _ClassVar[int]
    rtmp_url: str
    stream_key: str
    video_profile: VideoProfile
    width: int
    height: int
    fps: int
    video_bitrate_kbps: int
    audio_bitrate_kbps: int
    def __init__(self, rtmp_url: _Optional[str] = ..., stream_key: _Optional[str] = ..., video_profile: _Optional[_Union[VideoProfile, str]] = ..., width: _Optional[int] = ..., height: _Optional[int] = ..., fps: _Optional[int] = ..., video_bitrate_kbps: _Optional[int] = ..., audio_bitrate_kbps: _Optional[int] = ...) -> None: ...

class LoopRule(_message.Message):
    __slots__ = ("mode", "weights", "schedule_json")
    class WeightsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    MODE_FIELD_NUMBER: _ClassVar[int]
    WEIGHTS_FIELD_NUMBER: _ClassVar[int]
    SCHEDULE_JSON_FIELD_NUMBER: _ClassVar[int]
    mode: LoopMode
    weights: _containers.ScalarMap[str, int]
    schedule_json: str
    def __init__(self, mode: _Optional[_Union[LoopMode, str]] = ..., weights: _Optional[_Mapping[str, int]] = ..., schedule_json: _Optional[str] = ...) -> None: ...

class Playlist(_message.Message):
    __slots__ = ("playlist_id", "live_room_id", "items", "loop_rule", "created_at", "updated_at")
    PLAYLIST_ID_FIELD_NUMBER: _ClassVar[int]
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    LOOP_RULE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    playlist_id: str
    live_room_id: str
    items: _containers.RepeatedCompositeFieldContainer[PlaylistItem]
    loop_rule: LoopRule
    created_at: int
    updated_at: int
    def __init__(self, playlist_id: _Optional[str] = ..., live_room_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[PlaylistItem, _Mapping]]] = ..., loop_rule: _Optional[_Union[LoopRule, _Mapping]] = ..., created_at: _Optional[int] = ..., updated_at: _Optional[int] = ...) -> None: ...

class PlaylistItem(_message.Message):
    __slots__ = ("item_id", "order", "script_section_id", "product_id", "duration_ms", "type")
    ITEM_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_FIELD_NUMBER: _ClassVar[int]
    SCRIPT_SECTION_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    DURATION_MS_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    item_id: str
    order: int
    script_section_id: str
    product_id: str
    duration_ms: int
    type: ItemType
    def __init__(self, item_id: _Optional[str] = ..., order: _Optional[int] = ..., script_section_id: _Optional[str] = ..., product_id: _Optional[str] = ..., duration_ms: _Optional[int] = ..., type: _Optional[_Union[ItemType, str]] = ...) -> None: ...

class CreateLiveRoomRequest(_message.Message):
    __slots__ = ("store_id", "title", "avatar_id", "voice_id", "target_platforms")
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    VOICE_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_PLATFORMS_FIELD_NUMBER: _ClassVar[int]
    store_id: str
    title: str
    avatar_id: str
    voice_id: str
    target_platforms: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, store_id: _Optional[str] = ..., title: _Optional[str] = ..., avatar_id: _Optional[str] = ..., voice_id: _Optional[str] = ..., target_platforms: _Optional[_Iterable[str]] = ...) -> None: ...

class GetLiveRoomRequest(_message.Message):
    __slots__ = ("live_room_id",)
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    def __init__(self, live_room_id: _Optional[str] = ...) -> None: ...

class UpdateLiveRoomRequest(_message.Message):
    __slots__ = ("live_room_id", "title", "cover_url", "avatar_id", "voice_id")
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    COVER_URL_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    VOICE_ID_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    title: str
    cover_url: str
    avatar_id: str
    voice_id: str
    def __init__(self, live_room_id: _Optional[str] = ..., title: _Optional[str] = ..., cover_url: _Optional[str] = ..., avatar_id: _Optional[str] = ..., voice_id: _Optional[str] = ...) -> None: ...

class ListLiveRoomsRequest(_message.Message):
    __slots__ = ("store_id", "status", "pagination")
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    store_id: str
    status: LiveRoomStatus
    pagination: _common_pb2.Pagination
    def __init__(self, store_id: _Optional[str] = ..., status: _Optional[_Union[LiveRoomStatus, str]] = ..., pagination: _Optional[_Union[_common_pb2.Pagination, _Mapping]] = ...) -> None: ...

class ListLiveRoomsResponse(_message.Message):
    __slots__ = ("live_rooms", "page_info")
    LIVE_ROOMS_FIELD_NUMBER: _ClassVar[int]
    PAGE_INFO_FIELD_NUMBER: _ClassVar[int]
    live_rooms: _containers.RepeatedCompositeFieldContainer[LiveRoom]
    page_info: _common_pb2.PageInfo
    def __init__(self, live_rooms: _Optional[_Iterable[_Union[LiveRoom, _Mapping]]] = ..., page_info: _Optional[_Union[_common_pb2.PageInfo, _Mapping]] = ...) -> None: ...

class StartLiveRequest(_message.Message):
    __slots__ = ("live_room_id",)
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    def __init__(self, live_room_id: _Optional[str] = ...) -> None: ...

class PauseLiveRequest(_message.Message):
    __slots__ = ("live_room_id",)
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    def __init__(self, live_room_id: _Optional[str] = ...) -> None: ...

class ResumeLiveRequest(_message.Message):
    __slots__ = ("live_room_id",)
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    def __init__(self, live_room_id: _Optional[str] = ...) -> None: ...

class StopLiveRequest(_message.Message):
    __slots__ = ("live_room_id",)
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    def __init__(self, live_room_id: _Optional[str] = ...) -> None: ...

class EmergencyStopRequest(_message.Message):
    __slots__ = ("live_room_id", "reason")
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    reason: str
    def __init__(self, live_room_id: _Optional[str] = ..., reason: _Optional[str] = ...) -> None: ...

class CreatePlaylistRequest(_message.Message):
    __slots__ = ("live_room_id", "items", "loop_rule")
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    LOOP_RULE_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    items: _containers.RepeatedCompositeFieldContainer[PlaylistItem]
    loop_rule: LoopRule
    def __init__(self, live_room_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[PlaylistItem, _Mapping]]] = ..., loop_rule: _Optional[_Union[LoopRule, _Mapping]] = ...) -> None: ...

class UpdatePlaylistRequest(_message.Message):
    __slots__ = ("playlist_id", "items", "loop_rule")
    PLAYLIST_ID_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    LOOP_RULE_FIELD_NUMBER: _ClassVar[int]
    playlist_id: str
    items: _containers.RepeatedCompositeFieldContainer[PlaylistItem]
    loop_rule: LoopRule
    def __init__(self, playlist_id: _Optional[str] = ..., items: _Optional[_Iterable[_Union[PlaylistItem, _Mapping]]] = ..., loop_rule: _Optional[_Union[LoopRule, _Mapping]] = ...) -> None: ...

class GetPlaylistRequest(_message.Message):
    __slots__ = ("playlist_id",)
    PLAYLIST_ID_FIELD_NUMBER: _ClassVar[int]
    playlist_id: str
    def __init__(self, playlist_id: _Optional[str] = ...) -> None: ...

class GetStreamConfigRequest(_message.Message):
    __slots__ = ("live_room_id",)
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    def __init__(self, live_room_id: _Optional[str] = ...) -> None: ...

class UpdateStreamConfigRequest(_message.Message):
    __slots__ = ("live_room_id", "stream_config")
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    STREAM_CONFIG_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    stream_config: StreamConfig
    def __init__(self, live_room_id: _Optional[str] = ..., stream_config: _Optional[_Union[StreamConfig, _Mapping]] = ...) -> None: ...
