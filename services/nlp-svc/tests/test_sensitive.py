"""
Tests for the dual-mode sensitive word detector.

Tests:
  - Dictionary matching (AC automaton) for political, adult, violence, ads
  - LLM semantic fallback (mock/placeholder)
  - Normal (non-sensitive) text
  - Edge cases: empty text, mixed content
"""

from __future__ import annotations

import pytest

from src.detectors.sensitive import (
    BUILTIN_SENSITIVE_DICT,
    DetectionLayer,
    SensitiveDetector,
)


@pytest.fixture
def detector() -> SensitiveDetector:
    return SensitiveDetector()


class TestSensitivePolitical:
    """Political category sensitive words."""

    @pytest.mark.parametrize("text,expected_word", [
        ("法轮功是邪教", "法轮功"),
        ("天安门广场", "天安门"),
        ("台独言论", "台独"),
        ("分裂国家", "分裂国家"),
    ])
    def test_political_detection(
        self, detector: SensitiveDetector, text: str, expected_word: str
    ) -> None:
        result = detector.check(text)
        assert result.is_sensitive, f"Expected '{text}' to be flagged as sensitive"

        matched_words = [m.word for m in result.matches]
        assert expected_word in matched_words, (
            f"Expected word '{expected_word}' not found in matches: {matched_words}"
        )

        for match in result.matches:
            if match.word == expected_word:
                assert match.category == "political"


class TestSensitiveAdult:
    """Adult category sensitive words."""

    @pytest.mark.parametrize("text,expected_word", [
        ("色情网站", "色情"),
        ("裸聊直播", "裸聊"),
        ("约炮软件", "约炮"),
        ("黄色视频", "黄色"),
        ("AV电影", "AV"),
    ])
    def test_adult_detection(
        self, detector: SensitiveDetector, text: str, expected_word: str
    ) -> None:
        result = detector.check(text)
        assert result.is_sensitive, f"Expected '{text}' to be flagged as sensitive"

        matched_words = [m.word for m in result.matches]
        assert expected_word in matched_words, (
            f"Expected word '{expected_word}' not found in matches: {matched_words}"
        )

        for match in result.matches:
            if match.word == expected_word:
                assert match.category == "adult"


class TestSensitiveViolence:
    """Violence category sensitive words."""

    @pytest.mark.parametrize("text,expected_word", [
        ("杀人放火", "杀人"),
        ("恐怖袭击", "恐怖袭击"),
        ("炸弹威胁", "炸弹"),
        ("血腥画面", "血腥"),
        ("暴力行为", "暴力"),
    ])
    def test_violence_detection(
        self, detector: SensitiveDetector, text: str, expected_word: str
    ) -> None:
        result = detector.check(text)
        assert result.is_sensitive, f"Expected '{text}' to be flagged as sensitive"

        matched_words = [m.word for m in result.matches]
        assert expected_word in matched_words, (
            f"Expected word '{expected_word}' not found in matches: {matched_words}"
        )

        for match in result.matches:
            if match.word == expected_word:
                assert match.category == "violence"


class TestSensitiveAds:
    """Ads/spam category sensitive words."""

    @pytest.mark.parametrize("text,expected_word", [
        ("加微信联系", "加微信"),
        ("扫码关注", "扫码"),
        ("日赚300", "日赚"),
        ("招代理", "招代理"),
        ("兼职刷单", "刷单"),
    ])
    def test_ads_detection(
        self, detector: SensitiveDetector, text: str, expected_word: str
    ) -> None:
        result = detector.check(text)
        assert result.is_sensitive, f"Expected '{text}' to be flagged as sensitive"

        matched_words = [m.word for m in result.matches]
        assert expected_word in matched_words, (
            f"Expected word '{expected_word}' not found in matches: {matched_words}"
        )

        for match in result.matches:
            if match.word == expected_word:
                assert match.category == "ads"


class TestSensitiveNormal:
    """Normal text that should NOT be flagged."""

    @pytest.mark.parametrize("text", [
        "这个产品真不错",
        "什么时候发货？",
        "大家好，我是新来的",
        "今天的直播真精彩",
        "可以优惠一点吗",
        "怎么买？链接在哪？",
    ])
    def test_normal_text_not_flagged(self, detector: SensitiveDetector, text: str) -> None:
        result = detector.check(text)
        assert not result.is_sensitive, (
            f"Expected '{text}' NOT to be flagged, but got matches: {result.matches}"
        )


class TestSensitivePosition:
    """Test that match positions are correctly returned."""

    def test_match_position(self, detector: SensitiveDetector) -> None:
        text = "这个加微信联系我"
        result = detector.check(text)
        assert result.is_sensitive

        for match in result.matches:
            if match.word == "加微信":
                assert text[match.start_pos:match.end_pos] == "加微信"
                return

        pytest.fail("'加微信' not found in matches")


class TestSensitiveMultipleMatches:
    """Test that multiple sensitive words can be detected in one text."""

    def test_multiple_matches(self, detector: SensitiveDetector) -> None:
        text = "加微信买黄色视频"
        result = detector.check(text)
        assert result.is_sensitive
        assert len(result.matches) >= 2

        matched_words = [m.word for m in result.matches]
        assert "加微信" in matched_words


class TestSensitiveEdgeCases:
    """Edge cases: empty text, whitespace, very long text."""

    def test_empty_text(self, detector: SensitiveDetector) -> None:
        result = detector.check("")
        assert not result.is_sensitive
        assert len(result.matches) == 0

    def test_whitespace_text(self, detector: SensitiveDetector) -> None:
        result = detector.check("   ")
        assert not result.is_sensitive
        assert len(result.matches) == 0

    def test_special_characters(self, detector: SensitiveDetector) -> None:
        result = detector.check("!@#$%^&*()")
        assert not result.is_sensitive


class TestSensitiveLLMFallback:
    """Test LLM semantic fallback (mock)."""

    def test_llm_fallback_disabled(self, detector: SensitiveDetector) -> None:
        """With llm_semantic_enabled=False, only AC automaton runs."""
        result = detector.check("这个产品质量真不错")
        assert not result.is_sensitive

    def test_llm_fallback_enabled(self) -> None:
        """With llm_semantic_enabled=True, both layers run."""
        detector = SensitiveDetector(llm_semantic_enabled=True)
        result = detector.check("这个产品质量真不错")
        # Even with LLM enabled, clean text should not be flagged
        assert not result.is_sensitive


class TestSensitiveDict:
    """Test the built-in dictionary has sufficient coverage."""

    def test_dict_has_minimum_words(self) -> None:
        """Ensure dictionary has at least 50 entries."""
        assert len(BUILTIN_SENSITIVE_DICT) >= 50, (
            f"Dictionary only has {len(BUILTIN_SENSITIVE_DICT)} entries, need at least 50"
        )

    def test_dict_has_all_categories(self) -> None:
        """Ensure dictionary covers all required categories."""
        categories = {cat for _, cat in BUILTIN_SENSITIVE_DICT}
        required = {"political", "adult", "violence", "ads"}
        missing = required - categories
        assert not missing, f"Dictionary missing categories: {missing}"

    def test_layer_enum_values(self) -> None:
        """Verify DetectionLayer enum values match proto."""
        assert DetectionLayer.AC_AUTOMATON == 1
        assert DetectionLayer.LLM_SEMANTIC == 2
