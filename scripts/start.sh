#!/bin/bash
# 停掉端口上的旧进程，重启 TTS Platform POC 服务

PORT=${1:-8765}
GRPC_PORT=${2:-50051}

echo "🔍 Checking port $PORT and $GRPC_PORT..."

# 停掉占用端口的进程
for P in $PORT $GRPC_PORT; do
    PID=$(lsof -ti :$P 2>/dev/null)
    if [ -n "$PID" ]; then
        echo "  → Killing process $PID on port $P..."
        kill -9 $PID 2>/dev/null || true
        sleep 1
    fi
done

# 确认端口已释放
if lsof -ti :$PORT >/dev/null 2>&1; then
    echo "  ⚠️  Port $PORT still in use, trying again..."
    lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
    sleep 2
fi

echo "  ✅ Ports clear"

# 进入项目目录
cd "$(dirname "$0")/.."

echo "🚀 Starting TTS Platform POC..."
echo "  Web Page  → http://0.0.0.0:$PORT/            ← 打开浏览器访问"
echo "  WebSocket → ws://0.0.0.0:$PORT/ws/v1/tts"
echo "  gRPC     → 0.0.0.0:$GRPC_PORT"
echo "  REST     → http://0.0.0.0:$PORT/api/v1/health"
echo "  Voices   → http://0.0.0.0:$PORT/api/v1/voices"
echo ""

# 启动（前台，Ctrl+C 停止）
python3 -m src.main
