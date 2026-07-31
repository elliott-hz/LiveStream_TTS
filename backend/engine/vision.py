"""
DashScope Qwen-VL-Max — 关键帧视觉分析
https://help.aliyun.com/zh/model-studio/qwen-vl

分析每张关键帧: 描述画面中的商品、人物动作、文字信息。
"""

import base64
import asyncio
import httpx
from backend.config import settings

QWEN_VL_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


async def analyze_keyframes(keyframe_paths: list[str]) -> list[dict]:
    """
    逐张分析关键帧，返回每帧的描述。

    返回:
    [
      {"time_sec": 0, "frame": "/path/frame_0000.jpg",
       "scene": "主播展示商品", "product_hint": "碎花连衣裙",
       "details": "主播手持衣服展示，镜头近景，背景为直播布景"},
      ...
    ]
    """
    if settings.mock_external_api:
        return _mock_result(keyframe_paths)

    headers = {
        "Authorization": f"Bearer {settings.aliyun_access_key}",
        "Content-Type": "application/json",
    }

    # 并发分析，限制并发数
    sem = asyncio.Semaphore(5)
    tasks = [_analyze_one(path, idx, headers, sem) for idx, path in enumerate(keyframe_paths)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    parsed = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            parsed.append({"time_sec": i * 30, "frame": keyframe_paths[i],
                           "scene": "未知", "product_hint": "", "details": str(r)})
        else:
            parsed.append(r)
    return parsed


async def _analyze_one(path: str, idx: int, headers: dict, sem: asyncio.Semaphore) -> dict:
    """分析单张关键帧"""
    async with sem:
        b64 = _encode_image(path)
        if not b64:
            return {"time_sec": idx * 30, "frame": path, "scene": "编码失败", "product_hint": "", "details": ""}

        prompt = """你是一个直播带货视频分析专家。请分析这张直播截图：

1. 主播在做什么？（展示商品 / 讲解细节 / 互动聊天 / 切换商品 / 展示价格）
2. 画面中的商品是什么？（用一句话描述：颜色、品类、款式）
3. 画面中有什么明显的文字信息？（价格标签、尺码表、品牌logo等）

用简洁中文回复，格式:
场景: xxx
商品: xxx
文字: xxx"""

        payload = {
            "model": "qwen-vl-max",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 200,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(QWEN_VL_URL, headers=headers, json=payload)
            data = resp.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 解析回复
        scene, product, text_info = "", "", ""
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("场景"):
                scene = line.replace("场景:", "").replace("场景：", "").strip()
            elif line.startswith("商品"):
                product = line.replace("商品:", "").replace("商品：", "").strip()
            elif line.startswith("文字"):
                text_info = line.replace("文字:", "").replace("文字：", "").strip()

        return {
            "time_sec": idx * 30,
            "frame": path,
            "scene": scene,
            "product_hint": product,
            "details": text_info,
        }


def _encode_image(path: str) -> str | None:
    """读取图片并 base64 编码"""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _mock_result(keyframe_paths: list[str]) -> list[dict]:
    return [
        {"time_sec": i * 30, "frame": p, "scene": "展示商品", "product_hint": "服装", "details": ""}
        for i, p in enumerate(keyframe_paths)
    ]
