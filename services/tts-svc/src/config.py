"""TTS Service specific configuration defaults.

Backend modes:
  - ``mock`` (default) — sine-wave generator, no external API dependency
  - ``cloud`` — Alibaba Cloud NLS (CosyVoice) streaming TTS API
"""

from libs.common.config import ConfigKeys, ServiceConfig


class TTSConfig(ServiceConfig):
    """TTS Service configuration with TTS-specific defaults."""

    def __init__(self):
        super().__init__("tts-svc")

    # ── Server ports ──────────────────────────────────────────

    @property
    def grpc_port(self) -> int:
        return self.get_int(ConfigKeys.GRPC_PORT, 50059)

    @property
    def http_port(self) -> int:
        return self.get_int(ConfigKeys.HTTP_PORT, 8008)

    # ── TTS Backend ───────────────────────────────────────────

    @property
    def tts_backend(self) -> str:
        """TTS backend: 'mock' (sine wave) or 'cloud' (Alibaba NLS API)."""
        return self.get("TTS_BACKEND", "mock")

    # ── Cloud TTS: Alibaba Cloud NLS (CosyVoice) ──────────────

    @property
    def aliyun_access_key_id(self) -> str:
        """Alibaba Cloud RAM AccessKey ID."""
        return self.get("TTS_ALIYUN_ACCESS_KEY_ID", "")

    @property
    def aliyun_access_key_secret(self) -> str:
        """Alibaba Cloud RAM AccessKey Secret."""
        return self.get("TTS_ALIYUN_ACCESS_KEY_SECRET", "")

    @property
    def aliyun_nls_app_key(self) -> str:
        """NLS (Intelligent Speech Interaction) project AppKey."""
        return self.get("TTS_ALIYUN_APP_KEY", "")

    @property
    def aliyun_nls_endpoint(self) -> str:
        """NLS WebSocket endpoint. Default: Shanghai region."""
        return self.get("TTS_ALIYUN_ENDPOINT", "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1")

    @property
    def cloud_voice_name(self) -> str:
        """Voice name for cloud TTS (e.g. Aixia, Aiyun, Aida)."""
        return self.get("TTS_CLOUD_VOICE", "Aixia")

    @property
    def cloud_speech_rate(self) -> int:
        """Speech rate for cloud TTS (-500 to 500, 0 = normal)."""
        return self.get_int("TTS_CLOUD_SPEECH_RATE", 0)

    @property
    def cloud_volume(self) -> int:
        """Volume for cloud TTS (0-100)."""
        return self.get_int("TTS_CLOUD_VOLUME", 80)

    # ── Local model (Phase 3 CosyVoice2 self-host fallback) ───

    @property
    def model_path(self) -> str:
        return self.get("TTS_MODEL_PATH", "/models/cosyvoice2")

    @property
    def use_gpu(self) -> bool:
        return self.get_bool("TTS_USE_GPU", True)

    # ── Synthesis limits ──────────────────────────────────────

    @property
    def max_concurrent_synthesis(self) -> int:
        return self.get_int("TTS_MAX_CONCURRENT", 30)

    @property
    def cache_ttl_seconds(self) -> int:
        return self.get_int("TTS_CACHE_TTL", 3600)
