"""
NLP Service business logic orchestrator.

Coordinates intent classification, sentiment analysis, and sensitive word detection.
Serves as the single entry point for AnalyzeDanmaku operations.
"""

from __future__ import annotations

import time
from typing import Any

from libs.common.logging import get_logger

from src.classifiers.intent import IntentClassifier, IntentType, intent_classifier
from src.classifiers.sentiment import SentimentAnalyzer, SentimentType, sentiment_analyzer
from src.detectors.sensitive import SensitiveDetector, SensitiveResult, sensitive_detector

logger = get_logger(__name__)


class NLPService:
    """Orchestrator for all NLP operations."""

    def __init__(
        self,
        intent_clf: IntentClassifier | None = None,
        sentiment_clf: SentimentAnalyzer | None = None,
        detector: SensitiveDetector | None = None,
    ) -> None:
        self.intent_clf = intent_clf or intent_classifier
        self.sentiment_clf = sentiment_clf or sentiment_analyzer
        self.detector = detector or sensitive_detector

    async def analyze_danmaku(
        self,
        text: str,
        user_id: str = "",
        live_room_id: str = "",
        context_intent: IntentType | None = None,
    ) -> dict[str, Any]:
        """
        Analyze a single danmaku message.

        Returns a dict with:
            - intent: IntentType
            - intent_confidence: float
            - sentiment: SentimentType
            - sentiment_intensity: float
            - needs_reply: bool
            - reason: str
            - processing_ms: int
        """
        start = time.monotonic()

        if not text or not text.strip():
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return {
                "intent": IntentType.OTHER,
                "intent_confidence": 0.0,
                "sentiment": SentimentType.NEUTRAL,
                "sentiment_intensity": 0.0,
                "needs_reply": False,
                "reason": "Empty text",
                "processing_ms": elapsed_ms,
            }

        # Run intent classification
        intent_result = self.intent_clf.classify(text)

        # Boost confidence if context_intent matches
        if context_intent and context_intent != IntentType.UNSPECIFIED:
            if intent_result.intent == context_intent:
                intent_result.confidence = min(intent_result.confidence + 0.15, 1.0)
                intent_result.reason += " [confidence boosted by context]"

        # Run sentiment analysis
        sentiment_result = self.sentiment_clf.analyze(text)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return {
            "intent": intent_result.intent,
            "intent_confidence": intent_result.confidence,
            "sentiment": sentiment_result.sentiment,
            "sentiment_intensity": sentiment_result.intensity,
            "needs_reply": intent_result.needs_reply,
            "reason": intent_result.reason,
            "processing_ms": elapsed_ms,
        }

    async def batch_analyze_danmaku(
        self,
        items: list[dict[str, Any]],
        max_batch_size: int = 32,
    ) -> dict[str, Any]:
        """
        Batch analyze multiple danmaku messages.

        Args:
            items: List of dicts with keys: text, user_id, live_room_id, context_intent
            max_batch_size: Maximum number of items to process (default 32)

        Returns:
            Dict with results list, total count, needs_reply_count.
        """
        actual_batch = items[:max_batch_size]
        results = []

        for item in actual_batch:
            context_intent = item.get("context_intent", None)
            if isinstance(context_intent, int):
                context_intent = IntentType(context_intent) if context_intent != 0 else None

            result = await self.analyze_danmaku(
                text=item.get("text", ""),
                user_id=item.get("user_id", ""),
                live_room_id=item.get("live_room_id", ""),
                context_intent=context_intent,
            )
            results.append(result)

        needs_reply_count = sum(1 for r in results if r["needs_reply"])

        return {
            "results": results,
            "total": len(results),
            "needs_reply_count": needs_reply_count,
        }

    async def check_sensitive(
        self,
        text: str,
        context: str = "danmaku",
    ) -> SensitiveResult:
        """
        Check text for sensitive content.

        Args:
            text: The text to check.
            context: Context of the text ("script", "danmaku", "avatar_name").

        Returns:
            SensitiveResult with matches.
        """
        return self.detector.check(text, context)

    async def extract_entities(
        self,
        text: str,
        entity_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract named entities from text.

        This is a placeholder implementation using simple pattern matching.
        Replace with a proper NER model in production.
        """
        import re

        entities: list[dict[str, Any]] = []
        entity_types = entity_types or ["product", "price", "brand", "size"]

        if "price" in entity_types:
            # Extract prices: ￥199, 199元, $19.99
            price_patterns = [
                re.compile(r"[￥¥](\d+(?:\.\d+)?)"),
                re.compile(r"(\d+(?:\.\d+)?)元"),
                re.compile(r"\$(\d+(?:\.\d+)?)"),
            ]
            for pat in price_patterns:
                for m in pat.finditer(text):
                    entities.append({
                        "text": m.group(0),
                        "type": "price",
                        "start_pos": m.start(),
                        "end_pos": m.end(),
                        "confidence": 0.9,
                    })

        if "size" in entity_types:
            # Extract sizes: XL, XXL, 160/84A, 42码
            size_patterns = [
                re.compile(r"\b(X{0,3}[SLM])\b"),
                re.compile(r"(\d+/\d+[A-Z]?)"),
                re.compile(r"(\d+)\s*(码|号)"),
            ]
            for pat in size_patterns:
                for m in pat.finditer(text):
                    entities.append({
                        "text": m.group(0),
                        "type": "size",
                        "start_pos": m.start(),
                        "end_pos": m.end(),
                        "confidence": 0.7,
                    })

        if "product" in entity_types:
            # Placeholder: cannot extract product names without a proper NER model
            pass

        if "brand" in entity_types:
            # Placeholder: brand extraction needs a brand dictionary or NER
            pass

        return entities

    async def rewrite_text(
        self,
        text: str,
        style: str = "live_comment",
        context: str = "",
    ) -> dict[str, str]:
        """
        Rewrite text in a given style.

        This is a placeholder — replace with LLM-based rewriting in production.

        Args:
            text: The original text.
            style: Target style ("live_comment", "product_script", "field_control").
            context: Additional context (product info, live room theme).

        Returns:
            Dict with rewritten_text key.
        """
        # Simple rule-based rewriting (placeholder)
        if not text or not text.strip():
            return {"rewritten_text": text}

        # For now, return the original text with a note
        # In production, this would call an LLM
        rewritten = text.strip()

        if style == "live_comment":
            # Ensure it reads like a live comment
            if not rewritten.endswith(("!", "！", "?", "？", ".", "。")):
                rewritten += "！"
        elif style == "product_script":
            # Make it sound like a promotional script
            prefixes = ["来看看这款", "给大家推荐"]
            import random
            if not any(rewritten.startswith(p) for p in prefixes):
                rewritten = f"{random.choice(prefixes)}{rewritten}"
        elif style == "field_control":
            # Field control style: shorter, more urgent
            if len(rewritten) > 30:
                rewritten = rewritten[:27] + "..."

        return {"rewritten_text": rewritten}


# Singleton instance
nlp_service = NLPService()
