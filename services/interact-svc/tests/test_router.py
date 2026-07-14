"""
Tests for the ChannelRouter — the key routing component.

Tests all routing rules:
  - High intent -> VOICE
  - Low confidence -> IGNORE
  - Greeting/Praise -> TEXT
  - Compare -> BOTH
  - VIP upgrade: TEXT -> VOICE
  - New user upgrade: TEXT -> VOICE
  - Negative sentiment escalation
  - OTHER intent with low confidence -> IGNORE
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

from src.pipeline.router import ChannelRouter
from src.models import Channel


class TestChannelRouter:
    """Comprehensive tests for channel routing logic."""

    @pytest.fixture
    def router(self) -> ChannelRouter:
        return ChannelRouter()

    # ── High-intent routing ──

    @pytest.mark.parametrize(
        "intent",
        [
            nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT,
            nlp_pb2.INTENT_CATEGORY_QUESTION,
            nlp_pb2.INTENT_CATEGORY_REQUEST_DEMO,
            nlp_pb2.INTENT_CATEGORY_BARGAIN,
            nlp_pb2.INTENT_CATEGORY_COMPLAINT,
        ],
    )
    def test_high_intent_routes_to_voice(self, router: ChannelRouter, intent: int) -> None:
        """Purchase intent, questions, demos, bargains, complaints → VOICE."""
        result = router.route(intent=intent, confidence=0.9)
        assert result.channel == Channel.VOICE, (
            f"Intent {nlp_pb2.IntentCategory.Name(intent)} should route to VOICE, "
            f"got {Channel(result.channel).name}"
        )

    # ── Text intents ──

    @pytest.mark.parametrize(
        "intent",
        [
            nlp_pb2.INTENT_CATEGORY_GREETING,
            nlp_pb2.INTENT_CATEGORY_PRAISE,
        ],
    )
    def test_social_intent_routes_to_text(self, router: ChannelRouter, intent: int) -> None:
        """Greetings and praise → TEXT."""
        result = router.route(intent=intent, confidence=0.9)
        assert result.channel == Channel.TEXT

    # ── Compare → BOTH ──

    def test_compare_routes_to_both(self, router: ChannelRouter) -> None:
        """Comparison intent → BOTH (voice + product card)."""
        result = router.route(intent=nlp_pb2.INTENT_CATEGORY_COMPARE, confidence=0.9)
        assert result.channel == Channel.BOTH

    # ── Low confidence → IGNORE ──

    def test_low_confidence_routes_to_ignore(self, router: ChannelRouter) -> None:
        """Confidence below threshold → IGNORE."""
        result = router.route(intent=nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT, confidence=0.2)
        assert result.channel == Channel.IGNORE

    def test_other_intent_low_confidence_ignored(self, router: ChannelRouter) -> None:
        """OTHER intent with low confidence → IGNORE."""
        result = router.route(intent=nlp_pb2.INTENT_CATEGORY_OTHER, confidence=0.15)
        assert result.channel == Channel.IGNORE

    def test_custom_threshold(self, router: ChannelRouter) -> None:
        """Custom reply threshold should be respected."""
        result = router.route(
            intent=nlp_pb2.INTENT_CATEGORY_QUESTION,
            confidence=0.5,
            reply_threshold=0.8,
        )
        assert result.channel == Channel.IGNORE

    # ── VIP upgrades ──

    def test_vip_upgrades_text_to_voice(self, router: ChannelRouter) -> None:
        """VIP user: GREETING should upgrade from TEXT to VOICE."""
        result = router.route(
            intent=nlp_pb2.INTENT_CATEGORY_GREETING,
            confidence=0.9,
            user_profile={"is_vip": True, "is_new": False},
        )
        assert result.channel == Channel.VOICE, f"VIP greeting should be VOICE, got {Channel(result.channel).name}"
        assert "VIP" in result.reason

    def test_vip_stays_voice_for_high_intent(self, router: ChannelRouter) -> None:
        """VIP user with purchase intent stays VOICE."""
        result = router.route(
            intent=nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT,
            confidence=0.9,
            user_profile={"is_vip": True},
        )
        assert result.channel == Channel.VOICE

    # ── New user upgrades ──

    def test_new_user_upgrades_text_to_voice(self, router: ChannelRouter) -> None:
        """New user: PRAISE should upgrade from TEXT to VOICE."""
        result = router.route(
            intent=nlp_pb2.INTENT_CATEGORY_PRAISE,
            confidence=0.9,
            user_profile={"is_new": True, "is_vip": False},
        )
        assert result.channel == Channel.VOICE
        assert "New user" in result.reason

    def test_new_user_ignore_stays_ignore(self, router: ChannelRouter) -> None:
        """New user with low confidence stays IGNORE (no upgrade from IGNORE)."""
        result = router.route(
            intent=nlp_pb2.INTENT_CATEGORY_OTHER,
            confidence=0.1,
            user_profile={"is_new": True},
        )
        assert result.channel == Channel.IGNORE

    # ── Negative sentiment escalation ──

    def test_negative_sentiment_escalates_to_voice(self, router: ChannelRouter) -> None:
        """GREETING (normally TEXT) with NEGATIVE sentiment → VOICE."""
        result = router.route(
            intent=nlp_pb2.INTENT_CATEGORY_GREETING,
            confidence=0.9,
            sentiment=nlp_pb2.SENTIMENT_NEGATIVE,
            user_profile={},
        )
        assert result.channel == Channel.VOICE, "Negative greeting should escalate to VOICE"
        assert "Negative sentiment" in result.reason

    def test_angry_sentiment_escalates_ignore(self, router: ChannelRouter) -> None:
        """OTHER intent with ANGRY sentiment should escalate to VOICE."""
        result = router.route(
            intent=nlp_pb2.INTENT_CATEGORY_OTHER,
            confidence=0.5,  # Above threshold
            sentiment=nlp_pb2.SENTIMENT_ANGRY,
            user_profile={},
        )
        assert result.channel == Channel.VOICE

    # ── Normal user no upgrade ──

    def test_normal_user_no_upgrade(self, router: ChannelRouter) -> None:
        """Normal (non-VIP, non-new) greeting stays TEXT."""
        result = router.route(
            intent=nlp_pb2.INTENT_CATEGORY_GREETING,
            confidence=0.9,
            user_profile={"is_vip": False, "is_new": False},
        )
        assert result.channel == Channel.TEXT

    # ── Routing stats ──

    def test_routing_stats_tracked(self, router: ChannelRouter) -> None:
        """Routing statistics should be tracked correctly."""
        router.route(intent=nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT, confidence=0.9)
        router.route(intent=nlp_pb2.INTENT_CATEGORY_GREETING, confidence=0.9)
        router.route(intent=nlp_pb2.INTENT_CATEGORY_OTHER, confidence=0.1)
        router.route(
            intent=nlp_pb2.INTENT_CATEGORY_GREETING,
            confidence=0.9,
            user_profile={"is_vip": True},
        )

        stats = router.stats
        assert stats["voice"] >= 1
        assert stats["text"] >= 1
        assert stats["ignore"] >= 1
        assert stats["upgraded_vip"] >= 1
