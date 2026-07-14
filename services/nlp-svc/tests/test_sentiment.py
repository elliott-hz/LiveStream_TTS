"""
Tests for the 5-class sentiment analyzer.

Covers: POSITIVE, NEGATIVE, NEUTRAL, ANGRY, EXCITED
"""

from __future__ import annotations

import pytest

from src.classifiers.sentiment import SentimentAnalyzer, SentimentType


@pytest.fixture
def analyzer() -> SentimentAnalyzer:
    return SentimentAnalyzer()


class TestSentimentPositive:
    """SENTIMENT_POSITIVE (1) — Positive / favorable."""

    @pytest.mark.parametrize("text", [
        "这个产品真不错！",
        "我很喜欢这个设计",
        "非常满意，支持主播",
        "太棒了，推荐给大家",
        "好看又好用，给力",
        "品质很好，值得购买",
    ])
    def test_positive_detection(self, analyzer: SentimentAnalyzer, text: str) -> None:
        result = analyzer.analyze(text)
        assert result.sentiment == SentimentType.POSITIVE, (
            f"Expected POSITIVE for '{text}', got {result.sentiment.name}"
        )
        assert result.intensity > 0.1


class TestSentimentNegative:
    """SENTIMENT_NEGATIVE (2) — Negative / unfavorable."""

    @pytest.mark.parametrize("text", [
        "这个产品质量太差了",
        "很失望，根本不值这个价",
        "不好用，后悔买了",
        "太差了，差评",
        "效果不行",
    ])
    def test_negative_detection(self, analyzer: SentimentAnalyzer, text: str) -> None:
        result = analyzer.analyze(text)
        assert result.sentiment == SentimentType.NEGATIVE, (
            f"Expected NEGATIVE for '{text}', got {result.sentiment.name}"
        )
        assert result.intensity > 0.1


class TestSentimentNeutral:
    """SENTIMENT_NEUTRAL (3) — Neutral (fallback)."""

    @pytest.mark.parametrize("text", [
        "这个多少钱",
        "我看看",
        "嗯嗯",
        "abc 123 test",
    ])
    def test_neutral_detection(self, analyzer: SentimentAnalyzer, text: str) -> None:
        result = analyzer.analyze(text)
        assert result.sentiment == SentimentType.NEUTRAL, (
            f"Expected NEUTRAL for '{text}', got {result.sentiment.name}"
        )


class TestSentimentAngry:
    """SENTIMENT_ANGRY (4) — Angry / furious."""

    @pytest.mark.parametrize("text", [
        "骗子！退钱！",
        "我要投诉你们",
        "太恶心了，滚！",
        "欺诈消费者，举报了",
        "假货！还钱！",
    ])
    def test_angry_detection(self, analyzer: SentimentAnalyzer, text: str) -> None:
        result = analyzer.analyze(text)
        assert result.sentiment == SentimentType.ANGRY, (
            f"Expected ANGRY for '{text}', got {result.sentiment.name}"
        )
        assert result.intensity > 0.1


class TestSentimentExcited:
    """SENTIMENT_EXCITED (5) — Excited / enthusiastic."""

    @pytest.mark.parametrize("text", [
        "冲冲冲！！！",
        "买买买！太棒了！",
        "太喜欢了！！！",
        "好期待啊！！",
        "太美了，爱了爱了",
    ])
    def test_excited_detection(self, analyzer: SentimentAnalyzer, text: str) -> None:
        result = analyzer.analyze(text)
        assert result.sentiment == SentimentType.EXCITED, (
            f"Expected EXCITED for '{text}', got {result.sentiment.name}"
        )
        assert result.intensity > 0.1


class TestSentimentEmpty:
    """Test empty text edge case."""

    def test_empty_text(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer.analyze("")
        assert result.sentiment == SentimentType.NEUTRAL
        assert result.intensity == 0.0

    def test_whitespace_text(self, analyzer: SentimentAnalyzer) -> None:
        result = analyzer.analyze("   ")
        assert result.sentiment == SentimentType.NEUTRAL
        assert result.intensity == 0.0
