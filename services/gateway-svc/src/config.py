"""
Gateway service configuration.

Extends the base ServiceConfig with gateway-specific settings:
JWT, rate limiting, downstream service endpoints, CORS.
"""

from libs.common.config import ServiceConfig


class GatewayConfig(ServiceConfig):
    """Configuration for the gateway service."""

    def __init__(self) -> None:
        super().__init__("gateway-svc")

    # ── Server ──
    @property
    def http_host(self) -> str:
        return self.get("HTTP_HOST", default="0.0.0.0")

    @property
    def http_port(self) -> int:
        return self.get_int("HTTP_PORT", 8080)

    @property
    def log_level(self) -> str:
        return self.get("LOG_LEVEL", default="INFO")

    @property
    def log_json(self) -> bool:
        return self.get_bool("LOG_JSON", default=True)

    # ── JWT ──
    @property
    def jwt_secret(self) -> str:
        return self.get("JWT_SECRET", default="dev-secret-change-in-production")

    @property
    def jwt_algorithm(self) -> str:
        return self.get("JWT_ALGORITHM", default="HS256")

    @property
    def jwt_access_expire_minutes(self) -> int:
        return self.get_int("JWT_ACCESS_EXPIRE_MINUTES", default=30)

    @property
    def jwt_refresh_expire_days(self) -> int:
        return self.get_int("JWT_REFRESH_EXPIRE_DAYS", default=7)

    # ── Rate Limiting ──
    @property
    def rate_limit_admin_rps(self) -> int:
        """Admin API requests per second."""
        return self.get_int("RATE_LIMIT_ADMIN_RPS", default=100)

    @property
    def rate_limit_tts_rps(self) -> int:
        """TTS API requests per second."""
        return self.get_int("RATE_LIMIT_TTS_RPS", default=50)

    @property
    def rate_limit_default_rps(self) -> int:
        """Default requests per second."""
        return self.get_int("RATE_LIMIT_DEFAULT_RPS", default=20)

    @property
    def rate_limit_ws_per_ip(self) -> int:
        """WebSocket connections per IP."""
        return self.get_int("RATE_LIMIT_WS_PER_IP", default=5)

    @property
    def rate_limit_burst_multiplier(self) -> int:
        """Burst multiplier over base RPS."""
        return self.get_int("RATE_LIMIT_BURST_MULTIPLIER", default=2)

    # ── Downstream Service Endpoints ──
    @property
    def user_svc_grpc_host(self) -> str:
        return self.get("USER_SVC_GRPC_HOST", default="user-svc")

    @property
    def user_svc_grpc_port(self) -> int:
        return self.get_int("USER_SVC_GRPC_PORT", default=50052)

    @property
    def product_svc_grpc_host(self) -> str:
        return self.get("PRODUCT_SVC_GRPC_HOST", default="product-svc")

    @property
    def product_svc_grpc_port(self) -> int:
        return self.get_int("PRODUCT_SVC_GRPC_PORT", default=50053)

    @property
    def script_svc_grpc_host(self) -> str:
        return self.get("SCRIPT_SVC_GRPC_HOST", default="script-svc")

    @property
    def script_svc_grpc_port(self) -> int:
        return self.get_int("SCRIPT_SVC_GRPC_PORT", default=50054)

    @property
    def tts_svc_grpc_host(self) -> str:
        return self.get("TTS_SVC_GRPC_HOST", default="tts-svc")

    @property
    def tts_svc_grpc_port(self) -> int:
        return self.get_int("TTS_SVC_GRPC_PORT", default=50059)

    # ── CORS ──
    @property
    def cors_origins(self) -> list[str]:
        return self.get_list("CORS_ORIGINS", default=["*"])

    @property
    def cors_allow_credentials(self) -> bool:
        return self.get_bool("CORS_ALLOW_CREDENTIALS", default=True)


# Singleton
config = GatewayConfig()
