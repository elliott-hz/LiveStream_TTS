"""
platform-svc — Unified entry point for all 11 management services.

Single process hosting:
  - gRPC server (port 50050): 90 RPCs across 11 services
  - HTTP server (port 8081): ~79 REST endpoints across 11 modules

Usage:
    python -m services.platform_svc.src.main
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── Path setup ──
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from libs.common.config import ServiceConfig
from libs.common.grpc_utils import create_grpc_server
from libs.common.logging import setup_logging, get_logger
from libs.db import Database

from .config import platform_config

logger = get_logger(__name__)


async def main() -> None:
    """Start gRPC + HTTP servers with all 11 modules registered."""
    setup_logging(service_name="platform-svc")

    # ── 1. Infrastructure ──
    db = Database(platform_config)
    await db.connect()
    logger.info("db.connected")

    # ── 2. gRPC server ──
    grpc_server = create_grpc_server(platform_config)
    grpc_port = platform_config.grpc_port

    # ── 3. Import & register all gRPC servicers ──
    # Each servicer is registered on the shared grpc_server.
    _register_grpc_services(grpc_server, db)

    # ── 4. FastAPI app ──
    from fastapi import FastAPI
    app = FastAPI(title="platform-svc", version="0.1.0")
    _register_http_routes(app, db)

    # ── 5. Start both servers ──
    logger.info("platform_svc.starting", grpc_port=grpc_port, http_port=platform_config.http_port)

    import uvicorn
    grpc_task = asyncio.create_task(grpc_server.start())
    http_task = asyncio.create_task(
        asyncio.to_thread(
            uvicorn.run,
            app,
            host=platform_config.http_host,
            port=platform_config.http_port,
            log_level="info",
        )
    )

    try:
        await asyncio.gather(grpc_task, http_task)
    except asyncio.CancelledError:
        pass
    finally:
        await grpc_server.stop(5)
        await db.disconnect()
        logger.info("platform_svc.stopped")


def _register_grpc_services(grpc_server, db: Database) -> None:
    """Register all 11 gRPC servicers on the shared server."""
    from .modules.user.api.grpc_impl import UserServiceServicer
    from .modules.user.services.auth_service import AuthService
    from .modules.user.services.user_service import UserService
    from libs.proto.user.v1 import user_pb2_grpc

    auth_svc = AuthService(platform_config)
    user_svc_instance = UserService(platform_config)
    user_servicer = UserServiceServicer(auth_svc, user_svc_instance)
    user_pb2_grpc.add_UserServiceServicer_to_server(user_servicer, grpc_server)
    logger.debug("grpc.registered", service="UserService")

    # Pattern: factory-based servicers (create new service per request)
    from .modules.product.api.grpc_impl import ProductServiceServicer
    from .modules.product.services.product_service import ProductService
    from libs.proto.product.v1 import product_pb2_grpc

    async def _product_factory():
        return ProductService()
    product_servicer = ProductServiceServicer(_product_factory)
    product_pb2_grpc.add_ProductServiceServicer_to_server(product_servicer, grpc_server)
    logger.debug("grpc.registered", service="ProductService")

    from .modules.script.api.grpc_impl import ScriptServiceServicer
    from .modules.script.config import ScriptConfig
    from libs.proto.script.v1 import script_pb2_grpc

    script_servicer = ScriptServiceServicer(db, ScriptConfig())
    script_pb2_grpc.add_ScriptServiceServicer_to_server(script_servicer, grpc_server)
    logger.debug("grpc.registered", service="ScriptService")

    from .modules.live_mgr.api.grpc_impl import LiveManagerServicer
    from .modules.live_mgr.services.live_room_service import LiveRoomService
    from .modules.live_mgr.services.playlist_service import PlaylistService
    from libs.proto.live_mgr.v1 import live_mgr_pb2_grpc

    async def _live_room_factory():
        return LiveRoomService(platform_config)
    async def _playlist_factory():
        return PlaylistService(platform_config)
    live_mgr_servicer = LiveManagerServicer(_live_room_factory, _playlist_factory)
    live_mgr_pb2_grpc.add_LiveManagerServiceServicer_to_server(live_mgr_servicer, grpc_server)
    logger.debug("grpc.registered", service="LiveManagerService")

    from .modules.avatar.api.grpc_impl import AvatarServiceServicer
    from .modules.avatar.services.avatar_service import AvatarService
    from libs.proto.avatar.v1 import avatar_pb2_grpc

    async def _avatar_factory():
        return AvatarService()
    avatar_servicer = AvatarServiceServicer(_avatar_factory)
    avatar_pb2_grpc.add_AvatarServiceServicer_to_server(avatar_servicer, grpc_server)
    logger.debug("grpc.registered", service="AvatarService")

    from .modules.voice.api.grpc_impl import VoiceServiceServicer
    from .modules.voice.services.voice_service import VoiceService
    from libs.proto.voice.v1 import voice_pb2_grpc

    async def _voice_factory():
        return VoiceService()
    voice_servicer = VoiceServiceServicer(_voice_factory)
    voice_pb2_grpc.add_VoiceServiceServicer_to_server(voice_servicer, grpc_server)
    logger.debug("grpc.registered", service="VoiceService")

    from .modules.billing.api.grpc_impl import BillingServiceServicer
    from .modules.billing.services.billing_service import BillingService
    from libs.proto.billing.v1 import billing_pb2_grpc

    async def _billing_factory():
        return BillingService()
    billing_servicer = BillingServiceServicer(_billing_factory)
    billing_pb2_grpc.add_BillingServiceServicer_to_server(billing_servicer, grpc_server)
    logger.debug("grpc.registered", service="BillingService")

    from .modules.analytics.api.grpc_impl import AnalyticsServiceServicer
    from .modules.analytics.services.analytics_service import AnalyticsService
    from libs.proto.analytics.v1 import analytics_pb2_grpc

    async def _analytics_factory():
        return AnalyticsService()
    analytics_servicer = AnalyticsServiceServicer(_analytics_factory)
    analytics_pb2_grpc.add_AnalyticsServiceServicer_to_server(analytics_servicer, grpc_server)
    logger.debug("grpc.registered", service="AnalyticsService")

    from .modules.audit.api.grpc_impl import AuditServiceServicer
    from .modules.audit.services.audit_service import AuditService
    from libs.proto.audit.v1 import audit_pb2_grpc

    async def _audit_factory():
        return AuditService()
    audit_servicer = AuditServiceServicer(_audit_factory)
    audit_pb2_grpc.add_AuditServiceServicer_to_server(audit_servicer, grpc_server)
    logger.debug("grpc.registered", service="AuditService")

    from .modules.platform_sync.api.grpc_impl import PlatformSyncServiceServicer
    from .modules.platform_sync.services.binding_service import BindingService
    from .modules.platform_sync.services.sync_service import SyncService
    from libs.proto.platform_sync.v1 import platform_sync_pb2_grpc

    async def _binding_factory():
        return BindingService()
    async def _sync_factory():
        return SyncService()
    platform_sync_servicer = PlatformSyncServiceServicer(_binding_factory, _sync_factory)
    platform_sync_pb2_grpc.add_PlatformSyncServiceServicer_to_server(platform_sync_servicer, grpc_server)
    logger.debug("grpc.registered", service="PlatformSyncService")

    from .modules.profile.api.grpc_impl import ProfileServiceServicer
    from .modules.profile.services.profile_service import ProfileService
    from libs.proto.profile.v1 import profile_pb2_grpc

    async def _profile_factory():
        return ProfileService()
    profile_servicer = ProfileServiceServicer(_profile_factory)
    profile_pb2_grpc.add_ProfileServiceServicer_to_server(profile_servicer, grpc_server)
    logger.debug("grpc.registered", service="ProfileService")

    logger.info("grpc.registered_all", count=11)


def _register_http_routes(app, db: Database) -> None:
    """Register all 11 modules' HTTP routes on the shared FastAPI app."""
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse

    # Health check
    @app.get("/api/v1/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "platform-svc"})

    # User module — uses factory function
    from .modules.user.http.routes import create_router as user_create_router
    from .modules.user.services.auth_service import AuthService
    from .modules.user.services.user_service import UserService
    auth_svc = AuthService(platform_config)
    user_svc_instance = UserService(platform_config)
    app.include_router(user_create_router(auth_svc, user_svc_instance), prefix="/api/v1/users")

    # Product module
    from .modules.product.http.routes import router as product_router
    app.include_router(product_router, prefix="/api/v1/products")

    # Script module
    from .modules.script.http.routes import router as script_router
    app.include_router(script_router, prefix="/api/v1/scripts")

    # Live Manager module
    from .modules.live_mgr.http.routes import create_router as live_mgr_create_router
    from .modules.live_mgr.services.live_room_service import LiveRoomService
    live_room_svc = LiveRoomService(platform_config)
    app.include_router(live_mgr_create_router(live_room_svc), prefix="/api/v1/live-rooms")

    # Avatar module
    from .modules.avatar.http.routes import router as avatar_router
    app.include_router(avatar_router, prefix="/api/v1/avatars")

    # Voice module
    from .modules.voice.http.routes import router as voice_router
    app.include_router(voice_router, prefix="/api/v1/voices")

    # Billing module
    from .modules.billing.http.routes import router as billing_router
    app.include_router(billing_router, prefix="/api/v1/billing")

    # Analytics module
    from .modules.analytics.http.routes import router as analytics_router
    app.include_router(analytics_router, prefix="/api/v1/analytics")

    # Audit module
    from .modules.audit.http.routes import router as audit_router
    app.include_router(audit_router, prefix="/api/v1/audit")

    # Platform Sync module
    from .modules.platform_sync.http.routes import router as platform_sync_router
    app.include_router(platform_sync_router, prefix="/api/v1/platform-sync")

    # Profile module
    from .modules.profile.http.routes import router as profile_router
    app.include_router(profile_router, prefix="/api/v1/profiles")

    logger.info("http.registered_all", count=12)  # 11 modules + health


if __name__ == "__main__":
    asyncio.run(main())
