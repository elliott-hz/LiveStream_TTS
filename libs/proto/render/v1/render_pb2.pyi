from common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class OverlayType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    OVERLAY_TYPE_UNSPECIFIED: _ClassVar[OverlayType]
    OVERLAY_TYPE_PRODUCT_CARD: _ClassVar[OverlayType]
    OVERLAY_TYPE_PRICE_TAG: _ClassVar[OverlayType]
    OVERLAY_TYPE_COUPON: _ClassVar[OverlayType]
    OVERLAY_TYPE_WATERMARK: _ClassVar[OverlayType]
    OVERLAY_TYPE_LOGO: _ClassVar[OverlayType]
OVERLAY_TYPE_UNSPECIFIED: OverlayType
OVERLAY_TYPE_PRODUCT_CARD: OverlayType
OVERLAY_TYPE_PRICE_TAG: OverlayType
OVERLAY_TYPE_COUPON: OverlayType
OVERLAY_TYPE_WATERMARK: OverlayType
OVERLAY_TYPE_LOGO: OverlayType

class RenderRequest(_message.Message):
    __slots__ = ("request_id", "avatar_id", "audio_data", "sample_rate", "background_id", "overlays", "video_config")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    AUDIO_DATA_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_RATE_FIELD_NUMBER: _ClassVar[int]
    BACKGROUND_ID_FIELD_NUMBER: _ClassVar[int]
    OVERLAYS_FIELD_NUMBER: _ClassVar[int]
    VIDEO_CONFIG_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    avatar_id: str
    audio_data: bytes
    sample_rate: int
    background_id: str
    overlays: _containers.RepeatedCompositeFieldContainer[Overlay]
    video_config: VideoConfig
    def __init__(self, request_id: _Optional[str] = ..., avatar_id: _Optional[str] = ..., audio_data: _Optional[bytes] = ..., sample_rate: _Optional[int] = ..., background_id: _Optional[str] = ..., overlays: _Optional[_Iterable[_Union[Overlay, _Mapping]]] = ..., video_config: _Optional[_Union[VideoConfig, _Mapping]] = ...) -> None: ...

class RenderResponse(_message.Message):
    __slots__ = ("request_id", "video_frame", "frame_number", "is_final")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    VIDEO_FRAME_FIELD_NUMBER: _ClassVar[int]
    FRAME_NUMBER_FIELD_NUMBER: _ClassVar[int]
    IS_FINAL_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    video_frame: bytes
    frame_number: int
    is_final: bool
    def __init__(self, request_id: _Optional[str] = ..., video_frame: _Optional[bytes] = ..., frame_number: _Optional[int] = ..., is_final: _Optional[bool] = ...) -> None: ...

class VideoConfig(_message.Message):
    __slots__ = ("width", "height", "fps", "codec")
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    FPS_FIELD_NUMBER: _ClassVar[int]
    CODEC_FIELD_NUMBER: _ClassVar[int]
    width: int
    height: int
    fps: int
    codec: str
    def __init__(self, width: _Optional[int] = ..., height: _Optional[int] = ..., fps: _Optional[int] = ..., codec: _Optional[str] = ...) -> None: ...

class Overlay(_message.Message):
    __slots__ = ("overlay_id", "type", "content", "position")
    OVERLAY_ID_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    overlay_id: str
    type: OverlayType
    content: str
    position: Position
    def __init__(self, overlay_id: _Optional[str] = ..., type: _Optional[_Union[OverlayType, str]] = ..., content: _Optional[str] = ..., position: _Optional[_Union[Position, _Mapping]] = ...) -> None: ...

class Position(_message.Message):
    __slots__ = ("x", "y", "width", "height", "opacity")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    WIDTH_FIELD_NUMBER: _ClassVar[int]
    HEIGHT_FIELD_NUMBER: _ClassVar[int]
    OPACITY_FIELD_NUMBER: _ClassVar[int]
    x: int
    y: int
    width: int
    height: int
    opacity: float
    def __init__(self, x: _Optional[int] = ..., y: _Optional[int] = ..., width: _Optional[int] = ..., height: _Optional[int] = ..., opacity: _Optional[float] = ...) -> None: ...

class PredictLipSyncRequest(_message.Message):
    __slots__ = ("audio_data", "sample_rate", "avatar_id")
    AUDIO_DATA_FIELD_NUMBER: _ClassVar[int]
    SAMPLE_RATE_FIELD_NUMBER: _ClassVar[int]
    AVATAR_ID_FIELD_NUMBER: _ClassVar[int]
    audio_data: bytes
    sample_rate: int
    avatar_id: str
    def __init__(self, audio_data: _Optional[bytes] = ..., sample_rate: _Optional[int] = ..., avatar_id: _Optional[str] = ...) -> None: ...

class PredictLipSyncResponse(_message.Message):
    __slots__ = ("blendshape_weights", "frame_count")
    BLENDSHAPE_WEIGHTS_FIELD_NUMBER: _ClassVar[int]
    FRAME_COUNT_FIELD_NUMBER: _ClassVar[int]
    blendshape_weights: _containers.RepeatedScalarFieldContainer[float]
    frame_count: int
    def __init__(self, blendshape_weights: _Optional[_Iterable[float]] = ..., frame_count: _Optional[int] = ...) -> None: ...

class GetGPUStatusRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GPUStatus(_message.Message):
    __slots__ = ("device_name", "total_memory_mb", "used_memory_mb", "gpu_utilization_pct", "active_streams")
    DEVICE_NAME_FIELD_NUMBER: _ClassVar[int]
    TOTAL_MEMORY_MB_FIELD_NUMBER: _ClassVar[int]
    USED_MEMORY_MB_FIELD_NUMBER: _ClassVar[int]
    GPU_UTILIZATION_PCT_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_STREAMS_FIELD_NUMBER: _ClassVar[int]
    device_name: str
    total_memory_mb: int
    used_memory_mb: int
    gpu_utilization_pct: int
    active_streams: int
    def __init__(self, device_name: _Optional[str] = ..., total_memory_mb: _Optional[int] = ..., used_memory_mb: _Optional[int] = ..., gpu_utilization_pct: _Optional[int] = ..., active_streams: _Optional[int] = ...) -> None: ...
