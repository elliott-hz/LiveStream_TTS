"""
5-class sentiment analyzer using keyword-based rule matching.

Sentiment classes (per proto nlp.v1.Sentiment):
  1  POSITIVE   — positive / favorable
  2  NEGATIVE   — negative / unfavorable
  3  NEUTRAL    — neutral (fallback)
  4  ANGRY      — angry / furious
  5  EXCITED    — excited / enthusiastic
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Pattern

from libs.common.logging import get_logger

logger = get_logger(__name__)


class SentimentType(IntEnum):
    """Internal sentiment enum mapping 1:1 to proto Sentiment values."""
    UNSPECIFIED = 0
    POSITIVE = 1
    NEGATIVE = 2
    NEUTRAL = 3
    ANGRY = 4
    EXCITED = 5


@dataclass
class SentimentResult:
    """Result of sentiment analysis."""
    sentiment: SentimentType
    intensity: float       # 0.0–1.0
    matched_keywords: list[str] | None = None
    reason: str = ""


class SentimentAnalyzer:
    """Rule-based sentiment analyzer covering 5 sentiment classes."""

    # ── Positive keywords ──
    POSITIVE_KEYWORDS: list[str] = [
        "好", "棒", "喜欢", "不错", "满意", "支持", "给力", "赞", "优秀",
        "完美", "绝了", "惊艳", "漂亮", "好看", "好用", "好听", "好吃",
        "良心", "实惠", "划算", "值得", "收藏", "推荐", "安利", "绝绝子",
        "yyds", "高级", "大气", "上档次", "高品质", "没话说",
    ]

    # ── Negative keywords ──
    NEGATIVE_KEYWORDS: list[str] = [
        "差", "烂", "垃圾", "坑", "骗", "不行", "失望", "后悔", "不好",
        "很差", "太差", "不值", "上当", "虚假", "不值", "差评", "质量差",
        "效果差", "无语", "糟糕", "不好用", "不好吃", "不好看", "一般般",
        "凑合", "勉强", "不值这个价",
    ]

    # ── Angry keywords ──
    ANGRY_KEYWORDS: list[str] = [
        "滚", "骗子", "投诉", "举报", "骂人", "退钱", "还钱", "欺骗",
        "欺诈", "假冒", "假货", "无耻", "恶心", "气愤", "忍不了",
        "受不了", "过分", "太过分", "黑心", "无良", "倒闭", "关门",
    ]

    # ── Excited patterns/keywords ──
    EXCITED_KEYWORDS: list[str] = [
        "冲冲冲", "买买买", "太棒了", "太美了", "太喜欢了", "太赞了",
        "无敌", "绝了", "尖叫", "太可了", "爱了爱了", "迫不及待",
        "好期待", "期待", "太想买了",
    ]

    # Excited patterns: exclamation marks, question marks, repetitive chars
    EXCITED_PATTERNS: list[Pattern] = [
        re.compile(r"!!!+"),
        re.compile(r"\?!+"),
        re.compile(r"冲冲冲"),
        re.compile(r"买买买"),
        re.compile(r"(太|好|超).{1,4}(了|啊|呀|吧).*[!！]"),
        re.compile(r"[A-Z]{4,}"),  # ALL CAPS (SHOUTING)
    ]

    def analyze(self, text: str) -> SentimentResult:
        """
        Analyze the sentiment of the given text.

        Returns sentiment classification with intensity score.
        """
        if not text or not text.strip():
            return SentimentResult(
                sentiment=SentimentType.NEUTRAL,
                intensity=0.0,
                reason="Empty text — classified as NEUTRAL",
            )

        text_lower = text.lower().strip()

        # Score each sentiment category
        positive_score = self._score_keywords(text_lower, self.POSITIVE_KEYWORDS)
        negative_score = self._score_keywords(text_lower, self.NEGATIVE_KEYWORDS)
        angry_score = self._score_keywords(text_lower, self.ANGRY_KEYWORDS)
        excited_score = self._score_keywords(text_lower, self.EXCITED_KEYWORDS)

        # Boost excited score for exclamation/pattern matches
        for pat in self.EXCITED_PATTERNS:
            if pat.search(text):
                excited_score += 0.3

        # Cap all scores
        positive_score = min(positive_score, 1.0)
        negative_score = min(negative_score, 1.0)
        angry_score = min(angry_score, 1.0)
        excited_score = min(excited_score, 1.0)

        scores = {
            SentimentType.POSITIVE: positive_score,
            SentimentType.NEGATIVE: negative_score,
            SentimentType.ANGRY: angry_score,
            SentimentType.EXCITED: excited_score,
        }

        # If no strong signal, return neutral
        max_score = max(scores.values())
        if max_score < 0.1:
            return SentimentResult(
                sentiment=SentimentType.NEUTRAL,
                intensity=0.0,
                reason="No strong sentiment detected — classified as NEUTRAL",
            )

        # Angry takes priority over negative
        if angry_score >= 0.3:
            return SentimentResult(
                sentiment=SentimentType.ANGRY,
                intensity=round(angry_score, 4),
                reason=f"Angry sentiment detected (score={angry_score:.2f})",
            )

        # Excited takes priority over positive
        if excited_score >= 0.3 and excited_score >= positive_score:
            return SentimentResult(
                sentiment=SentimentType.EXCITED,
                intensity=round(excited_score, 4),
                reason=f"Excited sentiment detected (score={excited_score:.2f})",
            )

        # Pick the highest score among positive/negative
        if positive_score >= negative_score and positive_score >= 0.1:
            return SentimentResult(
                sentiment=SentimentType.POSITIVE,
                intensity=round(positive_score, 4),
                reason=f"Positive sentiment detected (score={positive_score:.2f})",
            )
        elif negative_score >= 0.1:
            return SentimentResult(
                sentiment=SentimentType.NEGATIVE,
                intensity=round(negative_score, 4),
                reason=f"Negative sentiment detected (score={negative_score:.2f})",
            )

        return SentimentResult(
            sentiment=SentimentType.NEUTRAL,
            intensity=0.0,
            reason="Fallback — classified as NEUTRAL",
        )

    @staticmethod
    def _score_keywords(text: str, keywords: list[str]) -> float:
        """
        Score text against a list of keywords.

        Returns a float 0.0–1.0 based on keyword density.
        """
        if not text:
            return 0.0

        matches = sum(1 for kw in keywords if kw in text)
        if matches == 0:
            return 0.0

        # Normalize: use keyword density with diminishing returns
        # 1 keyword → ~0.3, 2 keywords → ~0.5, 3+ → up to 1.0
        score = 1.0 - (1.0 / (1.0 + matches * 0.7))
        return round(min(score, 1.0), 4)


# Singleton instance
sentiment_analyzer = SentimentAnalyzer()
