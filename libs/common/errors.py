"""
Unified error codes for all 16 microservices.

Error code ranges:
  1xxx — Authentication / Authorization
  2xxx — Validation / Bad Request
  3xxx — Resource Not Found
  4xxx — Business Logic errors
  5xxx — Internal / Infrastructure errors
  6xxx — External dependency errors
"""

from enum import IntEnum


class Domain(IntEnum):
    """服务域标识，组合成完整错误码: {Domain}xxx"""
    COMMON = 0
    GATEWAY = 1
    USER = 2
    PRODUCT = 3
    SCRIPT = 4
    LIVE_MGR = 5
    AVATAR = 6
    VOICE = 7
    KNOWLEDGE = 8
    TTS = 9
    NLP = 10
    RENDER = 11
    INTERACT = 12
    PLATFORM_SYNC = 13
    ANALYTICS = 14
    BILLING = 15
    AUDIT = 16
    STREAM = 17
    PROFILE = 18


class ErrorCode(IntEnum):
    """全局错误码 (domain 前缀 + 3位错误号)"""

    # ── 1xxx: Auth ──
    UNAUTHENTICATED = 1001
    PERMISSION_DENIED = 1002
    TOKEN_EXPIRED = 1003
    INVALID_API_KEY = 1004

    # ── 2xxx: Validation ──
    INVALID_ARGUMENT = 2001
    MISSING_REQUIRED_FIELD = 2002
    VALUE_OUT_OF_RANGE = 2003
    INVALID_FORMAT = 2004

    # ── 3xxx: Not Found ──
    NOT_FOUND = 3001
    USER_NOT_FOUND = 3002
    PRODUCT_NOT_FOUND = 3003
    SCRIPT_NOT_FOUND = 3004
    LIVE_ROOM_NOT_FOUND = 3005
    AVATAR_NOT_FOUND = 3006
    VOICE_NOT_FOUND = 3007
    KNOWLEDGE_BASE_NOT_FOUND = 3008

    # ── 4xxx: Business Logic ──
    DUPLICATE_RESOURCE = 4001
    RESOURCE_IN_USE = 4002
    QUOTA_EXCEEDED = 4003
    INSUFFICIENT_BALANCE = 4004
    LIVE_ROOM_NOT_IN_STATE = 4005
    STREAM_ALREADY_RUNNING = 4006
    SCRIPT_NOT_APPROVED = 4007

    # ── 5xxx: Internal ──
    INTERNAL_ERROR = 5001
    DATABASE_ERROR = 5002
    CACHE_ERROR = 5003
    QUEUE_ERROR = 5004

    # ── 6xxx: External ──
    LLM_API_ERROR = 6001
    TTS_SYNTHESIS_FAILED = 6002
    PLATFORM_API_ERROR = 6003
    PAYMENT_GATEWAY_ERROR = 6004
    OBJECT_STORAGE_ERROR = 6005


class AppError(Exception):
    """Base exception for all service errors."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        domain: Domain = Domain.COMMON,
        details: dict | None = None,
    ):
        self.code = code
        self.domain = domain
        self.full_code = domain.value * 1000 + code.value if domain != Domain.COMMON else code.value
        self.message = message
        self.details = details or {}
        super().__init__(message)


# ── Convenience constructors ──

def not_found(resource: str, resource_id: str) -> AppError:
    return AppError(ErrorCode.NOT_FOUND, f"{resource} not found: {resource_id}")

def invalid_arg(field: str, reason: str) -> AppError:
    return AppError(ErrorCode.INVALID_ARGUMENT, f"Invalid {field}: {reason}")

def internal(msg: str = "Internal error") -> AppError:
    return AppError(ErrorCode.INTERNAL_ERROR, msg)
