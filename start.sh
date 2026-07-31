#!/bin/bash
set -e

PORT=8000
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================="
echo "  AI 直播工具 — 后端启动脚本"
echo "========================================="

# 1. 杀掉占用端口的进程
echo ""
echo "[1/3] 检查端口 $PORT ..."

# macOS/Linux 通用：查找并杀掉占端口的进程
PID=$(lsof -ti:$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "  → 发现进程 PID=$PID 占用端口 $PORT，正在终止..."
    kill -9 $PID 2>/dev/null || true
    sleep 1
    echo "  → 已终止"
else
    echo "  → 端口 $PORT 空闲"
fi

# 2. 安装依赖
echo ""
echo "[2/3] 安装依赖..."
cd "$PROJECT_DIR"
pip install -r backend/requirements.txt -q
echo "  → 依赖就绪"

# 3. 清理旧数据库 (可选 — 如果不需要保留数据)
# rm -f "$PROJECT_DIR/data/app.db"

# 4. 启动
echo ""
echo "[3/3] 启动服务 (Mock模式) ..."
echo ""
echo "  API 文档:  http://localhost:$PORT/docs"
echo "  健康检查:  http://localhost:$PORT/api/health"
echo ""
echo "========================================="

MOCK_EXTERNAL_API=true uvicorn backend.main:app \
    --reload \
    --host 0.0.0.0 \
    --port $PORT
