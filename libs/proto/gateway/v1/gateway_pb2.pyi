from common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HealthRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HealthResponse(_message.Message):
    __slots__ = ("status", "version", "uptime_seconds", "services")
    class ServicesEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: ServiceHealth
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[ServiceHealth, _Mapping]] = ...) -> None: ...
    STATUS_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    UPTIME_SECONDS_FIELD_NUMBER: _ClassVar[int]
    SERVICES_FIELD_NUMBER: _ClassVar[int]
    status: str
    version: str
    uptime_seconds: int
    services: _containers.MessageMap[str, ServiceHealth]
    def __init__(self, status: _Optional[str] = ..., version: _Optional[str] = ..., uptime_seconds: _Optional[int] = ..., services: _Optional[_Mapping[str, ServiceHealth]] = ...) -> None: ...

class ServiceHealth(_message.Message):
    __slots__ = ("status", "latency_ms", "error")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    status: str
    latency_ms: int
    error: str
    def __init__(self, status: _Optional[str] = ..., latency_ms: _Optional[int] = ..., error: _Optional[str] = ...) -> None: ...

class GetServiceEndpointRequest(_message.Message):
    __slots__ = ("service_name", "version")
    SERVICE_NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    service_name: str
    version: str
    def __init__(self, service_name: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class GetServiceEndpointResponse(_message.Message):
    __slots__ = ("host", "port", "healthy")
    HOST_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    HEALTHY_FIELD_NUMBER: _ClassVar[int]
    host: str
    port: int
    healthy: bool
    def __init__(self, host: _Optional[str] = ..., port: _Optional[int] = ..., healthy: _Optional[bool] = ...) -> None: ...
