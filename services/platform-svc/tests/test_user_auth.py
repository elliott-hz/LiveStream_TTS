"""Tests for auth and user service business logic.

Covers:
- Full auth flow (register -> login -> refresh -> get_me)
- User CRUD
- Permission checking
- Error cases (duplicate, not found, invalid credentials)
"""

from __future__ import annotations

from typing import Any

import jwt
import pytest

from libs.common.errors import AppError, ErrorCode
from services.platform_svc.src.modules.user.services.auth_service import AuthService
from services.platform_svc.src.modules.user.services.user_service import UserService

pytestmark = pytest.mark.asyncio


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def auth_service(db_factory: Any, test_config: Any) -> AuthService:
    return AuthService(db_factory, test_config)


@pytest.fixture
def user_service(db_factory: Any, test_config: Any) -> UserService:
    return UserService(db_factory, test_config)


# ═══════════════════════════════════════════════════════════
# Auth Flow
# ═══════════════════════════════════════════════════════════


class TestAuthFlow:
    """End-to-end authentication flow."""

    async def test_register_creates_user_and_returns_tokens(
        self, auth_service: AuthService
    ) -> None:
        result = await auth_service.register(
            username="testuser",
            email="test@example.com",
            password="password123",
            phone="+8613800000000",
            store_name="Test Store",
        )

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["expires_in"] == 15 * 60  # 15 minutes in seconds
        assert result["user"]["username"] == "testuser"
        assert result["user"]["email"] == "test@example.com"
        assert result["user"]["phone"] == "+8613800000000"
        assert result["user"]["status"] == "active"

        # Verify JWT payload
        payload = jwt.decode(
            result["access_token"],
            "test-secret-key-012345678901234567",
            algorithms=["HS256"],
        )
        assert payload["user_id"] == result["user"]["user_id"]
        assert payload["username"] == "testuser"
        assert payload["type"] == "access"

    async def test_register_duplicate_raises_error(
        self, auth_service: AuthService
    ) -> None:
        await auth_service.register(
            username="user1",
            email="user1@example.com",
            password="password123",
        )

        with pytest.raises(AppError) as exc_info:
            await auth_service.register(
                username="user1",  # same username
                email="other@example.com",
                password="password123",
            )
        assert exc_info.value.code == ErrorCode.DUPLICATE_RESOURCE

        with pytest.raises(AppError) as exc_info:
            await auth_service.register(
                username="other",
                email="user1@example.com",  # same email
                password="password123",
            )
        assert exc_info.value.code == ErrorCode.DUPLICATE_RESOURCE

    async def test_login_with_email(
        self, auth_service: AuthService
    ) -> None:
        await auth_service.register(
            username="logintest",
            email="login@example.com",
            password="secret123",
            phone="+8613800000001",
        )

        result = await auth_service.login(
            account="login@example.com", password="secret123"
        )
        assert "access_token" in result
        assert result["user"]["email"] == "login@example.com"

    async def test_login_with_phone(
        self, auth_service: AuthService
    ) -> None:
        await auth_service.register(
            username="phonelogin",
            email="phone@example.com",
            password="secret123",
            phone="+8613800000002",
        )

        result = await auth_service.login(
            account="+8613800000002", password="secret123"
        )
        assert "access_token" in result
        assert result["user"]["username"] == "phonelogin"

    async def test_login_wrong_password_raises_error(
        self, auth_service: AuthService
    ) -> None:
        await auth_service.register(
            username="wrongpw",
            email="wrongpw@example.com",
            password="correctpw",
        )

        with pytest.raises(AppError) as exc_info:
            await auth_service.login(
                account="wrongpw@example.com", password="wrongpw"
            )
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT

    async def test_login_nonexistent_user_raises_error(
        self, auth_service: AuthService
    ) -> None:
        with pytest.raises(AppError) as exc_info:
            await auth_service.login(
                account="nobody@example.com", password="any"
            )
        assert exc_info.value.code == ErrorCode.NOT_FOUND

    async def test_refresh_token_issues_new_access(
        self, auth_service: AuthService
    ) -> None:
        result = await auth_service.register(
            username="refreshtest",
            email="refresh@example.com",
            password="password123",
        )

        refresh_result = await auth_service.refresh_token(
            refresh_token=result["refresh_token"]
        )
        assert "access_token" in refresh_result
        assert refresh_result["user"]["user_id"] == result["user"]["user_id"]

        # Verify new token payload
        payload = jwt.decode(
            refresh_result["access_token"],
            "test-secret-key-012345678901234567",
            algorithms=["HS256"],
        )
        assert payload["type"] == "access"
        assert payload["user_id"] == result["user"]["user_id"]

    async def test_refresh_with_expired_token_raises_error(
        self, auth_service: AuthService
    ) -> None:
        # Create a token that's already expired
        import time
        expired_token = jwt.encode(
            {
                "user_id": "fake-id",
                "type": "refresh",
                "exp": int(time.time()) - 3600,  # 1 hour ago
                "iat": int(time.time()) - 7200,
            },
            "test-secret-key-012345678901234567",
            algorithm="HS256",
        )

        with pytest.raises(AppError) as exc_info:
            await auth_service.refresh_token(refresh_token=expired_token)
        assert exc_info.value.code == ErrorCode.TOKEN_EXPIRED

    async def test_logout_does_not_raise(
        self, auth_service: AuthService
    ) -> None:
        result = await auth_service.register(
            username="logouttest",
            email="logout@example.com",
            password="password123",
        )
        # Logout should not raise any error
        await auth_service.logout(user_id=result["user"]["user_id"])


# ═══════════════════════════════════════════════════════════
# User CRUD
# ═══════════════════════════════════════════════════════════


class TestUserCRUD:
    """User CRUD operations."""

    async def test_get_user(
        self, auth_service: AuthService, user_service: UserService
    ) -> None:
        reg = await auth_service.register(
            username="getuser",
            email="getuser@example.com",
            password="password123",
        )
        user_id = reg["user"]["user_id"]

        fetched = await user_service.get_user(user_id=user_id)
        assert fetched["user_id"] == user_id
        assert fetched["username"] == "getuser"
        assert fetched["email"] == "getuser@example.com"

    async def test_get_user_not_found(
        self, user_service: UserService
    ) -> None:
        with pytest.raises(AppError) as exc_info:
            await user_service.get_user(user_id="non-existent-id")
        assert exc_info.value.code == ErrorCode.NOT_FOUND

    async def test_update_user(
        self, auth_service: AuthService, user_service: UserService
    ) -> None:
        reg = await auth_service.register(
            username="updateuser",
            email="updateuser@example.com",
            password="password123",
        )
        user_id = reg["user"]["user_id"]

        updated = await user_service.update_user(
            user_id=user_id,
            updates={"email": "updated@example.com", "phone": "+8613900000000"},
        )
        assert updated["email"] == "updated@example.com"
        assert updated["phone"] == "+8613900000000"
        assert updated["username"] == "updateuser"  # unchanged

    async def test_update_user_no_valid_fields(
        self, user_service: UserService
    ) -> None:
        with pytest.raises(AppError) as exc_info:
            await user_service.update_user(
                user_id="some-id",
                updates={"invalid_field": "value"},
            )
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT

    async def test_list_users_pagination(
        self, auth_service: AuthService, user_service: UserService
    ) -> None:
        # Create multiple users
        for i in range(3):
            await auth_service.register(
                username=f"listuser{i}",
                email=f"listuser{i}@example.com",
                password="password123",
            )

        result = await user_service.list_users(page=1, page_size=2)
        assert len(result["users"]) == 2
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert result["total_count"] == 3
        assert result["total_pages"] == 2


# ═══════════════════════════════════════════════════════════
# Permission Checking
# ═══════════════════════════════════════════════════════════


class TestPermissions:
    """Permission checking logic."""

    async def test_check_permission_granted(
        self, auth_service: AuthService, user_service: UserService
    ) -> None:
        reg = await auth_service.register(
            username="permuser",
            email="permuser@example.com",
            password="password123",
        )
        user_id = reg["user"]["user_id"]

        # merchant_admin has "product:write"
        result = await user_service.check_permission(
            user_id=user_id, permission="product:write"
        )
        assert result["allowed"] is True

    async def test_check_permission_denied(
        self, auth_service: AuthService, user_service: UserService
    ) -> None:
        reg = await auth_service.register(
            username="permuser2",
            email="permuser2@example.com",
            password="password123",
        )
        user_id = reg["user"]["user_id"]

        # merchant_admin does NOT have "billing:admin"
        result = await user_service.check_permission(
            user_id=user_id, permission="billing:admin"
        )
        assert result["allowed"] is False

    async def test_check_permission_user_not_found(
        self, user_service: UserService
    ) -> None:
        result = await user_service.check_permission(
            user_id="nonexistent", permission="product:read"
        )
        assert result["allowed"] is False
        assert "not found" in result["reason"]

    async def test_assign_role(
        self, auth_service: AuthService, user_service: UserService
    ) -> None:
        reg = await auth_service.register(
            username="roleuser",
            email="roleuser@example.com",
            password="password123",
        )
        user_id = reg["user"]["user_id"]
        role_id = reg["user"]["role"]["role_id"]

        # Assign the same role (no-op effectively)
        updated = await user_service.assign_role(
            user_id=user_id, role_id=role_id
        )
        assert updated["user_id"] == user_id
        assert updated["role"]["role_id"] == role_id

    async def test_assign_role_not_found(
        self, user_service: UserService
    ) -> None:
        with pytest.raises(AppError) as exc_info:
            await user_service.assign_role(
                user_id="fake-user", role_id="fake-role"
            )
        assert exc_info.value.code == ErrorCode.NOT_FOUND


# ═══════════════════════════════════════════════════════════
# Token Validation
# ═══════════════════════════════════════════════════════════


class TestTokenValidation:
    """JWT token creation and validation."""

    async def test_decode_valid_token(
        self, auth_service: AuthService
    ) -> None:
        reg = await auth_service.register(
            username="tokentest",
            email="token@example.com",
            password="password123",
        )

        payload = auth_service.decode_token(reg["access_token"])
        assert payload["user_id"] == reg["user"]["user_id"]
        assert payload["type"] == "access"

    async def test_decode_invalid_token_raises_error(
        self, auth_service: AuthService
    ) -> None:
        with pytest.raises(AppError) as exc_info:
            auth_service.decode_token("invalid-token-string")
        assert exc_info.value.code == ErrorCode.INVALID_ARGUMENT
