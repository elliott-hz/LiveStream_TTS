"""Platform Sync module config — delegates to unified PlatformConfig."""
from ...config import platform_config as config
GRPC_PORT = config.grpc_port
HTTP_PORT = config.http_port
HTTP_HOST = config.http_host
DB_POOL_SIZE = config.db_pool_size
ENV = config.env
TAOBAO_API_BASE = config.taobao_api_base
DOUYIN_API_BASE = config.douyin_api_base
