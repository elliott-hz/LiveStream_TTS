"""
M4 — Linguistic Processing Engine
POC: 简化实现。用 pypinyin 做 G2P + 固定 Prosody 规则。
"""

import logging
from dataclasses import dataclass, asdict, field
from typing import Optional

from pypinyin import pinyin, Style

logger = logging.getLogger("M4.Linguistic")


@dataclass
class LinguisticFeatures:
    """语言学特征 — TTS Engine 的输入。"""
    phonemes: list[str] = field(default_factory=list)
    durations_ms: list[int] = field(default_factory=list)
    f0_contour: list[float] = field(default_factory=list)
    pause_positions: list[dict] = field(default_factory=list)
    energy_contour: list[float] = field(default_factory=list)
    stress_tags: list[int] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


# Emotion → Prosody 参数映射表
EMOTION_PROFILE = {
    "neutral": {"speed_factor": 1.0, "pitch_baseline": 220, "energy": 0.8},
    "happy":   {"speed_factor": 1.1, "pitch_baseline": 260, "energy": 0.9},
    "sad":     {"speed_factor": 0.8, "pitch_baseline": 180, "energy": 0.5},
    "excited": {"speed_factor": 1.2, "pitch_baseline": 280, "energy": 1.0},
    "calm":    {"speed_factor": 0.9, "pitch_baseline": 200, "energy": 0.6},
}


class LinguisticEngine:
    """
    语言处理引擎。
    POC: pypinyin 做 G2P + 固定停顿规则 + Emotion 影响 Prosody 参数。
    """

    # 标点 → 停顿时长（毫秒）
    PAUSE_MAP = {
        "。": 400, "！": 350, "？": 350,
        "，": 200, "、": 150, "；": 250,
        "：": 200, "—": 300, "…": 300,
    }

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def _split_sentences(self, text: str) -> list[tuple[str, int]]:
        """
        按停顿标点分割句子。
        返回: [(句子, 句末停顿ms), ...]
        """
        result = []
        buf = []
        for ch in text:
            buf.append(ch)
            if ch in self.PAUSE_MAP:
                sentence = "".join(buf).strip()
                pause_ms = self.PAUSE_MAP[ch]
                if sentence:
                    result.append((sentence, pause_ms))
                buf = []
        remaining = "".join(buf).strip()
        if remaining:
            result.append((remaining, 0))
        return result

    def process(self, normalized_text: str, emotion: str = "neutral",
                speed: float = 1.0) -> LinguisticFeatures:
        """
        执行语言学处理。
        """
        logger.info("╔═══════════════════════════════════════════")
        logger.info(f"║ INPUT:  \"{normalized_text[:60]}{'...' if len(normalized_text)>60 else ''}\"")
        logger.info(f"║ EMOTION: {emotion}, SPEED: {speed}")

        features = LinguisticFeatures()

        emotion_profile = EMOTION_PROFILE.get(emotion, EMOTION_PROFILE["neutral"])
        speed_factor = emotion_profile["speed_factor"] * speed
        pitch_base = emotion_profile["pitch_baseline"]
        energy = emotion_profile["energy"]

        logger.info(f"║ PROFILE: speed_factor={speed_factor:.2f}, pitch_base={pitch_base}Hz, energy={energy}")

        sentences = self._split_sentences(normalized_text)
        logger.info(f"║ SENTENCES: {len(sentences)} detected")
        for i, (sent, pause) in enumerate(sentences):
            logger.info(f"║   [{i}] \"{sent[:30]}\" → pause {pause}ms")

        for sentence, pause_ms in sentences:
            if not sentence.strip():
                continue

            # G2P: 汉字 → 拼音（声母+韵母作为音素单元）
            raw = pinyin(sentence, style=Style.BOPOMOFO_FIRST, errors="ignore")
            for syllable_list in raw:
                for syllable in syllable_list:
                    features.phonemes.append(syllable)

            # 音素时长
            features.durations_ms = [
                int(80 / speed_factor) for _ in features.phonemes
            ]

            # F0 Contour
            num_phonemes = len(features.phonemes) - (phoneme_offset if 'phoneme_offset' in dir() else 0)
            for i in range(num_phonemes if num_phonemes > 0 else 0):
                t = i / max(num_phonemes, 1)
                pitch = pitch_base + 30 * (1 - t) - 20 * t
                features.f0_contour.append(pitch)

            features.energy_contour.extend([energy] * max(num_phonemes, 1))

            if pause_ms > 0:
                features.pause_positions.append({
                    "after_phoneme_index": len(features.phonemes) - 1,
                    "duration_ms": pause_ms,
                })

        # 输出摘要
        logger.info(f"║ PHONEMES: {len(features.phonemes)} total")
        if features.phonemes:
            logger.info(f"║   first 10: {features.phonemes[:10]}")
        logger.info(f"║ PAUSES: {len(features.pause_positions)}")
        for p in features.pause_positions:
            logger.info(f"║   after phoneme #{p['after_phoneme_index']}: {p['duration_ms']}ms")
        logger.info(f"║ F0: {len(features.f0_contour)} points, range {min(features.f0_contour):.0f}-{max(features.f0_contour):.0f}Hz" if features.f0_contour else "║ F0: none")
        logger.info(f"╚═══════════════════════════════════════════")

        return features
