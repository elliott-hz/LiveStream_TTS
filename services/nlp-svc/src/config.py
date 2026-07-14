"""
NLP service configuration.

Extends the base ServiceConfig with NLP-specific settings.
"""

from libs.common.config import ServiceConfig


class NLPConfig(ServiceConfig):
    """Configuration for the NLP service."""

    def __init__(self) -> None:
        super().__init__("nlp-svc")

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
    def grpc_max_workers(self) -> int:
        return self.get_int("GRPC_MAX_WORKERS", default=20)

    @property
    def log_level(self) -> str:
        return self.get("LOG_LEVEL", default="INFO")

    @property
    def log_json(self) -> bool:
        return self.get_bool("LOG_JSON", default=True)

    # ── Sensitive Word Detection ──
    @property
    def sensitive_dict_path(self) -> str:
        """Path to custom sensitive word dictionary file, if any."""
        return self.get("SENSITIVE_DICT_PATH", default="")

    @property
    def llm_semantic_enabled(self) -> bool:
        """Enable LLM-based semantic fallback for sensitive detection."""
        return self.get_bool("LLM_SEMANTIC_ENABLED", default=False)

    # ── LLM ──
    @property
    def deepseek_api_key(self) -> str:
        return self.get("DEEPSEEK_API_KEY", default="")

    @property
    def deepseek_base_url(self) -> str:
        return self.get("DEEPSEEK_BASE_URL", default="https://api.deepseek.com")


# Singleton
config = NLPConfig()
