"""
Tests for the TextModerator — AI text field control.

Tests all moderator trigger events:
  - on_interval: scheduled comments
  - on_low_engagement: engagement prompts
  - on_negative_comment: negative comment handling
  - on_product_highlight: coupon on product card
"""

from __future__ import annotations

import sys
from pathlib import Path

# Monorepo path setup
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LIBS_PROTO = _REPO_ROOT / "libs" / "proto"
for p in [str(_REPO_ROOT), str(_LIBS_PROTO)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from libs.proto.nlp.v1 import nlp_pb2

from src.pipeline.moderator import TextModerator
from src.models import ModeratorActionType


class TestTextModerator:
    """Tests for the AI text moderator."""

    @pytest.fixture
    def moderator(self) -> TextModerator:
        return TextModerator(session_id="test_ses_001")

    @pytest.fixture
    def product_context(self) -> dict:
        return {
            "title": "超润保湿精华液",
            "price": "99.9",
            "highlight": "三重玻尿酸补水",
        }

    # ── Interval comments ──

    @pytest.mark.asyncio
    async def test_interval_returns_action(self, moderator: TextModerator) -> None:
        """on_interval should return a SEND_COMMENT action after interval elapses."""
        action = await moderator.on_interval(interval_seconds=0)  # Immediately
        assert action.action_type == ModeratorActionType.SEND_COMMENT
        assert len(action.comment_text) > 0
        assert "{" not in action.comment_text  # Template should be filled

    @pytest.mark.asyncio
    async def test_interval_rate_limited(self, moderator: TextModerator) -> None:
        """on_interval should return NO_ACTION if interval hasn't elapsed."""
        # First call returns action
        await moderator.on_interval(interval_seconds=10)

        # Second call immediately after should be rate-limited
        action = await moderator.on_interval(interval_seconds=10)
        assert action.action_type == ModeratorActionType.NO_ACTION

    @pytest.mark.asyncio
    async def test_interval_fills_product_context(self, moderator: TextModerator, product_context: dict) -> None:
        """on_interval should fill template with product context."""
        action = await moderator.on_interval(
            interval_seconds=0,
            product_context=product_context,
        )
        assert action.action_type == ModeratorActionType.SEND_COMMENT
        assert "超润保湿精华液" in action.comment_text or "99.9" in action.comment_text

    @pytest.mark.asyncio
    async def test_interval_rotates_templates(self, moderator: TextModerator) -> None:
        """on_interval should rotate through available templates."""
        texts = set()
        for _ in range(4):
            action = await moderator.on_interval(interval_seconds=0)
            texts.add(action.comment_text)
        assert len(texts) >= 2, "Should use multiple templates"

    # ── Low engagement ──

    @pytest.mark.asyncio
    async def test_low_engagement_triggers_prompt(self, moderator: TextModerator) -> None:
        """on_low_engagement should send a prompt when rate is below threshold."""
        action = await moderator.on_low_engagement(
            current_interaction_rate=0.05,
            threshold=0.1,
        )
        assert action.action_type == ModeratorActionType.SEND_COMMENT
        assert len(action.comment_text) > 0

    @pytest.mark.asyncio
    async def test_low_engagement_no_action_above_threshold(
        self, moderator: TextModerator
    ) -> None:
        """on_low_engagement should return NO_ACTION when rate is sufficient."""
        action = await moderator.on_low_engagement(
            current_interaction_rate=0.5,
            threshold=0.1,
        )
        assert action.action_type == ModeratorActionType.NO_ACTION

    # ── Negative comments ──

    @pytest.mark.asyncio
    async def test_negative_comment_hides_and_soothes(self, moderator: TextModerator) -> None:
        """Negative comment → HIDE_COMMENT with soothing reply."""
        action = await moderator.on_negative_comment(
            comment_id="cmt_001",
            sentiment=nlp_pb2.SENTIMENT_NEGATIVE,
            intensity=0.8,
        )
        assert action.action_type == ModeratorActionType.HIDE_COMMENT
        assert action.hide_comment_id == "cmt_001"
        assert len(action.comment_text) > 0

    @pytest.mark.asyncio
    async def test_angry_comment_hides_and_soothes(self, moderator: TextModerator) -> None:
        """Angry sentiment → HIDE_COMMENT with soothing reply."""
        action = await moderator.on_negative_comment(
            comment_id="cmt_002",
            sentiment=nlp_pb2.SENTIMENT_ANGRY,
            intensity=0.9,
        )
        assert action.action_type == ModeratorActionType.HIDE_COMMENT

    @pytest.mark.asyncio
    async def test_positive_comment_not_hidden(self, moderator: TextModerator) -> None:
        """Positive comment → NO_ACTION (no moderation needed)."""
        action = await moderator.on_negative_comment(
            comment_id="cmt_003",
            sentiment=nlp_pb2.SENTIMENT_POSITIVE,
        )
        assert action.action_type == ModeratorActionType.NO_ACTION

    # ── Product highlight → coupon ──

    @pytest.mark.asyncio
    async def test_product_highlight_sends_coupon(self, moderator: TextModerator) -> None:
        """Product highlight with coupon → POP_COUPON."""
        action = await moderator.on_product_highlight(
            product_id="prod_001",
            coupon_id="coup_001",
        )
        assert action.action_type == ModeratorActionType.POP_COUPON
        assert action.coupon_id == "coup_001"

    @pytest.mark.asyncio
    async def test_product_highlight_no_coupon_no_action(self, moderator: TextModerator) -> None:
        """Product highlight without coupon → NO_ACTION."""
        action = await moderator.on_product_highlight(product_id="prod_001", coupon_id="")
        assert action.action_type == ModeratorActionType.NO_ACTION

    # ── Unified evaluate ──

    @pytest.mark.asyncio
    async def test_evaluate_interval(self, moderator: TextModerator) -> None:
        """evaluate() with 'interval' trigger should work."""
        action = await moderator.evaluate("interval", {"interval_seconds": "0"})
        assert action.action_type in (
            ModeratorActionType.SEND_COMMENT,
            ModeratorActionType.NO_ACTION,
        )

    @pytest.mark.asyncio
    async def test_evaluate_negative_comment(self, moderator: TextModerator) -> None:
        """evaluate() with 'negative_comment' trigger should work."""
        action = await moderator.evaluate(
            "negative_comment",
            {
                "comment_id": "cmt_001",
                "sentiment": str(nlp_pb2.SENTIMENT_NEGATIVE),
                "intensity": "0.8",
            },
        )
        assert action.action_type == ModeratorActionType.HIDE_COMMENT

    @pytest.mark.asyncio
    async def test_evaluate_unknown_trigger(self, moderator: TextModerator) -> None:
        """evaluate() with unknown trigger → NO_ACTION."""
        action = await moderator.evaluate("unknown_event")
        assert action.action_type == ModeratorActionType.NO_ACTION

    # ── Comment count tracking ──

    @pytest.mark.asyncio
    async def test_comment_count_increments(self, moderator: TextModerator) -> None:
        """Comment count should increment with each action."""
        await moderator.on_interval(interval_seconds=0)
        assert moderator.comment_count == 1

        await moderator.on_interval(interval_seconds=0)
        assert moderator.comment_count == 2
