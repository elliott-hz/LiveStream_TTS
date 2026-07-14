"""Script module config — delegates to unified PlatformConfig."""
from ...config import platform_config as config, PlatformConfig
ScriptConfig = PlatformConfig
GRPC_PORT = config.grpc_port
HTTP_PORT = config.http_port
