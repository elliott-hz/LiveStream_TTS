"""Service configuration for knowledge-svc."""

from libs.common.config import ServiceConfig

config = ServiceConfig("knowledge-svc")

GRPC_PORT: int = config.get_int("GRPC_PORT", 50051)
HTTP_PORT: int = config.get_int("HTTP_PORT", 8008)
HTTP_HOST: str = config.get("HTTP_HOST", "0.0.0.0")
DB_POOL_SIZE: int = config.get_int("DB_POOL_SIZE", 10)
ENV: str = config.get("ENV", "dev")
