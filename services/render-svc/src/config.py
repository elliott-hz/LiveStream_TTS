"""
Render Service configuration with GPU-related defaults.

Config keys:
  RENDER_GRPC_PORT         — gRPC server port (default 50061)
  RENDER_HTTP_PORT         — HTTP server port (default 8010)
  RENDER_GPU_DEVICE        — CUDA device index (default 0)
  RENDER_GPU_MEMORY_FRAC   — Fraction of GPU memory to reserve (default 0.8)
  RENDER_GPU_BATCH_SIZE    — Batch size for GPU operations (default 1)
  RENDER_FRAME_WIDTH       — Output frame width in pixels (default 1920)
  RENDER_FRAME_HEIGHT      — Output frame height in pixels (default 1080)
  RENDER_FPS               — Output frames per second (default 30)
"""

from libs.common.config import ServiceConfig, ConfigKeys


class RenderConfig(ServiceConfig):
    """Render Service configuration with renderer-specific defaults."""

    def __init__(self):
        super().__init__("render-svc")

    @property
    def grpc_port(self) -> int:
        return self.get_int(ConfigKeys.GRPC_PORT, 50061)

    @property
    def http_port(self) -> int:
        return self.get_int(ConfigKeys.HTTP_PORT, 8010)

    @property
    def gpu_device(self) -> int:
        return self.get_int("RENDER_GPU_DEVICE", 0)

    @property
    def gpu_memory_fraction(self) -> float:
        return float(self.get("RENDER_GPU_MEMORY_FRAC", 0.8))

    @property
    def gpu_batch_size(self) -> int:
        return self.get_int("RENDER_GPU_BATCH_SIZE", 1)

    @property
    def frame_width(self) -> int:
        return self.get_int("RENDER_FRAME_WIDTH", 1920)

    @property
    def frame_height(self) -> int:
        return self.get_int("RENDER_FRAME_HEIGHT", 1080)

    @property
    def fps(self) -> int:
        return self.get_int("RENDER_FPS", 30)

    # ── Rendering Engine ──

    @property
    def render_engine(self) -> str:
        """Rendering engine: 'viseme' (2D CPU) or 'wav2lip' (GPU, Phase 3)."""
        return self.get("RENDER_ENGINE", "viseme")

    @property
    def avatar_image_dir(self) -> str:
        """Directory for 2D avatar base images and viseme PNGs."""
        return self.get("AVATAR_IMAGE_DIR", "/assets/avatars")
