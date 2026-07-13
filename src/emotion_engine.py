"""
M5 — Emotion & Style Engine
POC: 始终返回 neutral(1.0)。保留接口供后续接入 LLM 分类。
"""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class EmotionTag:
    emotion: str = "neutral"  # neutral / happy / sad / excited / calm
    intensity: float = 1.0    # [0.0, 1.0]
    style: str = "conversational"  # conversational / broadcast / storytelling

    def to_dict(self):
        return asdict(self)


class EmotionEngine:
    """
    情感与风格分析。
    POC 实现: client 指定则用指定的，否则返回 neutral。
    后续可接入 LLM 进行语义级情感分类。
    """

    SUPPORTED_EMOTIONS = {"neutral", "happy", "sad", "excited", "calm"}
    SUPPORTED_STYLES = {"conversational", "broadcast", "storytelling"}

    def classify(self, text: str, explicit_emotion: Optional[str] = None) -> EmotionTag:
        """
        分析文本情感。
        Args:
            text: 规范化后的文本
            explicit_emotion: client 明确指定的情感（来自 synthesis_request）
        Returns:
            EmotionTag
        """
        emotion = explicit_emotion or "neutral"
        if emotion not in self.SUPPORTED_EMOTIONS:
            emotion = "neutral"
        return EmotionTag(emotion=emotion, intensity=1.0, style="conversational")
