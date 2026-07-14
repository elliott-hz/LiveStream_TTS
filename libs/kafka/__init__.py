"""
Kafka client wrapper (async) — producer & consumer helpers.

Uses aiokafka under the hood for async I/O.
"""

import asyncio
from typing import AsyncIterator, Callable, Awaitable

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore

from libs.common.config import ServiceConfig
from libs.common.logging import get_logger

logger = get_logger(__name__)


class KafkaClient:
    """Async Kafka client for producing and consuming messages.

    Usage:
        kafka = KafkaClient(ServiceConfig("interact-svc"))
        await kafka.connect()
        await kafka.produce("danmaku.events", b'{"type": "comment"}')
    """

    def __init__(self, config: ServiceConfig):
        self.config = config
        self._producer: AIOKafkaProducer | None = None
        self._group_id = config.get("KAFKA_GROUP_ID", config.service_name)

    @property
    def bootstrap_servers(self) -> str:
        return self.config.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9093")

    async def connect(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            compression_type="gzip",
        )
        await self._producer.start()
        logger.info("kafka.connected", bootstrap_servers=self.bootstrap_servers)

    async def disconnect(self) -> None:
        if self._producer:
            await self._producer.stop()

    async def produce(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Produce a message to a Kafka topic."""
        if not self._producer:
            raise RuntimeError("Kafka not connected")
        _headers = [(k, v.encode()) for k, v in (headers or {}).items()]
        await self._producer.send_and_wait(topic, value=value, key=key, headers=_headers)

    async def consume(
        self,
        *topics: str,
        handler: Callable[[bytes, dict], Awaitable[None]],
        auto_commit: bool = True,
    ) -> None:
        """Consume messages from topics, invoking handler(value, headers) for each."""
        consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self._group_id,
            enable_auto_commit=auto_commit,
            auto_offset_reset="latest",
        )
        await consumer.start()
        try:
            async for msg in consumer:
                headers = {k: v.decode() for k, v in msg.headers or []}
                try:
                    await handler(msg.value, headers)
                except Exception:
                    logger.exception("kafka.handler_error", topic=msg.topic)
        finally:
            await consumer.stop()

    async def health_check(self) -> bool:
        try:
            await self._producer.partitions_for("__health_check_dummy__")
            return True
        except Exception:
            return False


# ── Well-known topics ──

class Topics:
    """Standardized Kafka topic names."""
    DANMAKU_RAW = "danmaku.raw"               # 平台弹幕原始消息
    DANMAKU_PROCESSED = "danmaku.processed"    # NLP 处理后的弹幕
    INTERACTION_REPLY = "interaction.reply"    # 互动回复 (语音+文字)
    LIVE_EVENTS = "live.events"                # 直播生命周期事件
    AUDIT_EVENTS = "audit.events"              # 审核相关事件
    ANALYTICS_EVENTS = "analytics.events"      # 数据分析事件
    PLATFORM_SYNC = "platform.sync"            # 平台同步任务
    NOTIFICATION = "notification.send"         # 通知发送
    BILLING_USAGE = "billing.usage"            # 用量计量
