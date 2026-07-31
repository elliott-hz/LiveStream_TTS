"""FastAPI 入口 — AI 直播工具 PoC"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.models.base import init_db
from backend.modules.product.router import router as product_router
from backend.modules.video_asset.router import router as video_asset_router
from backend.modules.live_video.router import router as live_video_router
from backend.modules.live_room.router import router as live_room_router
from backend.modules.live_control.router import router as live_control_router
from backend.modules.interaction.router import router as interaction_router
from backend.modules.analytics.router import router as analytics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：建表
    await init_db()
    yield
    # 关闭时：清理（PoC 阶段暂无需要）


app = FastAPI(
    title="AI 直播工具",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 允许前端 Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(product_router)
app.include_router(video_asset_router)
app.include_router(live_video_router)
app.include_router(live_room_router)
app.include_router(live_control_router)
app.include_router(interaction_router)
app.include_router(analytics_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
