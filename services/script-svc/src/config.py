"""
Script Service specific configuration defaults.
"""

from libs.common.config import ServiceConfig, ConfigKeys


class ScriptConfig(ServiceConfig):
    """Script Service configuration with script-specific defaults."""

    def __init__(self):
        super().__init__("script-svc")

    @property
    def grpc_port(self) -> int:
        return self.get_int(ConfigKeys.GRPC_PORT, 50054)

    @property
    def http_port(self) -> int:
        return self.get_int(ConfigKeys.HTTP_PORT, 8003)

    @property
    def db_host(self) -> str:
        return self.get(ConfigKeys.DB_HOST, "localhost")

    @property
    def db_port(self) -> int:
        return self.get_int(ConfigKeys.DB_PORT, 5432)

    @property
    def db_name(self) -> str:
        return self.get(ConfigKeys.DB_NAME, "livestream_tts")

    @property
    def db_user(self) -> str:
        return self.get(ConfigKeys.DB_USER, "livestream")

    @property
    def db_password(self) -> str:
        return self.get(ConfigKeys.DB_PASSWORD, "livestream_dev")

    @property
    def db_pool_size(self) -> int:
        return self.get_int(ConfigKeys.DB_POOL_SIZE, 10)

    @property
    def deepseek_api_key(self) -> str | None:
        return self.get(ConfigKeys.DEEPSEEK_API_KEY, None)

    @property
    def deepseek_base_url(self) -> str:
        return self.get(ConfigKeys.DEEPSEEK_BASE_URL, "https://api.deepseek.com/v1")

    @property
    def log_level(self) -> str:
        return self.get("LOG_LEVEL", "INFO")
