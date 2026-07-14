from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Pagination(_message.Message):
    __slots__ = ("page", "page_size")
    PAGE_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    page: int
    page_size: int
    def __init__(self, page: _Optional[int] = ..., page_size: _Optional[int] = ...) -> None: ...

class PageInfo(_message.Message):
    __slots__ = ("page", "page_size", "total_count", "total_pages")
    PAGE_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COUNT_FIELD_NUMBER: _ClassVar[int]
    TOTAL_PAGES_FIELD_NUMBER: _ClassVar[int]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    def __init__(self, page: _Optional[int] = ..., page_size: _Optional[int] = ..., total_count: _Optional[int] = ..., total_pages: _Optional[int] = ...) -> None: ...

class Error(_message.Message):
    __slots__ = ("code", "message", "details")
    class DetailsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    code: int
    message: str
    details: _containers.ScalarMap[str, str]
    def __init__(self, code: _Optional[int] = ..., message: _Optional[str] = ..., details: _Optional[_Mapping[str, str]] = ...) -> None: ...

class Timestamps(_message.Message):
    __slots__ = ("created_at", "updated_at")
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    created_at: int
    updated_at: int
    def __init__(self, created_at: _Optional[int] = ..., updated_at: _Optional[int] = ...) -> None: ...

class AuditInfo(_message.Message):
    __slots__ = ("created_by", "updated_by", "timestamps")
    CREATED_BY_FIELD_NUMBER: _ClassVar[int]
    UPDATED_BY_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMPS_FIELD_NUMBER: _ClassVar[int]
    created_by: str
    updated_by: str
    timestamps: Timestamps
    def __init__(self, created_by: _Optional[str] = ..., updated_by: _Optional[str] = ..., timestamps: _Optional[_Union[Timestamps, _Mapping]] = ...) -> None: ...

class Address(_message.Message):
    __slots__ = ("country", "province", "city", "district", "line1", "line2", "postal_code")
    COUNTRY_FIELD_NUMBER: _ClassVar[int]
    PROVINCE_FIELD_NUMBER: _ClassVar[int]
    CITY_FIELD_NUMBER: _ClassVar[int]
    DISTRICT_FIELD_NUMBER: _ClassVar[int]
    LINE1_FIELD_NUMBER: _ClassVar[int]
    LINE2_FIELD_NUMBER: _ClassVar[int]
    POSTAL_CODE_FIELD_NUMBER: _ClassVar[int]
    country: str
    province: str
    city: str
    district: str
    line1: str
    line2: str
    postal_code: str
    def __init__(self, country: _Optional[str] = ..., province: _Optional[str] = ..., city: _Optional[str] = ..., district: _Optional[str] = ..., line1: _Optional[str] = ..., line2: _Optional[str] = ..., postal_code: _Optional[str] = ...) -> None: ...

class Money(_message.Message):
    __slots__ = ("amount", "currency")
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    amount: int
    currency: str
    def __init__(self, amount: _Optional[int] = ..., currency: _Optional[str] = ...) -> None: ...
