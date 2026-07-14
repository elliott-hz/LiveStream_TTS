"""Tests for the gRPC servicer implementation.

Uses mocked service layers to verify correct proto message construction,
error handling, and edge cases in each RPC method.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import grpc
import pytest

# Ensure both repo root and proto dir are on sys.path for imports
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "libs" / "proto"))

from libs.common.errors import AppError, ErrorCode
from libs.proto.common.v1 import common_pb2
from libs.proto.user.v1 import user_pb2, user_pb2_grpc
from services.platform_svc.src.modules.user.api.grpc_impl import (
    UserServiceServicer,
    _dict_to_user_proto,
    _dict_to_store_proto,
    _error_to_grpc_status,
)

# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════


def _make_mock_context() -> MagicMock:
    """Create a mock gRPC context that records abort calls."""
    ctx = MagicMock(spec=grpc.aio.ServicerContext)
    ctx.abort = AsyncMock()
    return ctx


def _fake_user_dict(**overrides: Any) -> dict[str, Any]:
    """Generate a fake user dict as returned by the service layer."""
    data = {
        "user_id": "u_a1b2c3d4",
        "username": "testuser",
        "email": "test@example.com",
        "phone": "+8613800000000",
        "avatar_url": "https://example.com/avatar.png",
        "role": {
            "role_id": "r_merchant_admin",
            "name": "merchant_admin",
            "permissions": ["product:read", "product:write", "user:read"],
            "description": "Merchant admin role",
        },
        "stores": [
            {
                "store_id": "s_store1",
                "name": "Test Store",
                "logo_url": "https://example.com/logo.png",
                "platforms": {"taobao": True, "douyin": True},
                "status": "active",
            }
        ],
        "current_store_id": "s_store1",
        "status": "active",
        "created_at": 1700000000000,
        "updated_at": 1700000000000,
    }
    data.update(**overrides)
    return data


def _fake_store_dict(**overrides: Any) -> dict[str, Any]:
    """Generate a fake store dict."""
    data = {
        "store_id": "s_store1",
        "name": "Test Store",
        "logo_url": "https://example.com/logo.png",
        "platforms": {
            "taobao": True,
            "douyin": False,
            "jd": False,
            "kuaishou": False,
            "pinduoduo": False,
        },
        "status": "active",
    }
    data.update(**overrides)
    return data


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def mock_auth_service() -> MagicMock:
    mock = MagicMock()
    mock.register = AsyncMock()
    mock.login = AsyncMock()
    mock.refresh_token = AsyncMock()
    mock.logout = AsyncMock()
    return mock


@pytest.fixture
def mock_user_service() -> MagicMock:
    mock = MagicMock()
    mock.get_user = AsyncMock()
    mock.update_user = AsyncMock()
    mock.list_users = AsyncMock()
    mock.check_permission = AsyncMock()
    mock.assign_role = AsyncMock()
    mock.list_stores = AsyncMock()
    mock.switch_store = AsyncMock()
    return mock


@pytest.fixture
def servicer(
    mock_auth_service: MagicMock,
    mock_user_service: MagicMock,
) -> UserServiceServicer:
    return UserServiceServicer(mock_auth_service, mock_user_service)


# ═══════════════════════════════════════════════════════════
# Auth RPC Tests
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestRegisterRPC:
    async def test_success(
        self, servicer: UserServiceServicer, mock_auth_service: MagicMock
    ) -> None:
        mock_auth_service.register.return_value = {
            "access_token": "access123",
            "refresh_token": "refresh123",
            "expires_in": 900,
            "user": _fake_user_dict(),
        }

        request = user_pb2.RegisterRequest(
            username="newuser",
            email="new@example.com",
            password="password123",
            phone="+8613800000000",
            store_name="My Store",
        )
        ctx = _make_mock_context()
        response = await servicer.Register(request, ctx)

        assert response.access_token == "access123"
        assert response.refresh_token == "refresh123"
        assert response.expires_in == 900
        assert response.user.user_id == "u_a1b2c3d4"
        mock_auth_service.register.assert_called_once_with(
            username="newuser",
            email="new@example.com",
            password="password123",
            phone="+8613800000000",
            store_name="My Store",
        )

    async def test_duplicate_error(
        self, servicer: UserServiceServicer, mock_auth_service: MagicMock
    ) -> None:
        mock_auth_service.register.side_effect = AppError(
            ErrorCode.DUPLICATE_RESOURCE, "Username already exists"
        )

        request = user_pb2.RegisterRequest(
            username="existing", email="existing@example.com", password="pw"
        )
        ctx = _make_mock_context()
        await servicer.Register(request, ctx)

        ctx.abort.assert_called_once()


class TestLoginRPC:
    async def test_success(
        self, servicer: UserServiceServicer, mock_auth_service: MagicMock
    ) -> None:
        mock_auth_service.login.return_value = {
            "access_token": "access456",
            "refresh_token": "refresh456",
            "expires_in": 900,
            "user": _fake_user_dict(),
        }

        request = user_pb2.LoginRequest(account="test@example.com", password="pw")
        ctx = _make_mock_context()
        response = await servicer.Login(request, ctx)

        assert response.access_token == "access456"
        mock_auth_service.login.assert_called_once_with(
            account="test@example.com", password="pw"
        )


class TestRefreshTokenRPC:
    async def test_success(
        self, servicer: UserServiceServicer, mock_auth_service: MagicMock
    ) -> None:
        mock_auth_service.refresh_token.return_value = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 900,
            "user": _fake_user_dict(),
        }

        request = user_pb2.RefreshRequest(refresh_token="valid_refresh_token")
        ctx = _make_mock_context()
        response = await servicer.RefreshToken(request, ctx)

        assert response.access_token == "new_access"
        mock_auth_service.refresh_token.assert_called_once_with(
            refresh_token="valid_refresh_token"
        )


class TestLogoutRPC:
    async def test_success(
        self, servicer: UserServiceServicer, mock_auth_service: MagicMock
    ) -> None:
        request = user_pb2.LogoutRequest(user_id="u_a1b2c3d4")
        ctx = _make_mock_context()
        response = await servicer.Logout(request, ctx)

        assert response.code == 0
        assert response.message == ""
        mock_auth_service.logout.assert_called_once_with(user_id="u_a1b2c3d4")


# ═══════════════════════════════════════════════════════════
# User CRUD RPC Tests
# ═══════════════════════════════════════════════════════════


class TestGetUserRPC:
    async def test_success(
        self, servicer: UserServiceServicer, mock_user_service: MagicMock
    ) -> None:
        mock_user_service.get_user.return_value = _fake_user_dict()

        request = user_pb2.GetUserRequest(user_id="u_a1b2c3d4")
        ctx = _make_mock_context()
        response = await servicer.GetUser(request, ctx)

        assert response.user_id == "u_a1b2c3d4"
        assert response.username == "testuser"
        assert response.role.name == "merchant_admin"
        assert len(response.stores) == 1
        assert response.stores[0].name == "Test Store"

    async def test_not_found(
        self, servicer: UserServiceServicer, mock_user_service: MagicMock
    ) -> None:
        mock_user_service.get_user.side_effect = AppError(
            ErrorCode.USER_NOT_FOUND, "User not found: nope"
        )

        request = user_pb2.GetUserRequest(user_id="nope")
        ctx = _make_mock_context()
        await servicer.GetUser(request, ctx)
        ctx.abort.assert_called_once()


class TestUpdateUserRPC:
    async def test_success(
        self, servicer: UserServiceServicer, mock_user_service: MagicMock
    ) -> None:
        updated = _fake_user_dict(email="updated@example.com")
        mock_user_service.update_user.return_value = updated

        request = user_pb2.UpdateUserRequest(
            user_id="u_a1b2c3d4", email="updated@example.com"
        )
        ctx = _make_mock_context()
        response = await servicer.UpdateUser(request, ctx)

        assert response.email == "updated@example.com"


class TestListUsersRPC:
    async def test_success(
        self, servicer: UserServiceServicer, mock_user_service: MagicMock
    ) -> None:
        mock_user_service.list_users.return_value = {
            "users": [_fake_user_dict()],
            "page": 1,
            "page_size": 20,
            "total_count": 1,
            "total_pages": 1,
        }

        request = user_pb2.ListUsersRequest(
            store_id="s_store1",
            pagination=common_pb2.Pagination(page=1, page_size=20),
        )
        ctx = _make_mock_context()
        response = await servicer.ListUsers(request, ctx)

        assert len(response.users) == 1
        assert response.page_info.total_count == 1


# ═══════════════════════════════════════════════════════════
# Permission RPC Tests
# ═══════════════════════════════════════════════════════════


class TestCheckPermissionRPC:
    async def test_allowed(
        self, servicer: UserServiceServicer, mock_user_service: MagicMock
    ) -> None:
        mock_user_service.check_permission.return_value = {
            "allowed": True,
            "reason": "Permission granted",
        }

        request = user_pb2.CheckPermissionRequest(
            user_id="u_a1b2c3d4",
            permission="product:write",
            store_id="s_store1",
        )
        ctx = _make_mock_context()
        response = await servicer.CheckPermission(request, ctx)

        assert response.allowed is True

    async def test_denied(
        self, servicer: UserServiceServicer, mock_user_service: MagicMock
    ) -> None:
        mock_user_service.check_permission.return_value = {
            "allowed": False,
            "reason": "Missing permission",
        }

        request = user_pb2.CheckPermissionRequest(
            user_id="u_a1b2c3d4", permission="billing:admin"
        )
        ctx = _make_mock_context()
        response = await servicer.CheckPermission(request, ctx)

        assert response.allowed is False
        assert response.reason == "Missing permission"


# ═══════════════════════════════════════════════════════════
# Store RPC Tests
# ═══════════════════════════════════════════════════════════


class TestListStoresRPC:
    async def test_success(
        self, servicer: UserServiceServicer, mock_user_service: MagicMock
    ) -> None:
        mock_user_service.list_stores.return_value = [_fake_store_dict()]

        request = user_pb2.ListStoresRequest(user_id="u_a1b2c3d4")
        ctx = _make_mock_context()
        response = await servicer.ListStores(request, ctx)

        assert len(response.stores) == 1
        assert response.stores[0].name == "Test Store"
        assert response.stores[0].platforms.taobao is True


class TestSwitchStoreRPC:
    async def test_success(
        self, servicer: UserServiceServicer, mock_user_service: MagicMock
    ) -> None:
        mock_user_service.switch_store.return_value = _fake_store_dict(
            store_id="s_store2"
        )

        request = user_pb2.SwitchStoreRequest(
            user_id="u_a1b2c3d4", store_id="s_store2"
        )
        ctx = _make_mock_context()
        response = await servicer.SwitchStore(request, ctx)

        assert response.store_id == "s_store2"


# ═══════════════════════════════════════════════════════════
# Proto Conversion Tests
# ═══════════════════════════════════════════════════════════


class TestProtoConversion:
    """Verify domain-to-proto conversion functions."""

    def test_dict_to_user_proto_full(self) -> None:
        user_dict = _fake_user_dict()
        proto = _dict_to_user_proto(user_dict)

        assert proto.user_id == "u_a1b2c3d4"
        assert proto.username == "testuser"
        assert proto.email == "test@example.com"
        assert proto.role.name == "merchant_admin"
        assert proto.role.permissions == ["product:read", "product:write", "user:read"]
        assert proto.status == user_pb2.USER_STATUS_ACTIVE
        assert proto.timestamps.created_at == 1700000000000

    def test_dict_to_user_proto_minimal(self) -> None:
        user_dict = {
            "user_id": "u_minimal",
            "username": "minimal",
            "email": "min@example.com",
            "phone": None,
            "avatar_url": None,
            "role": None,
            "stores": [],
            "current_store_id": None,
            "status": "active",
            "created_at": 0,
            "updated_at": 0,
        }
        proto = _dict_to_user_proto(user_dict)
        assert proto.user_id == "u_minimal"
        assert proto.role.role_id == ""  # empty role proto
        assert len(proto.stores) == 0

    def test_dict_to_store_proto(self) -> None:
        store_dict = _fake_store_dict()
        proto = _dict_to_store_proto(store_dict)

        assert proto.store_id == "s_store1"
        assert proto.name == "Test Store"
        assert proto.platforms.taobao is True
        assert proto.platforms.douyin is False
        assert proto.status == user_pb2.STORE_STATUS_ACTIVE

    def test_error_to_grpc_status_mapping(self) -> None:
        assert _error_to_grpc_status(ErrorCode.NOT_FOUND) == grpc.StatusCode.NOT_FOUND
        assert (
            _error_to_grpc_status(ErrorCode.UNAUTHENTICATED)
            == grpc.StatusCode.UNAUTHENTICATED
        )
        assert (
            _error_to_grpc_status(ErrorCode.INVALID_ARGUMENT)
            == grpc.StatusCode.INVALID_ARGUMENT
        )
        assert (
            _error_to_grpc_status(ErrorCode.DUPLICATE_RESOURCE)
            == grpc.StatusCode.ALREADY_EXISTS
        )
        assert (
            _error_to_grpc_status(ErrorCode.INTERNAL_ERROR)
            == grpc.StatusCode.INTERNAL
        )
        assert (
            _error_to_grpc_status(ErrorCode.INVALID_API_KEY)
            == grpc.StatusCode.UNKNOWN
        )
