"""
M9 — Audio Cache
POC: 内存 dict 缓存。生产环境换 Redis。
"""

import hashlib
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class AudioCache:
    """
    音频缓存。缓存已合成文本的完整 PCM。
    POC: 内存实现。
    """

    def __init__(self, default_ttl_seconds: int = 86400):
        self._store: dict[str, tuple[bytes, float]] = {}  # key → (pcm_data, expire_at)
        self.default_ttl = default_ttl_seconds

    @staticmethod
    def build_key(text: str, voice_id: str, emotion: str) -> str:
        """缓存键 = md5(text):voice_id:emotion"""
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        return f"{text_hash}:{voice_id}:{emotion}"

    def get(self, key: str) -> Optional[bytes]:
        """查缓存。命中返回 PCM bytes，未命中返回 None。"""
        entry = self._store.get(key)
        if entry is None:
            logger.info(f"MISS: {key[:40]}... ({self.size} entries in cache)")
            return None
        pcm_data, expire_at = entry
        if expire_at > 0 and time.time() > expire_at:
            del self._store[key]
            logger.info(f"EXPIRED: {key[:40]}... (TTL expired)")
            return None
        logger.info(f"HIT:  {key[:40]}... ({len(pcm_data)} bytes, {self.size} entries)")
        return pcm_data

    def set(self, key: str, pcm_data: bytes, ttl_seconds: Optional[int] = None) -> None:
        """写缓存。"""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expire_at = time.time() + ttl if ttl > 0 else 0
        self._store[key] = (pcm_data, expire_at)
        logger.info(f"WRITE: {key[:40]}... ({len(pcm_data)} bytes, TTL={ttl}s, cache now {self.size} entries)")

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)
