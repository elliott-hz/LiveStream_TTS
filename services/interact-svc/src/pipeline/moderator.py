"""
AI Text Moderator (Field Control) — Automated live room management.

Handles:
  - Scheduled comments: send product highlights on interval
  - Low-engagement prompts: "大家有什么问题可以打在公屏上哦~"
  - Negative comment handling: hide + send soothing reply
  - Product highlight: auto-send coupon when product card shown

Template-based for MVP. LLM-powered in Phase 2.
"""

from __future__ import annotations

import time
from typing import Any

from libs.common.logging import get_logger
from libs.proto.nlp.v1 import nlp_pb2

from ..models import ModeratorAction, ModeratorActionType

logger = get_logger(__name__)


class TextModerator:
    """AI Text Moderator — manages automated live room interactions."""

    # Template comments for different triggers
    _TEMPLATES: dict[str, list[str]] = {
        "interval": [
            "这款 {product_title} 真的太划算了，{product_highlight}，喜欢的宝宝们不要错过哦~",
            "再给大家介绍一下，{product_title} 限时特惠只要 {price} 元，赶紧下单吧！",
            "家人们，{product_title} 的库存不多了，抓紧时间上车！",
            "想要 {product_title} 的宝宝公屏扣1，主播给你详细讲解！",
        ],
        "low_engagement": [
            "大家有什么问题可以打在公屏上哦~",
            "有什么想了解的欢迎随时提问！",
            "家人们有什么疑问吗？主播在线答疑~",
            "想看哪个商品可以告诉我哦！",
        ],
        "negative_comment": [
            "亲亲别着急，有什么问题我可以帮您解决哦~",
            "感谢您的反馈，我们会持续改进的！",
        ],
        "product_highlight": [
            "为大家准备了专属优惠券，赶紧领取吧！",
            "限时优惠券已发放，领券下单更优惠！",
        ],
    }

    def __init__(self, session_id: str, config: Any | None = None) -> None:
        self._session_id = session_id
        self._config = config
        self._last_comment_time: float = 0.0
        self._comment_count: int = 0

    @property
    def comment_count(self) -> int:
        return self._comment_count

    async def on_interval(
        self,
        interval_seconds: float,
        product_context: dict[str, Any] | None = None,
    ) -> ModeratorAction:
        """Send a scheduled comment if interval has elapsed.

        Returns SEND_COMMENT action with a random product highlight.
        """
        now = time.monotonic()
        if (now - self._last_comment_time) < interval_seconds:
            return ModeratorAction(action_type=ModeratorActionType.NO_ACTION)

        self._last_comment_time = now
        templates = self._TEMPLATES["interval"]
        text = self._fill_template(
            templates[self._comment_count % len(templates)],
            product_context or {},
        )
        self._comment_count += 1

        logger.debug(
            "moderator.interval_comment",
            session_id=self._session_id,
            text=text,
        )
        return ModeratorAction(
            action_type=ModeratorActionType.SEND_COMMENT,
            comment_text=text,
        )

    async def on_low_engagement(
        self,
        current_interaction_rate: float,
        threshold: float = 0.1,
    ) -> ModeratorAction:
        """Trigger engagement prompt when interaction rate drops below threshold."""
        if current_interaction_rate >= threshold:
            return ModeratorAction(action_type=ModeratorActionType.NO_ACTION)

        templates = self._TEMPLATES["low_engagement"]
        text = templates[self._comment_count % len(templates)]
        self._comment_count += 1

        logger.info(
            "moderator.low_engagement",
            session_id=self._session_id,
            rate=current_interaction_rate,
            threshold=threshold,
            text=text,
        )
        return ModeratorAction(
            action_type=ModeratorActionType.SEND_COMMENT,
            comment_text=text,
        )

    async def on_negative_comment(
        self,
        comment_id: str,
        sentiment: int,
        intensity: float = 0.5,
    ) -> ModeratorAction:
        """Handle a negative/angry comment.

        Returns HIDE_COMMENT + SEND_COMMENT with soothing reply.
        """
        if sentiment not in (nlp_pb2.SENTIMENT_NEGATIVE, nlp_pb2.SENTIMENT_ANGRY):
            return ModeratorAction(action_type=ModeratorActionType.NO_ACTION)

        templates = self._TEMPLATES["negative_comment"]
        text = templates[self._comment_count % len(templates)]
        self._comment_count += 1

        logger.info(
            "moderator.negative_comment",
            session_id=self._session_id,
            comment_id=comment_id,
            sentiment=sentiment,
            intensity=intensity,
            reply_text=text,
        )
        return ModeratorAction(
            action_type=ModeratorActionType.HIDE_COMMENT,
            hide_comment_id=comment_id,
            comment_text=text,
        )

    async def on_product_highlight(
        self,
        product_id: str,
        coupon_id: str = "",
    ) -> ModeratorAction:
        """Auto-send coupon when a product card is shown."""
        if not coupon_id:
            return ModeratorAction(action_type=ModeratorActionType.NO_ACTION)

        templates = self._TEMPLATES["product_highlight"]
        text = templates[self._comment_count % len(templates)]
        self._comment_count += 1

        logger.info(
            "moderator.coupon_sent",
            session_id=self._session_id,
            product_id=product_id,
            coupon_id=coupon_id,
            text=text,
        )
        return ModeratorAction(
            action_type=ModeratorActionType.POP_COUPON,
            coupon_id=coupon_id,
            comment_text=text,
        )

    def _fill_template(self, template: str, context: dict[str, Any]) -> str:
        """Fill template placeholders with context values."""
        return template.format(
            product_title=context.get("title", "商品"),
            product_highlight=context.get("highlight", "超值好物"),
            price=context.get("price", "惊喜价"),
        )

    async def evaluate(
        self,
        trigger_event: str,
        context: dict[str, Any] | None = None,
    ) -> ModeratorAction:
        """Evaluate a trigger event and return the appropriate moderator action.

        This is the unified entry point used by the gRPC GetModeratorAction.
        """
        context = context or {}
        product_ctx = {
            "title": context.get("product_title", ""),
            "price": context.get("product_price", ""),
            "highlight": context.get("product_highlight", ""),
        }

        if trigger_event == "interval":
            interval = float(context.get("interval_seconds", 30))
            return await self.on_interval(interval, product_ctx)

        elif trigger_event == "low_engagement":
            rate = float(context.get("current_interaction_rate", 0))
            threshold = float(context.get("threshold", 0.1))
            return await self.on_low_engagement(rate, threshold)

        elif trigger_event == "negative_comment":
            comment_id = context.get("comment_id", "")
            sentiment = int(context.get("sentiment", 0))
            intensity = float(context.get("intensity", 0.5))
            return await self.on_negative_comment(comment_id, sentiment, intensity)

        elif trigger_event == "product_highlight":
            product_id = context.get("product_id", "")
            coupon_id = context.get("coupon_id", "")
            return await self.on_product_highlight(product_id, coupon_id)

        return ModeratorAction(action_type=ModeratorActionType.NO_ACTION)
