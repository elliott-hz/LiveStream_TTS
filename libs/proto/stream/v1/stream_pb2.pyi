from common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StreamStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STREAM_STATUS_UNSPECIFIED: _ClassVar[StreamStatus]
    STREAM_STATUS_CONNECTING: _ClassVar[StreamStatus]
    STREAM_STATUS_STREAMING: _ClassVar[StreamStatus]
    STREAM_STATUS_DISCONNECTED: _ClassVar[StreamStatus]
    STREAM_STATUS_ERROR: _ClassVar[StreamStatus]

class RecordingStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    RECORDING_STATUS_UNSPECIFIED: _ClassVar[RecordingStatus]
    RECORDING_STATUS_RECORDING: _ClassVar[RecordingStatus]
    RECORDING_STATUS_COMPLETED: _ClassVar[RecordingStatus]
    RECORDING_STATUS_FAILED: _ClassVar[RecordingStatus]

class TranscodeStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TRANSCODE_STATUS_UNSPECIFIED: _ClassVar[TranscodeStatus]
    TRANSCODE_STATUS_QUEUED: _ClassVar[TranscodeStatus]
    TRANSCODE_STATUS_PROCESSING: _ClassVar[TranscodeStatus]
    TRANSCODE_STATUS_COMPLETED: _ClassVar[TranscodeStatus]
    TRANSCODE_STATUS_FAILED: _ClassVar[TranscodeStatus]
STREAM_STATUS_UNSPECIFIED: StreamStatus
STREAM_STATUS_CONNECTING: StreamStatus
STREAM_STATUS_STREAMING: StreamStatus
STREAM_STATUS_DISCONNECTED: StreamStatus
STREAM_STATUS_ERROR: StreamStatus
RECORDING_STATUS_UNSPECIFIED: RecordingStatus
RECORDING_STATUS_RECORDING: RecordingStatus
RECORDING_STATUS_COMPLETED: RecordingStatus
RECORDING_STATUS_FAILED: RecordingStatus
TRANSCODE_STATUS_UNSPECIFIED: TranscodeStatus
TRANSCODE_STATUS_QUEUED: TranscodeStatus
TRANSCODE_STATUS_PROCESSING: TranscodeStatus
TRANSCODE_STATUS_COMPLETED: TranscodeStatus
TRANSCODE_STATUS_FAILED: TranscodeStatus

class StreamSession(_message.Message):
    __slots__ = ("session_id", "live_room_id", "status", "rtmp_url", "stream_key", "platforms", "started_at", "bytes_sent")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    RTMP_URL_FIELD_NUMBER: _ClassVar[int]
    STREAM_KEY_FIELD_NUMBER: _ClassVar[int]
    PLATFORMS_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    BYTES_SENT_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    live_room_id: str
    status: StreamStatus
    rtmp_url: str
    stream_key: str
    platforms: _containers.RepeatedCompositeFieldContainer[PlatformStream]
    started_at: int
    bytes_sent: int
    def __init__(self, session_id: _Optional[str] = ..., live_room_id: _Optional[str] = ..., status: _Optional[_Union[StreamStatus, str]] = ..., rtmp_url: _Optional[str] = ..., stream_key: _Optional[str] = ..., platforms: _Optional[_Iterable[_Union[PlatformStream, _Mapping]]] = ..., started_at: _Optional[int] = ..., bytes_sent: _Optional[int] = ...) -> None: ...

class PlatformStream(_message.Message):
    __slots__ = ("platform", "rtmp_url", "status")
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    RTMP_URL_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    platform: str
    rtmp_url: str
    status: StreamStatus
    def __init__(self, platform: _Optional[str] = ..., rtmp_url: _Optional[str] = ..., status: _Optional[_Union[StreamStatus, str]] = ...) -> None: ...

class PushStatus(_message.Message):
    __slots__ = ("session_id", "status", "fps", "bitrate_kbps", "uptime_seconds", "dropped_frames", "health_score")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    FPS_FIELD_NUMBER: _ClassVar[int]
    BITRATE_KBPS_FIELD_NUMBER: _ClassVar[int]
    UPTIME_SECONDS_FIELD_NUMBER: _ClassVar[int]
    DROPPED_FRAMES_FIELD_NUMBER: _ClassVar[int]
    HEALTH_SCORE_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    status: StreamStatus
    fps: int
    bitrate_kbps: int
    uptime_seconds: int
    dropped_frames: int
    health_score: float
    def __init__(self, session_id: _Optional[str] = ..., status: _Optional[_Union[StreamStatus, str]] = ..., fps: _Optional[int] = ..., bitrate_kbps: _Optional[int] = ..., uptime_seconds: _Optional[int] = ..., dropped_frames: _Optional[int] = ..., health_score: _Optional[float] = ...) -> None: ...

class Recording(_message.Message):
    __slots__ = ("recording_id", "live_room_id", "status", "hls_url", "mp4_url", "file_size_bytes", "duration_seconds", "started_at")
    RECORDING_ID_FIELD_NUMBER: _ClassVar[int]
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    HLS_URL_FIELD_NUMBER: _ClassVar[int]
    MP4_URL_FIELD_NUMBER: _ClassVar[int]
    FILE_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    DURATION_SECONDS_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    recording_id: str
    live_room_id: str
    status: RecordingStatus
    hls_url: str
    mp4_url: str
    file_size_bytes: int
    duration_seconds: int
    started_at: int
    def __init__(self, recording_id: _Optional[str] = ..., live_room_id: _Optional[str] = ..., status: _Optional[_Union[RecordingStatus, str]] = ..., hls_url: _Optional[str] = ..., mp4_url: _Optional[str] = ..., file_size_bytes: _Optional[int] = ..., duration_seconds: _Optional[int] = ..., started_at: _Optional[int] = ...) -> None: ...

class TranscodeJob(_message.Message):
    __slots__ = ("job_id", "status", "input_url", "output_url", "progress_percent")
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    INPUT_URL_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_URL_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_PERCENT_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    status: TranscodeStatus
    input_url: str
    output_url: str
    progress_percent: int
    def __init__(self, job_id: _Optional[str] = ..., status: _Optional[_Union[TranscodeStatus, str]] = ..., input_url: _Optional[str] = ..., output_url: _Optional[str] = ..., progress_percent: _Optional[int] = ...) -> None: ...

class StartPushRequest(_message.Message):
    __slots__ = ("live_room_id",)
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    def __init__(self, live_room_id: _Optional[str] = ...) -> None: ...

class StopPushRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class GetPushStatusRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class StartRecordingRequest(_message.Message):
    __slots__ = ("live_room_id", "format")
    LIVE_ROOM_ID_FIELD_NUMBER: _ClassVar[int]
    FORMAT_FIELD_NUMBER: _ClassVar[int]
    live_room_id: str
    format: str
    def __init__(self, live_room_id: _Optional[str] = ..., format: _Optional[str] = ...) -> None: ...

class StopRecordingRequest(_message.Message):
    __slots__ = ("recording_id",)
    RECORDING_ID_FIELD_NUMBER: _ClassVar[int]
    recording_id: str
    def __init__(self, recording_id: _Optional[str] = ...) -> None: ...

class TranscodeRequest(_message.Message):
    __slots__ = ("recording_id", "target")
    class VideoConfig(_message.Message):
        __slots__ = ("width", "height", "fps", "bitrate_kbps", "format")
        WIDTH_FIELD_NUMBER: _ClassVar[int]
        HEIGHT_FIELD_NUMBER: _ClassVar[int]
        FPS_FIELD_NUMBER: _ClassVar[int]
        BITRATE_KBPS_FIELD_NUMBER: _ClassVar[int]
        FORMAT_FIELD_NUMBER: _ClassVar[int]
        width: int
        height: int
        fps: int
        bitrate_kbps: int
        format: str
        def __init__(self, width: _Optional[int] = ..., height: _Optional[int] = ..., fps: _Optional[int] = ..., bitrate_kbps: _Optional[int] = ..., format: _Optional[str] = ...) -> None: ...
    RECORDING_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    recording_id: str
    target: TranscodeRequest.VideoConfig
    def __init__(self, recording_id: _Optional[str] = ..., target: _Optional[_Union[TranscodeRequest.VideoConfig, _Mapping]] = ...) -> None: ...

class GetTranscodeJobRequest(_message.Message):
    __slots__ = ("job_id",)
    JOB_ID_FIELD_NUMBER: _ClassVar[int]
    job_id: str
    def __init__(self, job_id: _Optional[str] = ...) -> None: ...
