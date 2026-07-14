"""
Interact service configuration.

Extends the base ServiceConfig with interaction-specific settings:
session defaults, moderator config, product context, pipeline tuning.
"""

from libs.common.config import ServiceConfig


class InteractConfig(ServiceConfig):
    """Configuration for the interaction service."""

    def __init__(self) -> None:
        super().__init__("interact-svc")

    # ── Server ──

    @property
    def http_host(self) -> str:
        return self.get("HTTP_HOST", default="0.0.0.0")

    @property
    def http_port(self) -> int:
        return self.get_int("HTTP_PORT", default=8080)

    @property
    def grpc_port(self) -> int:
        return self.get_int("GRPC_PORT", default=50051)

    @property
    def log_level(self) -> str:
        return self.get("LOG_LEVEL", default="INFO")

    @property
    def log_json(self) -> bool:
        return self.get_bool("LOG_JSON", default=True)

    # ── Kafka ──

    @property
    def kafka_bootstrap_servers(self) -> str:
        return self.get("KAFKA_BOOTSTRAP_SERVERS", default="localhost:9093")

    @property
    def kafka_group_id(self) -> str:
        return self.get("KAFKA_GROUP_ID", default="interact-svc")

    # ── Session Defaults ──

    @property
    def default_voice_id(self) -> str:
        return self.get("DEFAULT_VOICE_ID", default="default")

    @property
    def default_avatar_id(self) -> str:
        return self.get("DEFAULT_AVATAR_ID", default="default")

    @property
    def default_system_prompt(self) -> str:
        return self.get(
            "DEFAULT_SYSTEM_PROMPT",
            default=(
                "你是一名专业带货主播，热情、亲切、专业。"
                "回复要简短有力，适合直播场景。"
                "禁止使用违禁词。"
                "始终围绕商品和直播主题。"
            ),
        )

    @property
    def default_reply_threshold(self) -> float:
        return self.get_float("DEFAULT_REPLY_THRESHOLD", default=0.3)

    # ── Moderator Defaults ──

    @property
    def moderator_account_id(self) -> str:
        return self.get("MODERATOR_ACCOUNT_ID", default="mod_official")

    @property
    def comment_interval_seconds(self) -> float:
        return self.get_float("COMMENT_INTERVAL_SECONDS", default=30.0)

    # ── Pipeline Tuning ──

    @property
    def dedup_ttl_seconds(self) -> int:
        """TTL for danmaku deduplication cache."""
        return self.get_int("DEDUP_TTL_SECONDS", default=300)

    @property
    def max_danmaku_queue_size(self) -> int:
        return self.get_int("MAX_DANMAKU_QUEUE_SIZE", default=10000)

    # ── Product Context (default/mock) ──

    @property
    def product_title(self) -> str:
        return self.get("PRODUCT_TITLE", default="超润保湿精华液")

    @property
    def product_price(self) -> str:
        return self.get("PRODUCT_PRICE", default="99.9")

    @property
    def product_highlight(self) -> str:
        return self.get(
            "PRODUCT_HIGHLIGHT",
            default="三重玻尿酸补水, 24小时长效锁水, 敏感肌可用",
        )

    # Deprecation shim: get_float is not in base ServiceConfig
    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key, default)
        return float(val)


# Singleton
config = InteractConfig()
