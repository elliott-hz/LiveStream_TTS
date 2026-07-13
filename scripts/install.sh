#!/bin/bash
# 安装 TTS Platform POC 依赖

set -e

echo "📦 Installing TTS Platform POC dependencies..."

# Python 依赖
echo "  → Python packages..."
python3 -m pip install --break-system-packages -q \
  fastapi \
  uvicorn \
  websockets \
  pydantic \
  pypinyin \
  numpy \
  grpcio \
  grpcio-tools \
  edge-tts \
  2>&1 | tail -1

# 测试依赖
echo "  → Test packages..."
python3 -m pip install --break-system-packages -q \
  pytest \
  pytest-asyncio \
  requests \
  2>&1 | tail -1

# 检查 ffmpeg
echo "  → Checking ffmpeg..."
if ! which ffmpeg >/dev/null 2>&1; then
  echo "  ⚠️  ffmpeg not found. Installing via Homebrew..."
  brew install ffmpeg
else
  echo "  ✅ ffmpeg found: $(which ffmpeg)"
fi

# 生成 gRPC 代码
echo "  → Generating gRPC stubs..."
cd "$(dirname "$0")/.."
python3 -m grpc_tools.protoc \
  -Iproto \
  --python_out=src \
  --grpc_python_out=src \
  proto/tts.proto

# 修复 gRPC 生成的 import 为相对导入
sed -i '' 's/^import tts_pb2/from . import tts_pb2/' src/tts_pb2_grpc.py 2>/dev/null || true

echo ""
echo "✅ Done. Run with:  python3 -m src.main"
