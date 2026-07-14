"""
Configuration for platform-sync-svc.
"""

from libs.common.config import ServiceConfig, ConfigKeys

config = ServiceConfig("platform-sync-svc")

GRPC_PORT: int = config.get_int("GRPC_PORT", 50051)
HTTP_PORT: int = config.get_int("HTTP_PORT", 8013)
HTTP_HOST: str = config.get("HTTP_HOST", "0.0.0.0")
DB_POOL_SIZE: int = config.get_int("DB_POOL_SIZE", 10)
ENV: str = config.get("ENV", "dev")

# Platform adapter endpoints (mock)
TAOBAO_API_BASE: str = config.get("TAOBAO_API_BASE", "https://api.taobao.com/mock")
DOUYIN_API_BASE: str = config.get("DOUYIN_API_BASE", "https://open.douyin.com/mock")
