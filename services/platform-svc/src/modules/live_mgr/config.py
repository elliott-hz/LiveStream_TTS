"""Live Manager module config — delegates to unified PlatformConfig."""

from ...config import platform_config as config, PlatformConfig

LiveMgrConfig = PlatformConfig

GRPC_PORT = config.grpc_port
HTTP_PORT = config.http_port
HTTP_HOST = config.http_host
DB_POOL_SIZE = config.db_pool_size
ENV = config.env
KAFKA_BOOTSTRAP_SERVERS = config.kafka_bootstrap_servers
