"""
Service configuration for product-svc.

Extends the shared ServiceConfig with product-specific defaults.
"""

from libs.common.config import ServiceConfig

config = ServiceConfig("product-svc")

# Convenience accessors for well-known config keys.
GRPC_PORT: int = config.get_int("GRPC_PORT", 50051)
HTTP_PORT: int = config.get_int("HTTP_PORT", 8003)
HTTP_HOST: str = config.get("HTTP_HOST", "0.0.0.0")
DB_POOL_SIZE: int = config.get_int("DB_POOL_SIZE", 10)
ENV: str = config.get("ENV", "dev")
