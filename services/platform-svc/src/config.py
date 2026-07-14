"""
Unified configuration for platform-svc.

Merges all 11 management service configs into one PlatformConfig class.
Single gRPC port + single HTTP port, shared DB/Kafka/Redis.
"""

from libs.common.config import ServiceConfig, ConfigKeys


class PlatformConfig(ServiceConfig):
    """Unified config for all management modules."""

    def __init__(self) -> None:
        super().__init__("platform-svc")

    # ── gRPC ──

    @property
    def grpc_port(self) -> int:
        return self.get_int(ConfigKeys.GRPC_PORT, 50050)

    # ── HTTP ──

    @property
    def http_port(self) -> int:
        return self.get_int(ConfigKeys.HTTP_PORT, 8081)

    @property
    def http_host(self) -> str:
        return self.get(ConfigKeys.HTTP_HOST, "0.0.0.0")

    # ── Database ──

    @property
    def db_pool_size(self) -> int:
        return self.get_int(ConfigKeys.DB_POOL_SIZE, 10)

    @property
    def db_echo(self) -> bool:
        return self.env == "dev"

    # ── JWT (user module) ──

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

    # ── LLM / DeepSeek (script module) ──

    @property
    def deepseek_api_key(self) -> str | None:
        return self.get(ConfigKeys.DEEPSEEK_API_KEY, None)

    @property
    def deepseek_base_url(self) -> str:
        return self.get(ConfigKeys.DEEPSEEK_BASE_URL, "https://api.deepseek.com/v1")

    # ── Platform adapters (platform_sync module) ──

    @property
    def taobao_api_base(self) -> str:
        return self.get("TAOBAO_API_BASE", "https://api.taobao.com/mock")

    @property
    def douyin_api_base(self) -> str:
        return self.get("DOUYIN_API_BASE", "https://open.douyin.com/mock")

    # ── Kafka (live_mgr module) ──

    @property
    def kafka_bootstrap_servers(self) -> str:
        return self.get(ConfigKeys.KAFKA_BOOTSTRAP_SERVERS, "localhost:9093")


# Singleton instance
platform_config = PlatformConfig()
