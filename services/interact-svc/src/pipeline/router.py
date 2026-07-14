"""
Channel Router — THE KEY COMPONENT of the interaction pipeline.

Routes each danmaku to the right output channel based on:
  - Intent category (from NLP)
  - Intent confidence score
  - Sentiment
  - User profile (VIP, new user)
  - Session config (reply threshold)

Routing rules:
  PURCHASE_INTENT, QUESTION, REQUEST_DEMO → VOICE (high value)
  BARGAIN, COMPLAINT → VOICE (need human-like handling)
  GREETING, PRAISE → TEXT (simple text reply enough)
  COMPARE → BOTH (voice + product card)
  Low confidence (< threshold) or OTHER → IGNORE
  VIP users: upgrade TEXT → VOICE
  New users (first visit): upgrade to VOICE for engagement
"""

from __future__ import annotations

import math
from typing import Any

from libs.common.logging import get_logger
from libs.proto.nlp.v1 import nlp_pb2

from ..models import Channel, DanmakuEvent, RouteResult

logger = get_logger(__name__)

# Intent categories for voice routing (high-value interactions)
_VOICE_INTENTS = frozenset({
    nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT,
    nlp_pb2.INTENT_CATEGORY_QUESTION,
    nlp_pb2.INTENT_CATEGORY_REQUEST_DEMO,
    nlp_pb2.INTENT_CATEGORY_BARGAIN,
    nlp_pb2.INTENT_CATEGORY_COMPLAINT,
})

# Intent categories for text-only routing
_TEXT_INTENTS = frozenset({
    nlp_pb2.INTENT_CATEGORY_GREETING,
    nlp_pb2.INTENT_CATEGORY_PRAISE,
})

# Intent categories that warrant both voice + product card
_BOTH_INTENTS = frozenset({
    nlp_pb2.INTENT_CATEGORY_COMPARE,
})


class ChannelRouter:
    """Routes danmaku to output channels based on intent, confidence, and user profile."""

    def __init__(self) -> None:
        self._routing_count: dict[str, int] = {
            "voice": 0,
            "text": 0,
            "both": 0,
            "ignore": 0,
            "upgraded_vip": 0,
            "upgraded_new_user": 0,
        }

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._routing_count)

    def route(
        self,
        intent: int,
        confidence: float,
        sentiment: int = 0,
        user_profile: dict[str, Any] | None = None,
        reply_threshold: float = 0.3,
    ) -> RouteResult:
        """Determine the output channel for a danmaku.

        Args:
            intent: nlp.v1.IntentCategory enum value
            confidence: Intent classification confidence (0.0 - 1.0)
            sentiment: nlp.v1.Sentiment enum value (optional)
            user_profile: User profile dict with is_vip, is_new, etc.
            reply_threshold: Minimum confidence to consider replying

        Returns:
            RouteResult with channel and reason
        """
        user_profile = user_profile or {}
        is_vip = user_profile.get("is_vip", False)
        is_new = user_profile.get("is_new", False)

        # Step 1: Check if confidence meets minimum threshold
        if confidence < reply_threshold:
            self._routing_count["ignore"] += 1
            return RouteResult(
                channel=Channel.IGNORE,
                reason=f"Confidence {confidence:.2f} below threshold {reply_threshold:.2f}",
            )

        # Step 2: Route by intent
        base_channel = self._route_by_intent(intent, sentiment)

        # Step 3: Apply upgrade rules
        upgraded = False
        if base_channel == Channel.TEXT and is_vip:
            base_channel = Channel.VOICE
            upgraded = True
            self._routing_count["upgraded_vip"] += 1
            reason = "VIP upgrade: TEXT → VOICE"
        elif base_channel == Channel.TEXT and is_new:
            base_channel = Channel.VOICE
            upgraded = True
            self._routing_count["upgraded_new_user"] += 1
            reason = "New user upgrade: TEXT → VOICE"
        elif base_channel == Channel.VOICE and is_vip:
            reason = "VIP deserves voice response"
        else:
            reason = self._reason_for_channel(base_channel, intent)

        # Step 4: Handle negative sentiment for voice routing
        if not upgraded and sentiment in (
            nlp_pb2.SENTIMENT_NEGATIVE,
            nlp_pb2.SENTIMENT_ANGRY,
        ):
            if base_channel in (Channel.TEXT, Channel.IGNORE):
                base_channel = Channel.VOICE
                reason = "Negative sentiment escalation: → VOICE"

        self._routing_count["voice" if base_channel == Channel.VOICE else
                            "text" if base_channel == Channel.TEXT else
                            "both" if base_channel == Channel.BOTH else
                            "ignore"] += 1

        return RouteResult(channel=base_channel, reason=reason)

    def route_danmaku(self, event: DanmakuEvent, reply_threshold: float = 0.3) -> RouteResult:
        """Convenience: route a DanmakuEvent directly."""
        return self.route(
            intent=event.intent,
            confidence=event.intent_confidence,
            sentiment=event.sentiment,
            user_profile=event.user_profile,
            reply_threshold=reply_threshold,
        )

    def _route_by_intent(self, intent: int, sentiment: int = 0) -> Channel:
        """Base routing by intent category (no upgrades)."""
        if intent in _VOICE_INTENTS:
            return Channel.VOICE

        if intent in _TEXT_INTENTS:
            return Channel.TEXT

        if intent in _BOTH_INTENTS:
            return Channel.BOTH

        # Handle OTHER and unknown intents
        return Channel.IGNORE

    def _reason_for_channel(self, channel: Channel, intent: int) -> str:
        """Generate a human-readable reason for the routing decision."""
        intent_name = nlp_pb2.IntentCategory.Name(intent) if intent else "UNKNOWN"
        channel_name = Channel(channel).name if channel else "UNKNOWN"

        reasons = {
            Channel.VOICE: f"Intent {intent_name} → {channel_name} (high value)",
            Channel.TEXT: f"Intent {intent_name} → {channel_name} (simple reply)",
            Channel.BOTH: f"Intent {intent_name} → {channel_name} (comparison)",
            Channel.IGNORE: f"Intent {intent_name} → {channel_name} (no reply needed)",
        }
        return reasons.get(Channel(channel), f"Routed to {channel_name}")
