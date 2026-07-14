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
        return self.get_int("HTTP_PORT", 8009)

    @property
    def grpc_port(self) -> int:
        return self.get_int("GRPC_PORT", 50060)

    @property
    def grpc_max_workers(self) -> int:
        return self.get_int("GRPC_MAX_WORKERS", default=20)

    @property
    def log_level(self) -> str:
        return self.get("LOG_LEVEL", default="INFO")

    @property
    def log_json(self) -> bool:
        return self.get_bool("LOG_JSON", default=True)

    # ── NLP Backend ──
    @property
    def nlp_backend(self) -> str:
        """NLP backend mode: 'rule' (keyword+pattern) or 'model' (transformer ML).

        Default: 'rule' — fast, no model download needed, ~70% accuracy.
        'model' — loads small transformer models (bert-base-chinese),
        better accuracy (~85%) but needs ~400MB RAM and longer cold start.
        """
        return self.get("NLP_BACKEND", default="rule")

    @property
    def model_cache_dir(self) -> str:
        """Directory for downloaded transformer models."""
        return self.get("NLP_MODEL_CACHE_DIR", default="/models/nlp")

    @property
    def model_name(self) -> str:
        """Base model name for intent + sentiment classifiers.

        Uses small, CPU-friendly models:
        - 'bert-base-chinese' (~400MB, best accuracy)
        - 'shibing624/text2vec-base-chinese' (~400MB, sentence embeddings)
        - 'distilbert-base-chinese' (~200MB, faster, slightly lower accuracy)
        """
        return self.get("NLP_MODEL_NAME", default="bert-base-chinese")

    # ── Sensitive Word Detection ──
    @property
    def sensitive_dict_path(self) -> str:
        """Path to custom sensitive word dictionary file, if any."""
        return self.get("SENSITIVE_DICT_PATH", default="")

    @property
    def llm_semantic_enabled(self) -> bool:
        """Enable LLM-based semantic fallback for sensitive detection."""
        return self.get_bool("LLM_SEMANTIC_ENABLED", default=False)

    @property
    def pinyin_variant_enabled(self) -> bool:
        """Enable pinyin homophone detection for obfuscated sensitive words.

        Detects variants like 威芯→微信, 抠抠→QQ, etc.
        Only adds ~1-2ms overhead per check.
        """
        return self.get_bool("PINYIN_VARIANT_ENABLED", default=True)

    # ── LLM ──
    @property
    def deepseek_api_key(self) -> str:
        return self.get("DEEPSEEK_API_KEY", default="")

    @property
    def deepseek_base_url(self) -> str:
        return self.get("DEEPSEEK_BASE_URL", default="https://api.deepseek.com")


# Singleton
config = NLPConfig()
