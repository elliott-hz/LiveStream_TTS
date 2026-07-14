"""
AI Script Generator — calls DeepSeek API to generate structured livestream scripts.

If the DeepSeek API key is not configured, falls back to a template-based
generation so the service is usable without external dependencies.
"""

import json
import time
from typing import Any

import httpx

from libs.common.errors import AppError, ErrorCode, Domain, internal
from libs.common.logging import get_logger

from ..config import ScriptConfig

logger = get_logger(__name__)

# ── Prompt template for DeepSeek ──

SYSTEM_PROMPT = """你是一个专业的直播带货脚本生成器。根据用户提供的商品信息、行业、风格和卖点，生成一个完整的直播带货脚本。

脚本必须是一个JSON数组，每个元素代表一个段落(section)，包含以下字段:
- order: 段落序号(从1开始)
- type: 段落类型，可选值为: opening(开场), product_intro(商品介绍), fabric_detail(材质/成分详解), size_guide(尺码指南), try_on(上身/实际展示), price_promo(价格促销), call_to_action(行动号召), closing(结尾), qa(问答互动)
- text: 段落文本内容(中文，口语化，适合直播)
- duration_estimate_ms: 预计时长(毫秒)
- emotion: 情感基调，可选: neutral, happy, excited, warm, sad, passionate, professional
- action: 动作，可选: wave_hand, point_product, show_detail, show_product_card, try_on_demo, taste_demo, compare_products
- show_product_card: 是否展示商品卡片(true/false)
- highlight_selling_point: 本段突出展示的核心卖点

要求:
1. 文本口语化、有感染力，符合直播场景
2. 段落之间衔接自然
3. 总时长控制在目标时长附近(正负10秒)
4. 每个段落突出至少一个卖点
5. 包含开场吸引注意、商品介绍、促销引导、行动号召、结尾等必备环节
6. 返回严格合法的JSON数组，不要包含任何其他文字"""

USER_PROMPT_TEMPLATE = """请为以下商品生成一个直播带货脚本:
- 商品名称: {product_name}
- 行业: {industry}
- 风格: {style}
- 核心卖点: {selling_points}
- 目标时长: {target_duration}秒
- 额外背景: {extra_context}

请返回JSON数组格式的脚本。"""

# ── Style display names ──

STYLE_NAMES = {
    "passionate": "激情带货",
    "professional": "专业讲解",
    "story": "故事营销",
    "comparison": "对比评测",
    "flash_sale": "限时秒杀",
}

_STYLE_DIRECTIONS = {
    "passionate": "语气热情、快节奏，使用大量感叹号和催促性语言",
    "professional": "语言理性专业，数据支撑，详细讲解产品参数",
    "story": "以故事叙述方式展开，有情节和情感起伏",
    "comparison": "与竞品对比，突出本产品的优势和性价比",
    "flash_sale": "强调限时、限量、紧迫感，节奏极快",
}

_SECTION_TEMPLATES = {
    "passionate": [
        {"type": "opening", "emotion": "excited", "action": "wave_hand", "show_product_card": True},
        {"type": "product_intro", "emotion": "happy", "action": "show_product_card", "show_product_card": True},
        {"type": "fabric_detail", "emotion": "professional", "action": "show_detail", "show_product_card": False},
        {"type": "size_guide", "emotion": "neutral", "action": "show_detail", "show_product_card": False},
        {"type": "try_on", "emotion": "excited", "action": "try_on_demo", "show_product_card": True},
        {"type": "price_promo", "emotion": "passionate", "action": "point_product", "show_product_card": True},
        {"type": "call_to_action", "emotion": "excited", "action": "point_product", "show_product_card": True},
        {"type": "closing", "emotion": "warm", "action": "wave_hand", "show_product_card": False},
    ],
    "professional": [
        {"type": "opening", "emotion": "neutral", "action": "wave_hand", "show_product_card": False},
        {"type": "product_intro", "emotion": "professional", "action": "show_product_card", "show_product_card": True},
        {"type": "fabric_detail", "emotion": "professional", "action": "show_detail", "show_product_card": False},
        {"type": "size_guide", "emotion": "neutral", "action": "show_detail", "show_product_card": False},
        {"type": "try_on", "emotion": "professional", "action": "try_on_demo", "show_product_card": True},
        {"type": "price_promo", "emotion": "neutral", "action": "show_detail", "show_product_card": True},
        {"type": "call_to_action", "emotion": "neutral", "action": "point_product", "show_product_card": True},
        {"type": "closing", "emotion": "neutral", "action": "wave_hand", "show_product_card": False},
    ],
    "story": [
        {"type": "opening", "emotion": "warm", "action": "wave_hand", "show_product_card": False},
        {"type": "product_intro", "emotion": "happy", "action": "show_product_card", "show_product_card": True},
        {"type": "fabric_detail", "emotion": "professional", "action": "show_detail", "show_product_card": False},
        {"type": "try_on", "emotion": "excited", "action": "try_on_demo", "show_product_card": True},
        {"type": "qa", "emotion": "warm", "action": "wave_hand", "show_product_card": False},
        {"type": "price_promo", "emotion": "happy", "action": "point_product", "show_product_card": True},
        {"type": "call_to_action", "emotion": "passionate", "action": "point_product", "show_product_card": True},
        {"type": "closing", "emotion": "warm", "action": "wave_hand", "show_product_card": False},
    ],
    "comparison": [
        {"type": "opening", "emotion": "excited", "action": "wave_hand", "show_product_card": False},
        {"type": "product_intro", "emotion": "professional", "action": "show_product_card", "show_product_card": True},
        {"type": "fabric_detail", "emotion": "professional", "action": "compare_products", "show_product_card": False},
        {"type": "try_on", "emotion": "happy", "action": "try_on_demo", "show_product_card": True},
        {"type": "price_promo", "emotion": "passionate", "action": "point_product", "show_product_card": True},
        {"type": "call_to_action", "emotion": "excited", "action": "point_product", "show_product_card": True},
        {"type": "closing", "emotion": "excited", "action": "wave_hand", "show_product_card": False},
    ],
    "flash_sale": [
        {"type": "opening", "emotion": "passionate", "action": "wave_hand", "show_product_card": True},
        {"type": "product_intro", "emotion": "excited", "action": "show_product_card", "show_product_card": True},
        {"type": "fabric_detail", "emotion": "professional", "action": "show_detail", "show_product_card": False},
        {"type": "try_on", "emotion": "excited", "action": "try_on_demo", "show_product_card": True},
        {"type": "price_promo", "emotion": "passionate", "action": "point_product", "show_product_card": True},
        {"type": "call_to_action", "emotion": "passionate", "action": "point_product", "show_product_card": True},
        {"type": "closing", "emotion": "excited", "action": "wave_hand", "show_product_card": False},
    ],
}

_TEXT_TEMPLATES_BY_TYPE = {
    "opening": [
        "欢迎各位来到直播间！今天给大家带来一款超级好物——{product_name}！",
        "家人们，今天给大家介绍一款宝藏产品——{product_name}，千万别错过！",
    ],
    "product_intro": [
        "首先来介绍一下这款{product_name}，它的核心卖点是{selling_points}。",
        "大家看这款{product_name}，第一眼就被它的{highlight}吸引了！",
    ],
    "fabric_detail": [
        "我们来仔细看看它的细节，{selling_points}，品质真的没话说。",
        "材质方面非常讲究，{selling_points}，用过的都知道好。",
    ],
    "size_guide": [
        "关于尺寸问题，这款产品提供了多个规格可选，大家可以根据自己的需求来选择。",
        "尺码方面，建议大家可以选大一码，穿着更舒适。",
    ],
    "try_on": [
        "我给大家实际展示一下效果，大家看看是不是跟说的一样好！",
        "来，直接上手上身试一下，效果立竿见影！",
    ],
    "price_promo": [
        "今天直播间专属价，比平时优惠了至少30%，只有今天有这个价格！",
        "限时特惠，今天下单立减，还赠送超值赠品，性价比拉满！",
    ],
    "call_to_action": [
        "库存有限，大家赶紧点击下方链接下单，手慢无！",
        "别犹豫了，这个价格只有今天有，错过就要等下次了！",
    ],
    "closing": [
        "感谢大家的支持，下单的朋友记得关注主播，后续还有更多好物推荐！",
        "今天的分享就到这里，有任何问题可以留言，我们下期再见！",
    ],
    "qa": [
        "大家有什么问题打在公屏上，我来一一为大家解答！",
        "我看到有朋友在问{question}，这个问题问得好，我来回答一下。",
    ],
}


class AIGenerator:
    """AI-powered script generation using DeepSeek API.

    Falls back to template-based generation when the API key is not set.
    """

    def __init__(self, config: ScriptConfig):
        self.config = config
        self.api_key = config.deepseek_api_key
        self.base_url = config.deepseek_base_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=60.0,
            )
        return self._client

    async def generate_script(
        self,
        product_name: str,
        industry: str,
        style: str,
        selling_points: list[str],
        target_duration_seconds: int = 120,
        extra_context: str = "",
    ) -> list[dict[str, Any]]:
        """Generate a structured script.

        Returns a list of section dicts. If the DeepSeek API is configured,
        it calls the API; otherwise it uses template-based generation.
        """
        if self.api_key:
            try:
                return await self._generate_via_api(
                    product_name, industry, style,
                    selling_points, target_duration_seconds, extra_context,
                )
            except Exception as e:
                logger.warning(
                    "ai_generator.api_fallback",
                    error=str(e),
                )
                # Fall through to template-based generation

        return self._generate_via_template(
            product_name, industry, style,
            selling_points, target_duration_seconds,
        )

    async def _generate_via_api(
        self,
        product_name: str,
        industry: str,
        style: str,
        selling_points: list[str],
        target_duration_seconds: int,
        extra_context: str,
    ) -> list[dict[str, Any]]:
        """Call DeepSeek API to generate script."""
        client = await self._get_client()

        style_direction = _STYLE_DIRECTIONS.get(style, "专业讲解")
        user_prompt = USER_PROMPT_TEMPLATE.format(
            product_name=product_name,
            industry=industry,
            style=style_direction,
            selling_points="、".join(selling_points) if selling_points else "暂无",
            target_duration=target_duration_seconds,
            extra_context=extra_context or "无",
        )

        response = await client.post(
            "/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.8,
                "max_tokens": 4096,
            },
        )

        if response.status_code != 200:
            raise AppError(
                ErrorCode.LLM_API_ERROR,
                f"DeepSeek API returned {response.status_code}: {response.text}",
                domain=Domain.SCRIPT,
            )

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Parse the JSON from the response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        sections = json.loads(content)
        if not isinstance(sections, list):
            raise AppError(
                ErrorCode.LLM_API_ERROR,
                "DeepSeek returned non-array response",
                domain=Domain.SCRIPT,
            )

        return sections

    def _generate_via_template(
        self,
        product_name: str,
        industry: str,
        style: str,
        selling_points: list[str],
        target_duration_seconds: int,
    ) -> list[dict[str, Any]]:
        """Fallback: generate script from built-in section templates."""
        if style not in _SECTION_TEMPLATES:
            style = "passionate"

        templates = _SECTION_TEMPLATES[style]
        total_duration_needed = target_duration_seconds * 1000
        num_sections = len(templates)

        # Distribute duration roughly evenly
        per_section_base = total_duration_needed // num_sections
        sections = []

        for i, tpl in enumerate(templates):
            sec_type = tpl["type"]
            texts = _TEXT_TEMPLATES_BY_TYPE.get(sec_type, [""])
            import random
            text = random.choice(texts).format(
                product_name=product_name,
                selling_points="、".join(selling_points[:2]) if selling_points else "",
                highlight=selling_points[0] if selling_points else "",
                question="产品质量怎么样",
            )

            # Vary duration a bit for realism
            duration_variance = int(per_section_base * 0.2)
            duration = per_section_base + random.randint(-duration_variance, duration_variance)
            if duration < 5000:
                duration = 5000

            sections.append({
                "order": i + 1,
                "type": sec_type,
                "text": text,
                "duration_estimate_ms": duration,
                "emotion": tpl["emotion"],
                "action": tpl["action"],
                "show_product_card": tpl["show_product_card"],
                "highlight_selling_point": selling_points[i % len(selling_points)] if selling_points else "",
            })

        return sections

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
