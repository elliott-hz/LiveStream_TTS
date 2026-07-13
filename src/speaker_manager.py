"""
M6 — Speaker Manager
POC: JSON 文件存储。预置 default 音色。
"""

import json
import logging
import os
from dataclasses import dataclass, asdict, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VoiceProfile:
    voice_id: str
    name: str
    gender: str = "unknown"
    language: str = "zh-CN"
    status: str = "active"
    embedding_path: str = ""
    prompt_audio_path: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class SpeakerManager:
    """
    音色管理器。
    POC: 从 JSON 文件加载音色列表。无 Embedding 向量文件，使用固定占位符。
    """

    def __init__(self, voices_dir: str):
        self.voices_dir = voices_dir
        self._voices: dict[str, VoiceProfile] = {}
        self._load_defaults()

    def _load_defaults(self):
        """从 voices/ 目录加载音色。"""
        # 内建 default 音色
        default = VoiceProfile(
            voice_id="default",
            name="默认音色",
            gender="female",
            language="zh-CN",
            status="active",
        )
        self._voices["default"] = default

        # 尝试加载用户自定义音色
        profile_path = os.path.join(self.voices_dir, "default", "voice.json")
        if os.path.exists(profile_path):
            try:
                with open(profile_path) as f:
                    data = json.load(f)
                vp = VoiceProfile(**data)
                self._voices[vp.voice_id] = vp
            except Exception:
                pass

    # --- 对内接口 (供 M7 调用) ---

    def get_voice(self, voice_id: str) -> Optional[VoiceProfile]:
        voice = self._voices.get(voice_id)
        if voice:
            logger.info("╔═══════════════════════════════════════════")
            logger.info(f"║ VOICE ID: {voice_id}")
            logger.info(f"║ NAME: {voice.name}")
            logger.info(f"║ GENDER: {voice.gender}, LANG: {voice.language}")
            logger.info(f"║ STATUS: {voice.status}")
            logger.info(f"║ EMBEDDING: {voice.embedding_path or '(none, POC default)'}")
            logger.info(f"╚═══════════════════════════════════════════")
        else:
            logger.warning(f"Voice '{voice_id}' not found")
        return voice

    def load_embedding(self, voice_id: str) -> list:
        """
        加载音色 Embedding 向量。
        POC: 返回空列表（占位符）。
        """
        voice = self.get_voice(voice_id)
        if voice and voice.embedding_path:
            logger.info(f"Loading embedding from {voice.embedding_path}")
            # TODO: numpy.load(embedding_path)
        else:
            logger.info(f"No embedding file for '{voice_id}', using default")
        return []

    def load_prompt_audio(self, voice_id: str) -> bytes:
        logger.info(f"Prompt audio load requested for '{voice_id}' — POC: returning empty")
        return b""

    # --- 对外接口 REST (供 M1 管理用) ---

    def list_voices(self) -> list[dict]:
        return [v.to_dict() for v in self._voices.values() if v.status == "active"]

    def get_voice_by_id(self, voice_id: str) -> Optional[dict]:
        v = self._voices.get(voice_id)
        return v.to_dict() if v else None

    def create_voice(self, profile: VoiceProfile) -> VoiceProfile:
        self._voices[profile.voice_id] = profile
        # 持久化到 JSON 文件
        voice_dir = os.path.join(self.voices_dir, profile.voice_id)
        os.makedirs(voice_dir, exist_ok=True)
        with open(os.path.join(voice_dir, "voice.json"), "w") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        return profile

    def delete_voice(self, voice_id: str) -> bool:
        if voice_id == "default":
            return False  # 不允许删除默认音色
        if voice_id in self._voices:
            self._voices[voice_id].status = "deleted"
            return True
        return False
