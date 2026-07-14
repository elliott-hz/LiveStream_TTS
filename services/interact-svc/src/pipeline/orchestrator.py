"""
Prompt Orchestrator — Assembles the LLM prompt for reply generation.

Builds prompt from:
  - System prompt (anchor persona + banned words + reply rules)
  - Product context (current product info)
  - RAG context (knowledge base retrieval — mock for now)
  - User profile (from profile_lookup)
  - Live room context (current session stats)
  - The user's danmaku text

Returns assembled prompt that would feed to the LLM in production.
"""

from __future__ import annotations

from typing import Any

from libs.common.logging import get_logger

from ..models import Session, DanmakuEvent

logger = get_logger(__name__)


class PromptOrchestrator:
    """Assembles structured prompts for LLM-based reply generation."""

    def __init__(self) -> None:
        # RAG retrieval client — mocked for now
        self._rag_client = None

    async def assemble(
        self,
        session: Session,
        event: DanmakuEvent,
        product_context: dict[str, Any] | None = None,
        rag_results: list[dict[str, Any]] | None = None,
    ) -> str:
        """Assemble a full prompt from all context sources.

        In production, this would construct a message list for the LLM API.
        For MVP, returns a plain-text prompt string.
        """
        system = self._build_system_prompt(session)
        product_info = self._format_product_context(product_context or self._default_product_context())
        rag = self._format_rag_context(rag_results or [])
        profile = self._format_user_profile(event.user_profile)
        live_ctx = self._format_live_context(session)

        prompt = f"""{system}

{product_info}

{rag}

{profile}

{live_ctx}

用户消息: {event.text}

请根据以上上下文，生成适合直播场景的回复。
回复要求:
1. 简短有力 (不超过40字)
2. 符合主播人设
3. 如适用，推荐当前商品
4. 禁止使用违禁词
"""
        logger.debug(
            "orchestrator.prompt_assembled",
            session_id=session.session_id,
            prompt_length=len(prompt),
        )
        return prompt

    def _build_system_prompt(self, session: Session) -> str:
        """Build the system prompt section."""
        cfg = session.config
        parts = [f"【系统设定】{cfg.system_prompt}"]

        if cfg.banned_words:
            banned = "、".join(cfg.banned_words)
            parts.append(f"【违禁词】以下词语严禁出现在回复中: {banned}")

        parts.append("【回复规则】")
        parts.append("- 回复长度不超过40字")
        parts.append("- 语气热情亲切，符合带货主播人设")
        parts.append("- 如用户提及竞品，用产品优势礼貌回应")
        parts.append("- 不要主动承认是AI")

        return "\n".join(parts)

    def _format_product_context(self, product: dict[str, Any]) -> str:
        """Format product information for the prompt."""
        title = product.get("title", "未知商品")
        price = product.get("price", "")
        highlight = product.get("highlight", "")
        selling_points = product.get("selling_points", [])

        lines = ["【当前商品】"]
        lines.append(f"商品名称: {title}")
        if price:
            lines.append(f"价格: {price}元")
        if highlight:
            lines.append(f"核心卖点: {highlight}")
        if selling_points:
            for i, sp in enumerate(selling_points, 1):
                lines.append(f"卖点{i}: {sp}")

        return "\n".join(lines)

    def _format_rag_context(self, rag_results: list[dict[str, Any]]) -> str:
        """Format knowledge base retrieval results."""
        if not rag_results:
            return "【知识库】暂无相关知识"

        lines = ["【相关知识库】"]
        for i, doc in enumerate(rag_results, 1):
            title = doc.get("title", f"知识{i}")
            content = doc.get("content", "")
            lines.append(f"{i}. {title}: {content[:200]}")

        return "\n".join(lines)

    def _format_user_profile(self, profile: dict[str, Any]) -> str:
        """Format user profile for personalized response."""
        lines = ["【用户画像】"]
        if profile.get("is_vip"):
            lines.append("- 该用户是VIP会员，请给予尊贵待遇")
        if profile.get("is_new"):
            lines.append("- 该用户是首次进入直播间，请热情欢迎")
        if profile.get("purchase_count", 0) > 0:
            lines.append(f"- 该用户已购买 {profile['purchase_count']} 次，是老顾客")
        tags = profile.get("tags", [])
        if tags:
            lines.append(f"- 标签: {', '.join(tags)}")

        return "\n".join(lines)

    def _format_live_context(self, session: Session) -> str:
        """Format live room context."""
        stats = session.stats
        lines = ["【直播上下文】"]
        lines.append(f"当前直播间: {session.live_room_id}")
        lines.append(f"已接收弹幕: {stats.total_danmaku}条")
        if stats.ignored_messages > 0:
            lines.append(f"已过滤低质弹幕: {stats.ignored_messages}条")

        return "\n".join(lines)

    @staticmethod
    def _default_product_context() -> dict[str, Any]:
        """Default/mock product context for development."""
        return {
            "title": "超润保湿精华液",
            "price": "99.9",
            "highlight": "三重玻尿酸补水, 24小时长效锁水, 敏感肌可用",
            "selling_points": [
                "三重玻尿酸深层补水",
                "24小时锁水保湿",
                "敏感肌适用",
                "清爽不黏腻",
            ],
        }
