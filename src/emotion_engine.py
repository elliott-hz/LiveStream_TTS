"""
M5 — Emotion & Style Engine
POC: 始终返回 neutral(1.0)。保留接口供后续接入 LLM 分类。
"""

import logging
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger("M5.Emotion")


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
        """
        emotion = explicit_emotion or "neutral"
        if emotion not in self.SUPPORTED_EMOTIONS:
            logger.warning(f"Unsupported emotion '{explicit_emotion}', falling back to 'neutral'")
            emotion = "neutral"

        tag = EmotionTag(emotion=emotion, intensity=1.0, style="conversational")

        logger.info("╔═══════════════════════════════════════════")
        logger.info(f"║ INPUT TEXT: \"{text[:50]}{'...' if len(text)>50 else ''}\"")
        logger.info(f"║ CLIENT SPECIFIED: {explicit_emotion or 'not set (use default)'}")
        logger.info(f"║ RESULT: emotion={tag.emotion}, intensity={tag.intensity}, style={tag.style}")
        logger.info("╚═══════════════════════════════════════════")
        return tag
