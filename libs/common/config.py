"""
Configuration loader with 3-tier priority:
  1. Environment variables (highest)
  2. K8s ConfigMap / mounted files
  3. Default values (lowest)
"""

import json
import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore


class ServiceConfig:
    """Base config for all microservices.

    Usage:
        config = ServiceConfig("gateway-svc")
        db_host = config.get("DB_HOST", default="localhost")
    """

    def __init__(self, service_name: str, env: str | None = None):
        self.service_name = service_name
        self.env = env or os.getenv("ENV", "dev")
        self._overrides: dict[str, Any] = {}
        self._load_configmap()

    def _load_configmap(self) -> None:
        """Load from K8s ConfigMap mount (if available)."""
        config_path = Path(f"/etc/config/{self.service_name}/config.yaml")
        if config_path.exists():
            with open(config_path) as f:
                self._overrides = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Resolve config value with priority: env > configmap > default."""
        env_key = f"{self.service_name.upper().replace('-', '_')}_{key}"
        env_val = os.getenv(env_key)
        if env_val is not None:
            return self._cast(env_val, default)
        if key in self._overrides:
            return self._overrides[key]
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        return int(self.get(key, default))

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes")

    def get_list(self, key: str, default: list | None = None) -> list:
        val = self.get(key, default or [])
        if isinstance(val, list):
            return val
        return json.loads(val) if isinstance(val, str) else [val]

    @staticmethod
    def _cast(value: str, default: Any) -> Any:
        """Cast string env var to the type of default."""
        if isinstance(default, bool):
            return value.lower() in ("true", "1", "yes")
        if isinstance(default, int):
            return int(value)
        if isinstance(default, float):
            return float(value)
        if isinstance(default, list):
            return json.loads(value) if value.startswith("[") else value.split(",")
        return value


# ── Common config keys ──

class ConfigKeys:
    """Well-known configuration key constants."""

    # Database
    DB_HOST = "DB_HOST"
    DB_PORT = "DB_PORT"
    DB_NAME = "DB_NAME"
    DB_USER = "DB_USER"
    DB_PASSWORD = "DB_PASSWORD"
    DB_POOL_SIZE = "DB_POOL_SIZE"

    # Redis
    REDIS_HOST = "REDIS_HOST"
    REDIS_PORT = "REDIS_PORT"
    REDIS_PASSWORD = "REDIS_PASSWORD"
    REDIS_DB = "REDIS_DB"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS = "KAFKA_BOOTSTRAP_SERVERS"
    KAFKA_GROUP_ID = "KAFKA_GROUP_ID"

    # gRPC
    GRPC_PORT = "GRPC_PORT"
    GRPC_MAX_WORKERS = "GRPC_MAX_WORKERS"

    # HTTP
    HTTP_PORT = "HTTP_PORT"
    HTTP_HOST = "HTTP_HOST"

    # DeepSeek API
    DEEPSEEK_API_KEY = "DEEPSEEK_API_KEY"
    DEEPSEEK_BASE_URL = "DEEPSEEK_BASE_URL"

    # MinIO / OSS
    S3_ENDPOINT = "S3_ENDPOINT"
    S3_ACCESS_KEY = "S3_ACCESS_KEY"
    S3_SECRET_KEY = "S3_SECRET_KEY"
    S3_BUCKET = "S3_BUCKET"
