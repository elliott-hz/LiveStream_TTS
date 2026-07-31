#!/bin/bash
set -e

BACKEND_PORT=8000
FRONTEND_PORT=5173
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================="
echo "  AI 直播工具 — 一键启动 (Mock模式)"
echo "========================================="

# ─── 1. 杀旧进程 ───
echo ""
echo "[1/4] 清理旧进程..."

kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        echo "  → 端口 $port 被 PID=$pid 占用，正在终止..."
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT
echo "  → 端口 $BACKEND_PORT / $FRONTEND_PORT 已释放"

# ─── 2. 后端依赖 ───
echo ""
echo "[2/4] 安装后端依赖..."
cd "$PROJECT_DIR"
pip install -r backend/requirements.txt -q
echo "  → 后端依赖就绪"

# ─── 3. 前端依赖 + 启动 ───
echo ""
echo "[3/4] 安装前端依赖 + 启动..."
cd "$PROJECT_DIR/frontend"
npm install
echo "  → 前端依赖就绪"

echo ""
echo "[4/4] 启动服务..."
npm run dev &
FRONTEND_PID=$!

# 后端 (前台)
cd "$PROJECT_DIR"
echo ""
echo "  后端 API:   http://localhost:$BACKEND_PORT/docs"
echo "  前端页面:   http://localhost:$FRONTEND_PORT"
echo "  健康检查:   http://localhost:$BACKEND_PORT/api/health"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "========================================="
echo ""

# 退出时杀前端进程
trap "kill $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

MOCK_EXTERNAL_API=true python -m uvicorn backend.main:app \
    --reload \
    --host 0.0.0.0 \
    --port $BACKEND_PORT

# 后端退出后杀前端
kill $FRONTEND_PID 2>/dev/null
