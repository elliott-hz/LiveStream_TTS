"""
Configuration for analytics-svc.
"""

from libs.common.config import ServiceConfig, ConfigKeys

config = ServiceConfig("analytics-svc")

GRPC_PORT: int = config.get_int("GRPC_PORT", 50064)
HTTP_PORT: int = config.get_int("HTTP_PORT", 8013)
HTTP_HOST: str = config.get("HTTP_HOST", "0.0.0.0")
DB_POOL_SIZE: int = config.get_int("DB_POOL_SIZE", 10)
ENV: str = config.get("ENV", "dev")
