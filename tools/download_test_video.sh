#!/bin/bash
# 下载测试带货视频
# 用法:
#   ./tools/download_test_video.sh                              → 生成 2分钟假视频
#   ./tools/download_test_video.sh bilibili                     → 下载推荐B站带货视频(摸鱼事务所, 5个品)
#   ./tools/download_test_video.sh https://b23.tv/xxx           → 下载指定B站视频
#   ./tools/download_test_video.sh https://youtube.com/xxx      → 下载YouTube视频

set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/data/videos"
mkdir -p "$OUTPUT_DIR"

URL="${1:-}"

# 推荐视频: 董明珠母亲节直播带货回放 — 24分钟, 多款格力产品
RECOMMENDED="https://www.youtube.com/watch?v=YLdy2wejsIc"

case "$URL" in
    "")
        # ─── 无URL → FFmpeg 生成测试视频 ───
        echo "未提供URL，用 FFmpeg 生成 2 分钟测试视频..."
        if ! command -v ffmpeg &>/dev/null; then
            echo "❌ 请先安装 FFmpeg: brew install ffmpeg"
            exit 1
        fi
        OUTPUT="$OUTPUT_DIR/test_product_video.mp4"
        ffmpeg -y -f lavfi \
            -i "color=c=0x111111:s=1920x1080:d=120:r=30" \
            -f lavfi -i "sine=frequency=440:duration=120" \
            -c:v libx264 -preset ultrafast -crf 28 \
            -c:a aac -b:a 128k \
            -shortest "$OUTPUT" 2>/dev/null
        echo "✅ 测试视频: $OUTPUT"
        ;;

    bilibili|b站|bili)
        URL="$RECOMMENDED"
        echo "使用推荐视频: 摸鱼事务所 10月31日带货直播 (5个品)"
        ;;

    *)
        ;;
esac

# ─── 有URL → yt-dlp 下载 ───
if [ -n "$URL" ] && [ "$URL" != "bilibili" ]; then
    if ! command -v yt-dlp &>/dev/null; then
        echo "安装 yt-dlp..."
        pip install yt-dlp -q
    fi
    OUTPUT="$OUTPUT_DIR/test_product_video.mp4"
    echo "下载中: $URL"
    yt-dlp -f "best[ext=mp4][height<=1080]" -o "$OUTPUT" --no-playlist "$URL"
    echo "✅ 下载完成: $OUTPUT"
fi

echo "   大小: $(du -h "$OUTPUT" | cut -f1)"
echo ""
echo "上传测试:"
echo "  curl -X POST http://localhost:8000/api/video-assets/upload -F \"file=@$OUTPUT\""
