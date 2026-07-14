"""
gRPC client connection manager.

Maintains persistent gRPC channels to all downstream microservices.
Provides health checking with retry and graceful shutdown.

Usage:
    async with GrpcClientManager() as mgr:
        stub = mgr.user_stub
        response = await stub.Login(...)
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Generic, TypeVar

import grpc
from grpc import aio

from libs.common.logging import get_logger

from .config import config

logger = get_logger(__name__)

# Re-export for downstream use
grpc_status = grpc.StatusCode
grpc_error = grpc.RpcError

# ── Type vars for typed stubs ──

TStub = TypeVar("TStub")


# ── Service endpoint descriptor ──

@dataclass
class ServiceEndpoint:
    """A downstream gRPC service endpoint."""
    name: str
    host: str
    port: int
    timeout_seconds: float = 10.0
    health_check_interval: float = 30.0
    reconnect_delay: float = 1.0

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


# ── Managed channel wrapper ──

@dataclass
class ManagedChannel(Generic[TStub]):
    """A managed gRPC channel with health checking and reconnection."""

    endpoint: ServiceEndpoint
    stub_factory: callable  # (grpc.Channel) -> TStub
    _channel: aio.Channel | None = field(default=None, repr=False)
    _stub: TStub | None = field(default=None, repr=False)
    _healthy: bool = field(default=True, repr=False)
    _last_health_check: float = field(default=0.0, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def stub(self) -> TStub:
        """Get the typed gRPC stub (raises if not connected)."""
        if self._stub is None:
            raise RuntimeError(
                f"gRPC channel to {self.endpoint.name} is not connected"
            )
        return self._stub

    @property
    def is_healthy(self) -> bool:
        return self._healthy

    async def connect(self) -> None:
        """Create the gRPC channel and stub."""
        async with self._lock:
            if self._channel is not None:
                return
            logger.info(
                "grpc.connect",
                service=self.endpoint.name,
                address=self.endpoint.address,
            )
            self._channel = aio.insecure_channel(
                self.endpoint.address,
                options=[
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 10000),
                    ("grpc.keepalive_permit_without_calls", 1),
                    ("grpc.http2.max_pings_without_data", 0),
                ],
            )
            self._stub = self.stub_factory(self._channel)
            self._healthy = True

    async def disconnect(self) -> None:
        """Close the gRPC channel."""
        async with self._lock:
            if self._channel is not None:
                await self._channel.close()
                self._channel = None
                self._stub = None
                self._healthy = False
                logger.info(
                    "grpc.disconnect",
                    service=self.endpoint.name,
                )

    async def check_health(self) -> bool:
        """Perform a health check by attempting to get channel state.

        Returns True if healthy, False otherwise.
        """
        now = time.monotonic()
        if now - self._last_health_check < 5.0:
            return self._healthy

        self._last_health_check = now
        if self._channel is None:
            self._healthy = False
            return False

        try:
            # Wait for channel to be ready with a short deadline
            await asyncio.wait_for(
                self._channel.channel_ready(),
                timeout=self.endpoint.timeout_seconds,
            )
            self._healthy = True
        except (asyncio.TimeoutError, grpc.RpcError) as exc:
            self._healthy = False
            logger.warning(
                "grpc.health_check_failed",
                service=self.endpoint.name,
                error=str(exc),
            )
            # Attempt reconnection
            await self._reconnect()
        return self._healthy

    async def _reconnect(self) -> None:
        """Reconnect the channel after a failure."""
        logger.info(
            "grpc.reconnecting",
            service=self.endpoint.name,
            address=self.endpoint.address,
        )
        await self.disconnect()
        await asyncio.sleep(self.endpoint.reconnect_delay)
        await self.connect()


# ── Client Manager ──

class GrpcClientManager:
    """Manages all downstream gRPC connections.

    Usage:
        manager = GrpcClientManager()
        await manager.start()
        # ... use manager.user_stub ...
        await manager.stop()
    """

    def __init__(self) -> None:
        self._channels: dict[str, ManagedChannel[Any]] = {}
        self._health_task: asyncio.Task[None] | None = None
        self._running = False

        # Lazy-import stubs at construction time so proto modules
        # are importable without generated code present at import time.
        self._user_stub: Any = None
        self._product_stub: Any = None
        self._script_stub: Any = None
        self._tts_stub: Any = None

    # ── Stub accessors ──
    # These are populated after start() is called.

    @property
    def user_stub(self) -> Any:
        if self._user_stub is None:
            raise RuntimeError("gRPC client manager not started")
        return self._user_stub

    @property
    def product_stub(self) -> Any:
        if self._product_stub is None:
            raise RuntimeError("gRPC client manager not started")
        return self._product_stub

    @property
    def script_stub(self) -> Any:
        if self._script_stub is None:
            raise RuntimeError("gRPC client manager not started")
        return self._script_stub

    @property
    def tts_stub(self) -> Any:
        if self._tts_stub is None:
            raise RuntimeError("gRPC client manager not started")
        return self._tts_stub

    # ── Channel accessors for direct use ──

    @property
    def user_channel(self) -> ManagedChannel:
        return self._get_channel("user-svc")

    @property
    def product_channel(self) -> ManagedChannel:
        return self._get_channel("product-svc")

    @property
    def script_channel(self) -> ManagedChannel:
        return self._get_channel("script-svc")

    @property
    def tts_channel(self) -> ManagedChannel:
        return self._get_channel("tts-svc")

    def _get_channel(self, name: str) -> ManagedChannel:
        if name not in self._channels:
            raise RuntimeError(f"gRPC channel '{name}' not registered")
        return self._channels[name]

    # ── Lifecycle ──

    async def start(self) -> None:
        """Connect to all downstream services."""
        from proto.user.v1 import user_pb2_grpc as user_grpc
        from proto.product.v1 import product_pb2_grpc as product_grpc
        from proto.script.v1 import script_pb2_grpc as script_grpc
        from proto.tts.v1 import tts_pb2_grpc as tts_grpc

        self._register(
            "user-svc",
            ServiceEndpoint("user-svc", config.user_svc_grpc_host, config.user_svc_grpc_port),
            user_grpc.UserServiceStub,
        )
        self._register(
            "product-svc",
            ServiceEndpoint("product-svc", config.product_svc_grpc_host, config.product_svc_grpc_port),
            product_grpc.ProductServiceStub,
        )
        self._register(
            "script-svc",
            ServiceEndpoint("script-svc", config.script_svc_grpc_host, config.script_svc_grpc_port),
            script_grpc.ScriptServiceStub,
        )
        self._register(
            "tts-svc",
            ServiceEndpoint("tts-svc", config.tts_svc_grpc_host, config.tts_svc_grpc_port),
            tts_grpc.TTSServiceStub,
        )

        # Connect in parallel
        tasks = [ch.connect() for ch in self._channels.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Start background health checker
        self._running = True
        self._health_task = asyncio.create_task(self._health_loop())

        # Expose convience stubs
        self._user_stub = self._channels["user-svc"].stub
        self._product_stub = self._channels["product-svc"].stub
        self._script_stub = self._channels["script-svc"].stub
        self._tts_stub = self._channels["tts-svc"].stub

        logger.info("grpc.client_manager_started", channels=list(self._channels.keys()))

    async def stop(self) -> None:
        """Disconnect all downstream services."""
        self._running = False
        if self._health_task is not None:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        tasks = [ch.disconnect() for ch in self._channels.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._channels.clear()
        self._user_stub = None
        self._product_stub = None
        self._script_stub = None
        self._tts_stub = None
        logger.info("grpc.client_manager_stopped")

    async def health_status(self) -> dict[str, dict[str, Any]]:
        """Get health status of all downstream services.

        Returns:
            Dict mapping service name to {"healthy": bool, "latency_ms": float, "error": str | None}
        """
        results: dict[str, dict[str, Any]] = {}
        for name, ch in self._channels.items():
            start = time.monotonic()
            try:
                healthy = await ch.check_health()
                latency_ms = (time.monotonic() - start) * 1000
                results[name] = {
                    "healthy": healthy,
                    "latency_ms": round(latency_ms, 2),
                    "error": None,
                }
            except Exception as exc:
                results[name] = {
                    "healthy": False,
                    "latency_ms": 0,
                    "error": str(exc),
                }
        return results

    # ── Private helpers ──

    def _register(
        self,
        name: str,
        endpoint: ServiceEndpoint,
        stub_class: type,
    ) -> None:
        """Register a downstream service."""
        channel = ManagedChannel(
            endpoint=endpoint,
            stub_factory=lambda ch: stub_class(ch),
        )
        self._channels[name] = channel

    async def _health_loop(self) -> None:
        """Periodically check health of all downstream services."""
        while self._running:
            await asyncio.sleep(15.0)
            for name, ch in list(self._channels.items()):
                try:
                    await ch.check_health()
                except Exception as exc:
                    logger.error(
                        "grpc.health_loop_error",
                        service=name,
                        error=str(exc),
                    )

    # ── Context manager support ──

    async def __aenter__(self) -> "GrpcClientManager":
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()


# Singleton
grpc_manager = GrpcClientManager()
