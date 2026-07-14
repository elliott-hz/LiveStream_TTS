"""Live Manager service configuration.

Extends ``ServiceConfig`` with live-mgr-svc-specific settings for
database, gRPC, HTTP, and Kafka.
"""

from libs.common.config import ServiceConfig


class LiveMgrConfig(ServiceConfig):
    """Configuration for the live-mgr-svc microservice.

    All settings resolve with 3-tier priority:
    environment variable -> ConfigMap -> default value.
    """

    def __init__(self) -> None:
        super().__init__("live-mgr-svc")

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
        return self.get_int("GRPC_PORT", 50055)

    @property
    def grpc_max_workers(self) -> int:
        return self.get_int("GRPC_MAX_WORKERS", 20)

    # ── HTTP ──

    @property
    def http_port(self) -> int:
        return self.get_int("HTTP_PORT", 8004)

    @property
    def http_host(self) -> str:
        return self.get("HTTP_HOST", "0.0.0.0")

    # ── Kafka ──

    @property
    def kafka_bootstrap_servers(self) -> str:
        return self.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")

    @property
    def kafka_live_events_topic(self) -> str:
        return self.get("KAFKA_LIVE_EVENTS_TOPIC", "live.events")
