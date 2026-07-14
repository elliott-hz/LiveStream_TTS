"""
Danmaku Collector — Ingests raw danmaku messages from Kafka.

Responsibilities:
- Consume from 'danmaku.raw' Kafka topic
- Parse platform-specific JSON message formats
- Deduplicate by danmaku_id (5-minute TTL)
- Filter empty/spam messages
- Forward to next pipeline stage via callback
"""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from typing import Awaitable, Callable

from libs.common.logging import get_logger
from libs.kafka import KafkaClient, Topics

from ..models import DanmakuEvent

logger = get_logger(__name__)


class DanmakuCollector:
    """Ingests raw danmaku from Kafka, deduplicates, and forwards."""

    def __init__(
        self,
        kafka: KafkaClient,
        dedup_ttl_seconds: int = 300,
        max_dedup_size: int = 100000,
    ) -> None:
        self._kafka = kafka
        self._dedup_ttl = dedup_ttl_seconds
        # OrderedDict used as LRU-like dedup cache: {danmaku_id: timestamp}
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._max_dedup_size = max_dedup_size
        self._handler: Callable[[DanmakuEvent], Awaitable[None]] | None = None

    def set_handler(self, handler: Callable[[DanmakuEvent], Awaitable[None]]) -> None:
        """Set the async callback for processed danmaku events."""
        self._handler = handler

    async def start(self) -> None:
        """Start consuming from the danmaku.raw topic."""
        logger.info("collector.starting", topic=Topics.DANMAKU_RAW)
        await self._kafka.consume(Topics.DANMAKU_RAW, handler=self._on_message)

    async def _on_message(self, value: bytes, headers: dict[str, str]) -> None:
        """Process a single raw Kafka message."""
        try:
            payload = json.loads(value.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("collector.parse_error", error=str(e))
            return

        event = self._parse_payload(payload)
        if event is None:
            return

        if self._is_duplicate(event.danmaku_id):
            logger.debug("collector.duplicate", danmaku_id=event.danmaku_id)
            return

        self._mark_seen(event.danmaku_id)

        if self._handler:
            try:
                await self._handler(event)
            except Exception:
                logger.exception("collector.handler_error", danmaku_id=event.danmaku_id)

    def _parse_payload(self, payload: dict) -> DanmakuEvent | None:
        """Parse a raw JSON payload into a DanmakuEvent.

        Supports a common format:
          {"danmaku_id": "...", "text": "...", "user_id": "...", "platform": "douyin", ...}
        """
        text = (payload.get("text") or "").strip()
        if not text:
            return None

        # Spam filter: repeated single characters, very short messages
        if len(text) < 1:
            return None
        if len(text) == 1 and text in (".", "。", "!", "！", "?", "？"):
            return None
        if len(set(text)) == 1 and len(text) > 3:
            # Repeated single char (e.g. "。。。。。。", "!!!!!")
            return None

        return DanmakuEvent(
            danmaku_id=payload.get("danmaku_id", "") or payload.get("id", ""),
            text=text,
            platform_user_id=payload.get("user_id", "") or payload.get("userId", ""),
            platform=payload.get("platform", "unknown"),
            timestamp=payload.get("timestamp", 0) or int(time.time() * 1000),
        )

    def _is_duplicate(self, danmaku_id: str) -> bool:
        """Check if a message ID was seen recently (within TTL)."""
        if not danmaku_id:
            return False
        seen_at = self._seen.get(danmaku_id)
        if seen_at is None:
            return False
        return (time.monotonic() - seen_at) < self._dedup_ttl

    def _mark_seen(self, danmaku_id: str) -> None:
        """Record a message ID with current timestamp."""
        if not danmaku_id:
            return
        self._seen[danmaku_id] = time.monotonic()
        # Evict oldest entries when cache exceeds max size
        while len(self._seen) > self._max_dedup_size:
            self._seen.popitem(last=False)

    def cleanup_expired(self) -> int:
        """Remove expired entries from the dedup cache. Returns count removed."""
        now = time.monotonic()
        expired = [k for k, t in self._seen.items() if (now - t) >= self._dedup_ttl]
        for k in expired:
            self._seen.pop(k, None)
        return len(expired)
