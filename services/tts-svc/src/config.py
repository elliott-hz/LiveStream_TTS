"""TTS Service specific configuration defaults."""

from libs.common.config import ServiceConfig, ConfigKeys


class TTSConfig(ServiceConfig):
    """TTS Service configuration with TTS-specific defaults."""

    def __init__(self):
        super().__init__("tts-svc")

    @property
    def grpc_port(self) -> int:
        return self.get_int(ConfigKeys.GRPC_PORT, 50051)

    @property
    def http_port(self) -> int:
        return self.get_int(ConfigKeys.HTTP_PORT, 8080)

    @property
    def model_path(self) -> str:
        return self.get("TTS_MODEL_PATH", "/models/cosyvoice2")

    @property
    def max_concurrent_synthesis(self) -> int:
        return self.get_int("TTS_MAX_CONCURRENT", 30)

    @property
    def cache_ttl_seconds(self) -> int:
        return self.get_int("TTS_CACHE_TTL", 3600)

    @property
    def use_gpu(self) -> bool:
        return self.get_bool("TTS_USE_GPU", True)
