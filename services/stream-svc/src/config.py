"""
Stream Service configuration.

Config keys:
  STREAM_GRPC_PORT          — gRPC server port (default 50067)
  STREAM_HTTP_PORT          — HTTP server port (default 8016)
  STREAM_RTMP_BASE_URL      — Base RTMP URL for push (default "rtmp://push.livestream-tts.com/live")
  STREAM_RECORDING_DIR      — Directory for HLS recording output (default "/data/recordings")
  STREAM_TRANSCODE_QUEUE    — Transcode job queue size (default 10)
"""

from libs.common.config import ServiceConfig, ConfigKeys


class StreamConfig(ServiceConfig):
    """Stream Service configuration with stream-specific defaults."""

    def __init__(self):
        super().__init__("stream-svc")

    @property
    def grpc_port(self) -> int:
        return self.get_int(ConfigKeys.GRPC_PORT, 50067)

    @property
    def http_port(self) -> int:
        return self.get_int(ConfigKeys.HTTP_PORT, 8016)

    @property
    def rtmp_base_url(self) -> str:
        return self.get("STREAM_RTMP_BASE_URL", "rtmp://push.livestream-tts.com/live")

    @property
    def recording_dir(self) -> str:
        return self.get("STREAM_RECORDING_DIR", "/data/recordings")

    @property
    def transcode_queue_size(self) -> int:
        return self.get_int("STREAM_TRANSCODE_QUEUE", 10)
