from common.v1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class UserStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    USER_STATUS_UNSPECIFIED: _ClassVar[UserStatus]
    USER_STATUS_ACTIVE: _ClassVar[UserStatus]
    USER_STATUS_SUSPENDED: _ClassVar[UserStatus]
    USER_STATUS_DELETED: _ClassVar[UserStatus]

class StoreStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    STORE_STATUS_UNSPECIFIED: _ClassVar[StoreStatus]
    STORE_STATUS_ACTIVE: _ClassVar[StoreStatus]
    STORE_STATUS_SUSPENDED: _ClassVar[StoreStatus]
USER_STATUS_UNSPECIFIED: UserStatus
USER_STATUS_ACTIVE: UserStatus
USER_STATUS_SUSPENDED: UserStatus
USER_STATUS_DELETED: UserStatus
STORE_STATUS_UNSPECIFIED: StoreStatus
STORE_STATUS_ACTIVE: StoreStatus
STORE_STATUS_SUSPENDED: StoreStatus

class User(_message.Message):
    __slots__ = ("user_id", "username", "email", "phone", "avatar_url", "role", "stores", "current_store_id", "status", "timestamps")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    PHONE_FIELD_NUMBER: _ClassVar[int]
    AVATAR_URL_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    STORES_FIELD_NUMBER: _ClassVar[int]
    CURRENT_STORE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMPS_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    username: str
    email: str
    phone: str
    avatar_url: str
    role: Role
    stores: _containers.RepeatedCompositeFieldContainer[Store]
    current_store_id: str
    status: UserStatus
    timestamps: _common_pb2.Timestamps
    def __init__(self, user_id: _Optional[str] = ..., username: _Optional[str] = ..., email: _Optional[str] = ..., phone: _Optional[str] = ..., avatar_url: _Optional[str] = ..., role: _Optional[_Union[Role, _Mapping]] = ..., stores: _Optional[_Iterable[_Union[Store, _Mapping]]] = ..., current_store_id: _Optional[str] = ..., status: _Optional[_Union[UserStatus, str]] = ..., timestamps: _Optional[_Union[_common_pb2.Timestamps, _Mapping]] = ...) -> None: ...

class Role(_message.Message):
    __slots__ = ("role_id", "name", "permissions", "description")
    ROLE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    PERMISSIONS_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    role_id: str
    name: str
    permissions: _containers.RepeatedScalarFieldContainer[str]
    description: str
    def __init__(self, role_id: _Optional[str] = ..., name: _Optional[str] = ..., permissions: _Optional[_Iterable[str]] = ..., description: _Optional[str] = ...) -> None: ...

class Store(_message.Message):
    __slots__ = ("store_id", "name", "logo_url", "platforms", "status")
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    LOGO_URL_FIELD_NUMBER: _ClassVar[int]
    PLATFORMS_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    store_id: str
    name: str
    logo_url: str
    platforms: StorePlatform
    status: StoreStatus
    def __init__(self, store_id: _Optional[str] = ..., name: _Optional[str] = ..., logo_url: _Optional[str] = ..., platforms: _Optional[_Union[StorePlatform, _Mapping]] = ..., status: _Optional[_Union[StoreStatus, str]] = ...) -> None: ...

class StorePlatform(_message.Message):
    __slots__ = ("taobao", "douyin", "jd", "kuaishou", "pinduoduo")
    TAOBAO_FIELD_NUMBER: _ClassVar[int]
    DOUYIN_FIELD_NUMBER: _ClassVar[int]
    JD_FIELD_NUMBER: _ClassVar[int]
    KUAISHOU_FIELD_NUMBER: _ClassVar[int]
    PINDUODUO_FIELD_NUMBER: _ClassVar[int]
    taobao: bool
    douyin: bool
    jd: bool
    kuaishou: bool
    pinduoduo: bool
    def __init__(self, taobao: _Optional[bool] = ..., douyin: _Optional[bool] = ..., jd: _Optional[bool] = ..., kuaishou: _Optional[bool] = ..., pinduoduo: _Optional[bool] = ...) -> None: ...

class RegisterRequest(_message.Message):
    __slots__ = ("username", "email", "phone", "password", "store_name")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    PHONE_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    STORE_NAME_FIELD_NUMBER: _ClassVar[int]
    username: str
    email: str
    phone: str
    password: str
    store_name: str
    def __init__(self, username: _Optional[str] = ..., email: _Optional[str] = ..., phone: _Optional[str] = ..., password: _Optional[str] = ..., store_name: _Optional[str] = ...) -> None: ...

class LoginRequest(_message.Message):
    __slots__ = ("account", "password")
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    account: str
    password: str
    def __init__(self, account: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class AuthResponse(_message.Message):
    __slots__ = ("access_token", "refresh_token", "expires_in", "user")
    ACCESS_TOKEN_FIELD_NUMBER: _ClassVar[int]
    REFRESH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_IN_FIELD_NUMBER: _ClassVar[int]
    USER_FIELD_NUMBER: _ClassVar[int]
    access_token: str
    refresh_token: str
    expires_in: int
    user: User
    def __init__(self, access_token: _Optional[str] = ..., refresh_token: _Optional[str] = ..., expires_in: _Optional[int] = ..., user: _Optional[_Union[User, _Mapping]] = ...) -> None: ...

class RefreshRequest(_message.Message):
    __slots__ = ("refresh_token",)
    REFRESH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    refresh_token: str
    def __init__(self, refresh_token: _Optional[str] = ...) -> None: ...

class LogoutRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class GetUserRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class UpdateUserRequest(_message.Message):
    __slots__ = ("user_id", "username", "email", "phone", "avatar_url")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    PHONE_FIELD_NUMBER: _ClassVar[int]
    AVATAR_URL_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    username: str
    email: str
    phone: str
    avatar_url: str
    def __init__(self, user_id: _Optional[str] = ..., username: _Optional[str] = ..., email: _Optional[str] = ..., phone: _Optional[str] = ..., avatar_url: _Optional[str] = ...) -> None: ...

class ListUsersRequest(_message.Message):
    __slots__ = ("store_id", "status", "pagination")
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PAGINATION_FIELD_NUMBER: _ClassVar[int]
    store_id: str
    status: UserStatus
    pagination: _common_pb2.Pagination
    def __init__(self, store_id: _Optional[str] = ..., status: _Optional[_Union[UserStatus, str]] = ..., pagination: _Optional[_Union[_common_pb2.Pagination, _Mapping]] = ...) -> None: ...

class ListUsersResponse(_message.Message):
    __slots__ = ("users", "page_info")
    USERS_FIELD_NUMBER: _ClassVar[int]
    PAGE_INFO_FIELD_NUMBER: _ClassVar[int]
    users: _containers.RepeatedCompositeFieldContainer[User]
    page_info: _common_pb2.PageInfo
    def __init__(self, users: _Optional[_Iterable[_Union[User, _Mapping]]] = ..., page_info: _Optional[_Union[_common_pb2.PageInfo, _Mapping]] = ...) -> None: ...

class CheckPermissionRequest(_message.Message):
    __slots__ = ("user_id", "permission", "store_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PERMISSION_FIELD_NUMBER: _ClassVar[int]
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    permission: str
    store_id: str
    def __init__(self, user_id: _Optional[str] = ..., permission: _Optional[str] = ..., store_id: _Optional[str] = ...) -> None: ...

class CheckPermissionResponse(_message.Message):
    __slots__ = ("allowed", "reason")
    ALLOWED_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    allowed: bool
    reason: str
    def __init__(self, allowed: _Optional[bool] = ..., reason: _Optional[str] = ...) -> None: ...

class AssignRoleRequest(_message.Message):
    __slots__ = ("user_id", "role_id", "store_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    role_id: str
    store_id: str
    def __init__(self, user_id: _Optional[str] = ..., role_id: _Optional[str] = ..., store_id: _Optional[str] = ...) -> None: ...

class ListStoresRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class ListStoresResponse(_message.Message):
    __slots__ = ("stores",)
    STORES_FIELD_NUMBER: _ClassVar[int]
    stores: _containers.RepeatedCompositeFieldContainer[Store]
    def __init__(self, stores: _Optional[_Iterable[_Union[Store, _Mapping]]] = ...) -> None: ...

class SwitchStoreRequest(_message.Message):
    __slots__ = ("user_id", "store_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    STORE_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    store_id: str
    def __init__(self, user_id: _Optional[str] = ..., store_id: _Optional[str] = ...) -> None: ...
