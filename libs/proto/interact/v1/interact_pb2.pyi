from common.v1 import common_pb2 as _common_pb2
from tts.v1 import tts_pb2 as _tts_pb2
from nlp.v1 import nlp_pb2 as _nlp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SessionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SESSION_STATUS_UNSPECIFIED: _ClassVar[SessionStatus]
    SESSION_STATUS_RUNNING: _ClassVar[SessionStatus]
    SESSION_STATUS_PAUSED: _ClassVar[SessionStatus]
    SESSION_STATUS_STOPPED: _ClassVar[SessionStatus]

class Channel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CHANNEL_UNSPECIFIED: _ClassVar[Channel]
    CHANNEL_VOICE: _ClassVar[Channel]
    CHANNEL_TEXT: _ClassVar[Channel]
    CHANNEL_BOTH: _ClassVar[Channel]
    CHANNEL_IGNORE: _ClassVar[Channel]

class ModeratorActionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    MODERATOR_ACTION_TYPE_UNSPECIFIED: _ClassVar[ModeratorActionType]
    MODERATOR_ACTION_TYPE_SEND_COMMENT: _ClassVar[ModeratorActionType]
    MODERATOR_ACTION_TYPE_POP_COUPON: _ClassVar[ModeratorActionType]
    MODERATOR_ACTION_TYPE_POP_PRODUCT_CARD: _ClassVar[ModeratorActionType]
    MODERATOR_ACTION_TYPE_HIDE_COMMENT: _ClassVar[ModeratorActionType]
    MODERATOR_ACTION_TYPE_PIN_COMMENT: _ClassVar[ModeratorActionType]
    MODERATOR_ACTION_TYPE_NO_ACTION: _ClassVar[ModeratorActionType]
SESSION_STATUS_UNSPECIFIED: SessionStatus
SESSION_STATUS_RUNNING: SessionStatus
SESSION_STATUS_PAUSED: SessionStatus
SESSION_STATUS_STOPPED: SessionStatus
CHANNEL_UNSPECIFIED: Channel
CHANNEL_VOICE: Channel
CHANNEL_TEXT: Channel
CHANNEL_BOTH: Channel
CHANNEL_IGNORE: Channel
MODERATOR_ACTION_TYPE_UNSPECIFIED: ModeratorActionType
MODERATOR_ACTION_TYPE_SEND_COMMENT: ModeratorActionType
MODERATOR_ACTION_TYPE_POP_COUPON: ModeratorActionType
MODERATOR_ACTION_TYPE_POP_PRODUCT_CARD: ModeratorActionType
MODERATOR_ACTION_TYPE_HIDE_COMMENT: ModeratorActionType
MODERATOR_ACTION_TYPE_PIN_COMMENT: ModeratorActionType
MODERATOR_ACTION_TYPE_NO_ACTION: ModeratorActionType

class Session(_message.Message):
    __slots__ = ("session_id", "live_room_id", "store_id", "config", "status", "stats", "started_at", "ended_at")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    STATS_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    ENDED_AT_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    live_room_id: str
    store_id: str
    config: SessionConfig
    status: SessionStatus
    stats: SessionStats
    started_at: int
    ended_at: int
    def __init__(self, session_id: _Optional[str] = ..., live_room_id: _Optional[str] = ..., store_id: _Optional[str] = ..., config: _Optional[_Union[SessionConfig, _Mapping]] = ..., status: _Optional[_Union[SessionStatus, str]] = ..., stats: _Optional[_Union[SessionStats, _Mapping]] = ..., started_at: _Optional[int] = ..., ended_at: _Optional[int] = ...) -> None: ...

class SessionConfig(_message.Message):
    __slots__ = ("voice_id", "avatar_id", "system_prompt", "banned_words", "enable_moderator", "enable_product_card", "reply_threshold", "moderator_config")
    VOICE_ID_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_PROMPT_FIELD_NUMBER: _ClassVar[int]
    BANNED_WORDS_FIELD_NUMBER: _ClassVar[int]
    ENABLE_MODERATOR_FIELD_NUMBER: _ClassVar[int]
    ENABLE_PRODUCT_CARD_FIELD_NUMBER: _ClassVar[int]
    REPLY_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    MODERATOR_CONFIG_FIELD_NUMBER: _ClassVar[int]
    voice_id: str
    avatar_id: str
    system_prompt: str
    banned_words: _containers.RepeatedScalarFieldContainer[str]
    enable_moderator: bool
    enable_product_card: bool
    reply_threshold: float
    moderator_config: ModeratorConfig
    def __init__(self, voice_id: _Optional[str] = ..., avatar_id: _Optional[str] = ..., system_prompt: _Optional[str] = ..., banned_words: _Optional[_Iterable[str]] = ..., enable_moderator: _Optional[bool] = ..., enable_product_card: _Optional[bool] = ..., reply_threshold: _Optional[float] = ..., moderator_config: _Optional[_Union[ModeratorConfig, _Mapping]] = ...) -> None: ...

class ModeratorConfig(_message.Message):
    __slots__ = ("moderator_account_id", "auto_send_comments", "auto_send_coupons", "auto_send_product_card", "auto_hide_negative", "comment_interval_seconds")
    MODERATOR_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    AUTO_SEND_COMMENTS_FIELD_NUMBER: _ClassVar[int]
    AUTO_SEND_COUPONS_FIELD_NUMBER: _ClassVar[int]
    AUTO_SEND_PRODUCT_CARD_FIELD_NUMBER: _ClassVar[int]
    AUTO_HIDE_NEGATIVE_FIELD_NUMBER: _ClassVar[int]
    COMMENT_INTERVAL_SECONDS_FIELD_NUMBER: _ClassVar[int]
    moderator_account_id: str
    auto_send_comments: bool
    auto_send_coupons: bool
    auto_send_product_card: bool
    auto_hide_negative: bool
    comment_interval_seconds: float
    def __init__(self, moderator_account_id: _Optional[str] = ..., auto_send_comments: _Optional[bool] = ..., auto_send_coupons: _Optional[bool] = ..., auto_send_product_card: _Optional[bool] = ..., auto_hide_negative: _Optional[bool] = ..., comment_interval_seconds: _Optional[float] = ...) -> None: ...

class SessionStats(_message.Message):
    __slots__ = ("total_danmaku", "voice_replies", "text_replies", "moderator_actions", "ignored_messages", "avg_latency_ms")
    TOTAL_DANMAKU_FIELD_NUMBER: _ClassVar[int]
    VOICE_REPLIES_FIELD_NUMBER: _ClassVar[int]
    TEXT_REPLIES_FIELD_NUMBER: _ClassVar[int]
    MODERATOR_ACTIONS_FIELD_NUMBER: _ClassVar[int]
    IGNORED_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    AVG_LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    total_danmaku: int
    voice_replies: int
    text_replies: int
    moderator_actions: int
    ignored_messages: int
    avg_latency_ms: float
    def __init__(self, total_danmaku: _Optional[int] = ..., voice_replies: _Optional[int] = ..., text_replies: _Optional[int] = ..., moderator_actions: _Optional[int] = ..., ignored_messages: _Optional[int] = ..., avg_latency_ms: _Optional[float] = ...) -> None: ...

class StartSessionRequest(_message.Message):
    __slots__ = ("live_room_id", "config")
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    config: SessionConfig
    def __init__(self, live_room_id: _Optional[str] = ..., config: _Optional[_Union[SessionConfig, _Mapping]] = ...) -> None: ...

class StopSessionRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class GetSessionRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class ProcessDanmakuRequest(_message.Message):
    __slots__ = ("session_id", "danmaku_id", "text", "platform_user_id", "platform", "timestamp")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    DANMAKU_ID_FIELD_NUMBER: _ClassVar[int]
    TEXT_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_USER_ID_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    danmaku_id: str
    text: str
    platform_user_id: str
    platform: str
    timestamp: int
    def __init__(self, session_id: _Optional[str] = ..., danmaku_id: _Optional[str] = ..., text: _Optional[str] = ..., platform_user_id: _Optional[str] = ..., platform: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class ProcessDanmakuResponse(_message.Message):
    __slots__ = ("reply_id", "channel", "reply_text", "emotion", "action", "trigger_coupon_ids", "pipeline_latency_ms")
    REPLY_ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    REPLY_TEXT_FIELD_NUMBER: _ClassVar[int]
    EMOTION_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_COUPON_IDS_FIELD_NUMBER: _ClassVar[int]
    PIPELINE_LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    reply_id: str
    channel: Channel
    reply_text: str
    emotion: _tts_pb2.Emotion
    action: str
    trigger_coupon_ids: _containers.RepeatedScalarFieldContainer[str]
    pipeline_latency_ms: int
    def __init__(self, reply_id: _Optional[str] = ..., channel: _Optional[_Union[Channel, str]] = ..., reply_text: _Optional[str] = ..., emotion: _Optional[_Union[_tts_pb2.Emotion, str]] = ..., action: _Optional[str] = ..., trigger_coupon_ids: _Optional[_Iterable[str]] = ..., pipeline_latency_ms: _Optional[int] = ...) -> None: ...

class RouteChannelRequest(_message.Message):
    __slots__ = ("text", "intent", "intent_confidence", "sentiment", "user_profile_tags")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    INTENT_FIELD_NUMBER: _ClassVar[int]
    INTENT_CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    SENTIMENT_FIELD_NUMBER: _ClassVar[int]
    USER_PROFILE_TAGS_FIELD_NUMBER: _ClassVar[int]
    text: str
    intent: _nlp_pb2.IntentCategory
    intent_confidence: float
    sentiment: _nlp_pb2.Sentiment
    user_profile_tags: str
    def __init__(self, text: _Optional[str] = ..., intent: _Optional[_Union[_nlp_pb2.IntentCategory, str]] = ..., intent_confidence: _Optional[float] = ..., sentiment: _Optional[_Union[_nlp_pb2.Sentiment, str]] = ..., user_profile_tags: _Optional[str] = ...) -> None: ...

class RouteChannelResponse(_message.Message):
    __slots__ = ("channel", "reason")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    channel: Channel
    reason: str
    def __init__(self, channel: _Optional[_Union[Channel, str]] = ..., reason: _Optional[str] = ...) -> None: ...

class GetModeratorActionRequest(_message.Message):
    __slots__ = ("session_id", "trigger_event", "context")
    class ContextEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    TRIGGER_EVENT_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    trigger_event: str
    context: _containers.ScalarMap[str, str]
    def __init__(self, session_id: _Optional[str] = ..., trigger_event: _Optional[str] = ..., context: _Optional[_Mapping[str, str]] = ...) -> None: ...

class ModeratorAction(_message.Message):
    __slots__ = ("action_type", "comment_text", "coupon_id", "product_id", "hide_comment_id")
    ACTION_TYPE_FIELD_NUMBER: _ClassVar[int]
    COMMENT_TEXT_FIELD_NUMBER: _ClassVar[int]
    COUPON_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_ID_FIELD_NUMBER: _ClassVar[int]
    HIDE_COMMENT_ID_FIELD_NUMBER: _ClassVar[int]
    action_type: ModeratorActionType
    comment_text: str
    coupon_id: str
    product_id: str
    hide_comment_id: bool
    def __init__(self, action_type: _Optional[_Union[ModeratorActionType, str]] = ..., comment_text: _Optional[str] = ..., coupon_id: _Optional[str] = ..., product_id: _Optional[str] = ..., hide_comment_id: _Optional[bool] = ...) -> None: ...
