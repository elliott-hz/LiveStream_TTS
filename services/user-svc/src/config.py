"""User service configuration.

Extends ``ServiceConfig`` with user-svc-specific settings for JWT,
database, gRPC, and HTTP.
"""

from libs.common.config import ServiceConfig


class UserServiceConfig(ServiceConfig):
    """Configuration for the user-svc microservice.

    All settings resolve with 3-tier priority:
    environment variable -> ConfigMap -> default value.
    """

    def __init__(self) -> None:
        super().__init__("user-svc")

    # ── JWT ──

    @property
    def jwt_secret(self) -> str:
        return self.get("JWT_SECRET", "dev-secret-key-change-in-production")

    @property
    def jwt_algorithm(self) -> str:
        return self.get("JWT_ALGORITHM", "HS256")

    @property
    def access_token_expire_minutes(self) -> int:
        return self.get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 15)

    @property
    def refresh_token_expire_days(self) -> int:
        return self.get_int("REFRESH_TOKEN_EXPIRE_DAYS", 7)

    # ── Database ──

    @property
    def db_dsn(self) -> str:
        host = self.get("DB_HOST", "localhost")
        port = self.get("DB_PORT", 5432)
        name = self.get("DB_NAME", "livestream_tts")
        user = self.get("DB_USER", "livestream")
        password = self.get("DB_PASSWORD", "livestream_dev")
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    @property
    def db_pool_size(self) -> int:
        return self.get_int("DB_POOL_SIZE", 10)

    @property
    def db_echo(self) -> bool:
        return self.env == "dev"

    # ── gRPC ──

    @property
    def grpc_port(self) -> int:
        return self.get_int("GRPC_PORT", 50052)

    @property
    def grpc_max_workers(self) -> int:
        return self.get_int("GRPC_MAX_WORKERS", 20)

    # ── HTTP ──

    @property
    def http_port(self) -> int:
        return self.get_int("HTTP_PORT", 8001)

    @property
    def http_host(self) -> str:
        return self.get("HTTP_HOST", "0.0.0.0")
