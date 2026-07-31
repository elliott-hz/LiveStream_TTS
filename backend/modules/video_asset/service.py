"""视频素材库 — 解析管线编排"""

import os
import json
import asyncio
import subprocess

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.models.video import RawVideo, VideoSegment
from backend.modules.video_asset.schemas import SegmentUpdate


# ═══════════════════════════════════════════════════════════
#  CRUD
# ═══════════════════════════════════════════════════════════

async def list_videos(db: AsyncSession) -> list[RawVideo]:
    result = await db.execute(
        select(RawVideo).options(selectinload(RawVideo.segments))
        .order_by(RawVideo.created_at.desc())
    )
    return list(result.scalars().all())


async def get_video(db: AsyncSession, video_id: str) -> RawVideo | None:
    result = await db.execute(
        select(RawVideo).options(selectinload(RawVideo.segments))
        .where(RawVideo.id == video_id)
    )
    return result.scalar_one_or_none()


async def create_video(db: AsyncSession, file_name: str, file_path: str) -> RawVideo:
    video = RawVideo(file_name=file_name, file_path=file_path, parse_status="pending")
    db.add(video)
    await db.commit()
    await db.refresh(video)
    return video


async def update_segment(db: AsyncSession, segment_id: str, data: SegmentUpdate) -> VideoSegment | None:
    result = await db.execute(select(VideoSegment).where(VideoSegment.id == segment_id))
    seg = result.scalar_one_or_none()
    if not seg:
        return None
    if data.start_time is not None:
        seg.start_time = data.start_time
    if data.end_time is not None:
        seg.end_time = data.end_time
    if data.product_id is not None:
        seg.product_id = data.product_id
    if data.script is not None:
        seg.script = data.script
    await db.commit()
    await db.refresh(seg)
    return seg


async def publish_segment(db: AsyncSession, segment_id: str) -> VideoSegment | None:
    result = await db.execute(select(VideoSegment).where(VideoSegment.id == segment_id))
    seg = result.scalar_one_or_none()
    if not seg:
        return None
    seg.status = "published"
    await db.commit()
    await db.refresh(seg)
    return seg


# ═══════════════════════════════════════════════════════════
#  解析管线 (被 BackgroundTasks 调用)
# ═══════════════════════════════════════════════════════════

async def parse_video_pipeline(video_id: str):
    """
    5 步解析管线:
      1. FFmpeg 预处理 → 场景切换点 + 关键帧 + 音频
      2. 并行: Paraformer ASR + Qwen-VL-Max 画面分析
      3. DeepSeek 融合分品 → 商品分段
      4. RAG 商品知识库匹配
      5. FFmpeg 切割
    """
    from backend.models.base import async_session
    from backend.engine import ffmpeg_preprocess, asr, vision, rag, llm

    async with async_session() as db:
        video = await db.get(RawVideo, video_id)
        if not video:
            return

        video.parse_status = "processing"
        await db.commit()

        try:
            work_dir = os.path.join(settings.video_dir, f"parse_{video_id}")
            os.makedirs(work_dir, exist_ok=True)

            # ─── Step 1: FFmpeg 预处理 (10%) ───
            video.parse_progress = 5
            await db.commit()

            pre = ffmpeg_preprocess.preprocess(video.file_path, work_dir)
            video.parse_progress = 15
            await db.commit()

            # ─── Step 2: 并行 ASR + 视觉分析 (30%) ───
            video.parse_progress = 20
            await db.commit()

            asr_task = asr.transcribe(pre.audio_path)
            vision_task = vision.analyze_keyframes(pre.keyframes)

            asr_result, vision_results = await asyncio.gather(asr_task, vision_task)

            video.parse_progress = 35
            await db.commit()

            # ─── Step 3: LLM 融合分品 (60%) ───
            segments = await _llm_fusion(
                asr_text=asr_result.get("full_text", ""),
                asr_sentences=asr_result.get("sentences", []),
                vision_results=vision_results,
                scene_changes=pre.scene_changes,
                duration=pre.duration,
            )
            video.parse_progress = 55
            await db.commit()

            # ─── Step 4: RAG 匹配每个商品 (65%) ───
            for seg in segments:
                enriched = rag.enrich_product(seg.get("product_hint", ""))
                seg["sku"] = enriched.get("sku", "")
                seg["product_name"] = enriched.get("name", seg.get("product_name", ""))
                seg["product_info"] = enriched  # 保存完整匹配结果

            video.parse_progress = 65
            await db.commit()

            # ─── Step 5: FFmpeg 切割 (90%) ───
            total = len(segments)
            for i, seg in enumerate(segments):
                clip_name = f"{video_id}_{i}.mp4"
                clip_path = os.path.join(settings.video_dir, clip_name)
                _cut_video(video.file_path, seg["start"], seg["end"], clip_path)

                segment = VideoSegment(
                    raw_video_id=video_id,
                    start_time=seg["start"],
                    end_time=seg["end"],
                    script=seg.get("script", ""),
                    clip_path=clip_path,
                    status="pending",
                )
                db.add(segment)

                progress = 65 + int((i + 1) / total * 30)
                video.parse_progress = progress
                await db.commit()

            video.parse_status = "done"
            video.parse_progress = 100
            await db.commit()

        except Exception:
            video.parse_status = "done"
            video.parse_progress = 100
            await db.commit()
            raise


# ═══════════════════════════════════════════════════════════
#  LLM 融合分品 (Step 3)
# ═══════════════════════════════════════════════════════════

async def _llm_fusion(
    asr_text: str,
    asr_sentences: list,
    vision_results: list,
    scene_changes: list[float],
    duration: float,
) -> list[dict]:
    """
    把 ASR 文稿 + 画面分析 + 场景切换点 一起喂给 DeepSeek，
    让它判断每个商品的起止时间和讲解脚本。
    """
    from backend.engine import llm

    # 构建画面时间线
    vision_timeline = ""
    for v in vision_results:
        minute = int(v["time_sec"] // 60)
        sec = int(v["time_sec"] % 60)
        vision_timeline += f"[{minute:02d}:{sec:02d}] 场景:{v.get('scene','?')} 商品:{v.get('product_hint','?')}\n"

    # 构建场景切换点
    scene_list = ", ".join(f"{t:.0f}s" for t in scene_changes[:20])

    prompt = f"""你是一个直播带货视频分析专家。请分析以下带货视频的信息，将视频切分为多个商品讲解片段。

【视频总时长】{duration:.0f}秒

【ASR 语音文稿】
{asr_text[:4000]}

【画面分析（每30秒一帧）】
{vision_timeline[:3000]}

【场景切换点】{scene_list}

请输出严格的 JSON 数组（不要加任何其他文字），将视频分解为 3-8 个商品讲解片段：

```json
[
  {{
    "start": 0,
    "end": 120,
    "product_hint": "法式碎花连衣裙",
    "script": "完整的讲解脚本文案（100-200字，带货风格亲切自然）"
  }},
  ...
]
```

规则：
1. start/end 用整数秒
2. 相邻片段无缝衔接
3. product_hint 要具体描述（颜色+品类+款式，便于后续匹配SKU）
4. script 根据 ASR 文稿内容写，保持原意但更流畅
5. 优先按商品切换点分段，辅助参考视觉画面的场景描述"""

    response = await llm.chat(prompt)

    # 解析 JSON
    try:
        json_str = response
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0]
        data = json.loads(json_str.strip())
        return data if isinstance(data, list) else [data]
    except (json.JSONDecodeError, IndexError):
        # 解析失败 → 兜底：整个视频作为一个商品
        return [{
            "start": 0,
            "end": duration,
            "product_hint": "未知商品",
            "script": asr_text[:200] or "暂无可解析的脚本文案",
        }]


# ═══════════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════════

def _cut_video(input_path: str, start: float, end: float, output_path: str):
    """FFmpeg 无损切割"""
    subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", input_path,
        "-c", "copy",
        output_path,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
