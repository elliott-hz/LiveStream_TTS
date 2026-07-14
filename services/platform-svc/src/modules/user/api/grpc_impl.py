"""gRPC service implementation for the UserService proto.

Implements all 12 RPCs defined in ``user/v1/user.proto``.
"""

from __future__ import annotations

from typing import Any

import grpc
from google.protobuf.json_format import MessageToDict

from libs.common.errors import AppError, Domain, ErrorCode
from libs.common.logging import get_logger
from .services.auth_service import AuthService
from .services.user_service import UserService

# Generated proto stubs (checked in under libs/proto/)
from libs.proto.user.v1 import user_pb2, user_pb2_grpc
from libs.proto.common.v1 import common_pb2

logger = get_logger(__name__)

# Map domain-level status strings to proto enum values
_STATUS_TO_PROTO = {
    "active": user_pb2.USER_STATUS_ACTIVE,
    "suspended": user_pb2.USER_STATUS_SUSPENDED,
    "deleted": user_pb2.USER_STATUS_DELETED,
}

_STORE_STATUS_TO_PROTO = {
    "active": user_pb2.STORE_STATUS_ACTIVE,
    "suspended": user_pb2.STORE_STATUS_SUSPENDED,
}


class UserServiceServicer(user_pb2_grpc.UserServiceServicer):
    """gRPC servicer for the UserService.

    Wraps :class:`AuthService` and :class:`UserService` to translate
    between protobuf messages and domain logic.
    """

    def __init__(
        self, auth_service: AuthService, user_service: UserService
    ) -> None:
        self._auth = auth_service
        self._user = user_service

    # ── Auth RPCs ──

    async def Register(
        self,
        request: user_pb2.RegisterRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.AuthResponse:
        try:
            result = await self._auth.register(
                username=request.username,
                email=request.email,
                password=request.password,
                phone=request.phone or None,
                store_name=request.store_name or None,
            )
            return self._dict_to_auth_response(result)
        except AppError as e:
            await _abort_with_error(context, e)

    async def Login(
        self,
        request: user_pb2.LoginRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.AuthResponse:
        try:
            result = await self._auth.login(
                account=request.account, password=request.password
            )
            return self._dict_to_auth_response(result)
        except AppError as e:
            await _abort_with_error(context, e)

    async def RefreshToken(
        self,
        request: user_pb2.RefreshRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.AuthResponse:
        try:
            result = await self._auth.refresh_token(
                refresh_token=request.refresh_token
            )
            return self._dict_to_auth_response(result)
        except AppError as e:
            await _abort_with_error(context, e)

    async def Logout(
        self,
        request: user_pb2.LogoutRequest,
        context: grpc.aio.ServicerContext,
    ) -> common_pb2.Error:
        try:
            await self._auth.logout(user_id=request.user_id)
            # Return empty error (null) on success
            return common_pb2.Error(code=0, message="")
        except AppError as e:
            await _abort_with_error(context, e)

    # ── User CRUD RPCs ──

    async def GetUser(
        self,
        request: user_pb2.GetUserRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.User:
        try:
            user_dict = await self._user.get_user(user_id=request.user_id)
            return _dict_to_user_proto(user_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def UpdateUser(
        self,
        request: user_pb2.UpdateUserRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.User:
        try:
            updates: dict[str, Any] = {}
            if request.HasField("username"):
                updates["username"] = request.username
            if request.HasField("email"):
                updates["email"] = request.email
            if request.HasField("phone"):
                updates["phone"] = request.phone
            if request.HasField("avatar_url"):
                updates["avatar_url"] = request.avatar_url

            user_dict = await self._user.update_user(
                user_id=request.user_id, updates=updates
            )
            return _dict_to_user_proto(user_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    async def ListUsers(
        self,
        request: user_pb2.ListUsersRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.ListUsersResponse:
        try:
            status_filter = None
            if request.HasField("status"):
                status_filter = _proto_status_to_str(request.status)

            page = 1
            page_size = 20
            if request.HasField("pagination"):
                page = request.pagination.page or 1
                page_size = request.pagination.page_size or 20

            result = await self._user.list_users(
                store_id=request.store_id or None,
                status=status_filter,
                page=page,
                page_size=page_size,
            )

            return user_pb2.ListUsersResponse(
                users=[_dict_to_user_proto(u) for u in result["users"]],
                page_info=common_pb2.PageInfo(
                    page=result["page"],
                    page_size=result["page_size"],
                    total_count=result["total_count"],
                    total_pages=result["total_pages"],
                ),
            )
        except AppError as e:
            await _abort_with_error(context, e)

    # ── Permission RPCs ──

    async def CheckPermission(
        self,
        request: user_pb2.CheckPermissionRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.CheckPermissionResponse:
        try:
            store_id = request.store_id if request.HasField("store_id") else None
            result = await self._user.check_permission(
                user_id=request.user_id,
                permission=request.permission,
                store_id=store_id,
            )
            return user_pb2.CheckPermissionResponse(
                allowed=result["allowed"], reason=result["reason"]
            )
        except AppError as e:
            await _abort_with_error(context, e)

    async def AssignRole(
        self,
        request: user_pb2.AssignRoleRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.User:
        try:
            user_dict = await self._user.assign_role(
                user_id=request.user_id,
                role_id=request.role_id,
                store_id=request.store_id or None,
            )
            return _dict_to_user_proto(user_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    # ── Store RPCs ──

    async def ListStores(
        self,
        request: user_pb2.ListStoresRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.ListStoresResponse:
        try:
            stores = await self._user.list_stores(user_id=request.user_id)
            return user_pb2.ListStoresResponse(
                stores=[_dict_to_store_proto(s) for s in stores]
            )
        except AppError as e:
            await _abort_with_error(context, e)

    async def SwitchStore(
        self,
        request: user_pb2.SwitchStoreRequest,
        context: grpc.aio.ServicerContext,
    ) -> user_pb2.Store:
        try:
            store_dict = await self._user.switch_store(
                user_id=request.user_id, store_id=request.store_id
            )
            return _dict_to_store_proto(store_dict)
        except AppError as e:
            await _abort_with_error(context, e)

    # ── Helpers ──

    def _dict_to_auth_response(self, data: dict[str, Any]) -> user_pb2.AuthResponse:
        return user_pb2.AuthResponse(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
            user=_dict_to_user_proto(data["user"]),
        )


# ── Module-level helpers ──


async def _abort_with_error(context: grpc.aio.ServicerContext, error: AppError) -> None:
    """Abort a gRPC call with the given ``AppError`` mapped to a gRPC status."""
    logger.warning(
        "grpc.abort",
        method=context._rpc_method if hasattr(context, "_rpc_method") else "unknown",
        code=error.full_code,
        message=error.message,
    )
    status_code = _error_to_grpc_status(error.code)
    await context.abort(
        code=status_code,
        details=f"[{error.full_code}] {error.message}",
    )


def _error_to_grpc_status(code: ErrorCode) -> grpc.StatusCode:
    """Map an ``ErrorCode`` to a gRPC ``StatusCode``."""
    mapping: dict[ErrorCode, grpc.StatusCode] = {
        ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
        ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
        ErrorCode.TOKEN_EXPIRED: grpc.StatusCode.UNAUTHENTICATED,
        ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
        ErrorCode.MISSING_REQUIRED_FIELD: grpc.StatusCode.INVALID_ARGUMENT,
        ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        ErrorCode.USER_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
        ErrorCode.DUPLICATE_RESOURCE: grpc.StatusCode.ALREADY_EXISTS,
        ErrorCode.INTERNAL_ERROR: grpc.StatusCode.INTERNAL,
        ErrorCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
    }
    return mapping.get(code, grpc.StatusCode.UNKNOWN)


def _dict_to_user_proto(user: dict[str, Any]) -> user_pb2.User:
    """Convert a user dict from the service layer to a proto ``User`` message."""
    role = user.get("role")
    role_proto = None
    if role:
        role_proto = user_pb2.Role(
            role_id=role.get("role_id", ""),
            name=role.get("name", ""),
            permissions=role.get("permissions", []),
            description=role.get("description", ""),
        )

    stores_proto = []
    for store in user.get("stores", []):
        stores_proto.append(_dict_to_store_proto(store))

    status_str = user.get("status", "active")
    status_enum = _STATUS_TO_PROTO.get(status_str, user_pb2.USER_STATUS_UNSPECIFIED)

    return user_pb2.User(
        user_id=user.get("user_id", ""),
        username=user.get("username", ""),
        email=user.get("email", ""),
        phone=user.get("phone", ""),
        avatar_url=user.get("avatar_url", ""),
        role=role_proto,
        stores=stores_proto,
        current_store_id=user.get("current_store_id", ""),
        status=status_enum,
        timestamps=common_pb2.Timestamps(
            created_at=user.get("created_at", 0),
            updated_at=user.get("updated_at", 0),
        ),
    )


def _dict_to_store_proto(store: dict[str, Any]) -> user_pb2.Store:
    """Convert a store dict to a proto ``Store`` message."""
    platforms = store.get("platforms", {})
    store_status = store.get("status", "active")
    status_enum = _STORE_STATUS_TO_PROTO.get(
        store_status, user_pb2.STORE_STATUS_UNSPECIFIED
    )

    return user_pb2.Store(
        store_id=store.get("store_id", ""),
        name=store.get("name", ""),
        logo_url=store.get("logo_url", ""),
        platforms=user_pb2.StorePlatform(
            taobao=platforms.get("taobao", False),
            douyin=platforms.get("douyin", False),
            jd=platforms.get("jd", False),
            kuaishou=platforms.get("kuaishou", False),
            pinduoduo=platforms.get("pinduoduo", False),
        ),
        status=status_enum,
    )


def _proto_status_to_str(status: int) -> str:
    """Map proto ``UserStatus`` enum value to domain string."""
    mapping = {
        user_pb2.USER_STATUS_ACTIVE: "active",
        user_pb2.USER_STATUS_SUSPENDED: "suspended",
        user_pb2.USER_STATUS_DELETED: "deleted",
    }
    return mapping.get(status, "active")
