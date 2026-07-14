"""
Health check endpoint.

Returns the aggregate health status of the gateway and all
downstream gRPC services. Used by Kubernetes liveness/readiness probes
and external monitoring.
"""

from __future__ import annotations

import time

from fastapi import APIRouter

from libs.common.logging import get_logger

from ..grpc_client import grpc_manager

logger = get_logger(__name__)

router = APIRouter(tags=["health"])

# ── Service metadata ──

SERVICE_NAME = "gateway-svc"
SERVICE_VERSION = "0.1.0"
_START_TIME = time.monotonic()


def _uptime_seconds() -> int:
    """Get the service uptime in seconds."""
    return int(time.monotonic() - _START_TIME)


@router.get("/api/v1/health")
async def health_check():
    """
    Health check endpoint.

    Returns gateway status and the health of all downstream services.
    This endpoint is NOT rate-limited or auth-protected.
    """
    # Get downstream service health
    downstream = await grpc_manager.health_status()

    # Determine overall status
    all_healthy = all(svc["healthy"] for svc in downstream.values())
    any_degraded = any(
        not svc["healthy"] for svc in downstream.values()
    )

    if not downstream:
        overall_status = "healthy"  # No downstream services configured yet
    elif all_healthy:
        overall_status = "healthy"
    elif any_degraded:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    # Map downstream health into the response format
    services_map = {
        name: {
            "status": "healthy" if info["healthy"] else "unhealthy",
            "latency_ms": info["latency_ms"],
            "error": info.get("error"),
        }
        for name, info in downstream.items()
    }

    status_code = 200 if overall_status != "unhealthy" else 503

    return status_code, {
        "status": overall_status,
        "version": SERVICE_VERSION,
        "uptime_seconds": _uptime_seconds(),
        "services": services_map,
    }
