"""
gRPC server & client utilities for all microservices.

Standard patterns: health check service reflection, interceptors, retry.
"""

import asyncio
import time
from typing import Any

import grpc
from grpc import aio
from grpc_health.v1 import health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from libs.common.logging import get_logger

logger = get_logger(__name__)

# ── Standard interceptors ──


class LoggingInterceptor(aio.ServerInterceptor):
    """Logs every gRPC call with timing."""

    async def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method
        start = time.monotonic()
        try:
            result = await continuation(handler_call_details)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.debug("grpc.call", method=method, elapsed_ms=round(elapsed_ms, 2), status="ok")
            return result
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.warning("grpc.call_error", method=method, elapsed_ms=round(elapsed_ms, 2), error=str(e))
            raise


class TracingInterceptor(aio.ServerInterceptor):
    """Injects/extracts trace context into gRPC metadata."""

    async def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata or {})
        trace_id = metadata.get("x-trace-id", None)
        if trace_id:
            # Store in contextvar for downstream use
            pass
        return await continuation(handler_call_details)


# ── Server factory ──


def create_grpc_server(
    service_name: str,
    port: int = 50051,
    max_workers: int = 20,
    interceptors: list | None = None,
) -> aio.Server:
    """Create a pre-configured async gRPC server.

    Includes health check service + server reflection by default.
    """
    if interceptors is None:
        interceptors = [LoggingInterceptor()]

    server = aio.server(
        interceptors=interceptors,
        options=[
            ("grpc.max_concurrent_streams", max_workers),
            ("grpc.keepalive_time_ms", 30000),
            ("grpc.keepalive_timeout_ms", 10000),
        ],
    )

    # Health check service
    health_servicer = health_pb2_grpc.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)

    # Server reflection
    service_names = (
        health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    server.add_insecure_port(f"[::]:{port}")
    return server
