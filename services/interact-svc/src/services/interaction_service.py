"""
InteractionService — The core pipeline orchestrator.

Coordinates all pipeline stages:
  Danmaku → Collector → Profile Lookup → Router → Orchestrator → [Reply]

This is the central class that wires everything together and provides
a clean API for the gRPC and HTTP handlers.
"""

from __future__ import annotations

import time
from typing import Any

from libs.common.errors import AppError, ErrorCode, Domain
from libs.common.logging import get_logger
from libs.kafka import KafkaClient
from libs.proto.nlp.v1 import nlp_pb2

from ..config import config as svc_config
from ..models import (
    Channel,
    DanmakuEvent,
    ModeratorAction,
    ModeratorActionType,
    Session,
    SessionConfig,
    SessionStats,
    SessionStatus,
    ModeratorConfig,
    ReplyRecord,
    RouteResult,
)
from ..pipeline import (
    ChannelRouter,
    DanmakuCollector,
    ProfileLookup,
    PromptOrchestrator,
    TextModerator,
)

logger = get_logger(__name__)


class InteractionService:
    """Core interaction service — orchestrates the full pipeline."""

    def __init__(
        self,
        kafka: KafkaClient | None = None,
        router: ChannelRouter | None = None,
        profile_lookup: ProfileLookup | None = None,
        orchestrator: PromptOrchestrator | None = None,
    ) -> None:
        self._kafka = kafka
        self._router = router or ChannelRouter()
        self._profile = profile_lookup or ProfileLookup()
        self._orchestrator = orchestrator or PromptOrchestrator()

        # In-memory session store (PostgreSQL in production)
        self._sessions: dict[str, Session] = {}
        self._reply_records: dict[str, ReplyRecord] = {}

        # Moderators keyed by session_id
        self._moderators: dict[str, TextModerator] = {}

    # ── Session Management ──

    def start_session(self, live_room_id: str, config: SessionConfig) -> Session:
        """Start a new interaction session."""
        if not live_room_id:
            raise AppError(
                ErrorCode.INVALID_ARGUMENT,
                "live_room_id is required",
                domain=Domain.INTERACT,
            )

        session = Session.create(live_room_id, config)
        self._sessions[session.session_id] = session

        # Create moderator for this session
        self._moderators[session.session_id] = TextModerator(
            session_id=session.session_id,
            config=config.moderator_config,
        )

        logger.info(
            "session.started",
            session_id=session.session_id,
            live_room_id=live_room_id,
        )
        return session

    def stop_session(self, session_id: str) -> None:
        """Stop an active session."""
        session = self._get_session(session_id)
        if session.status == SessionStatus.STOPPED:
            raise AppError(
                ErrorCode.RESOURCE_IN_USE,
                f"Session {session_id} is already stopped",
                domain=Domain.INTERACT,
            )
        session.status = SessionStatus.STOPPED
        session.ended_at = int(time.time() * 1000)

        # Clean up moderator
        self._moderators.pop(session_id, None)

        logger.info("session.stopped", session_id=session_id)

    def get_session(self, session_id: str) -> Session:
        """Get session by ID."""
        return self._get_session(session_id)

    def list_active_sessions(self) -> list[Session]:
        """List all running sessions."""
        return [
            s for s in self._sessions.values()
            if s.status == SessionStatus.RUNNING
        ]

    # ── Danmaku Processing ──

    async def process_danmaku(
        self,
        session_id: str,
        danmaku_id: str,
        text: str,
        platform_user_id: str,
        platform: str = "",
        timestamp: int = 0,
    ) -> ReplyRecord:
        """Process a single danmaku through the full pipeline.

        Pipeline: Parse → Profile Lookup → NLP Analysis → Route → Orchestrate → Reply
        """
        start_time = time.monotonic()
        session = self._get_session(session_id)

        if session.status != SessionStatus.RUNNING:
            raise AppError(
                ErrorCode.LIVE_ROOM_NOT_IN_STATE,
                f"Session {session_id} is not running",
                domain=Domain.INTERACT,
            )

        # Step 1: Create event
        event = DanmakuEvent(
            danmaku_id=danmaku_id,
            session_id=session_id,
            text=text.strip(),
            platform_user_id=platform_user_id,
            platform=platform,
            timestamp=timestamp or int(time.time() * 1000),
        )

        if not event.text:
            raise AppError(
                ErrorCode.INVALID_ARGUMENT,
                "Danmaku text is empty",
                domain=Domain.INTERACT,
            )

        # Step 2: Profile lookup
        event.user_profile = await self._profile.lookup(platform_user_id, platform)

        # Step 3: NLP analysis (mock for MVP — in production calls nlp-svc)
        nlp_result = self._mock_nlp_analysis(event.text)
        event.intent = nlp_result["intent"]
        event.intent_confidence = nlp_result["confidence"]
        event.sentiment = nlp_result["sentiment"]
        event.sentiment_intensity = nlp_result["intensity"]
        event.needs_reply = nlp_result["needs_reply"]

        # Step 4: Route to channel
        route_result = self._router.route(
            intent=event.intent,
            confidence=event.intent_confidence,
            sentiment=event.sentiment,
            user_profile=event.user_profile,
            reply_threshold=session.config.reply_threshold,
        )
        event.channel = route_result.channel
        event.route_reason = route_result.reason

        # Update session stats
        session.stats.total_danmaku += 1
        if route_result.channel == Channel.IGNORE:
            session.stats.ignored_messages += 1
        elif route_result.channel in (Channel.VOICE, Channel.BOTH):
            session.stats.voice_replies += 1
        if route_result.channel == Channel.TEXT:
            session.stats.text_replies += 1

        # Step 5: If not ignored, reply
        if route_result.channel == Channel.IGNORE:
            latency = (time.monotonic() - start_time) * 1000
            self._update_avg_latency(session, latency)
            return ReplyRecord.create(
                session_id=session_id,
                danmaku_id=danmaku_id,
                channel=Channel.IGNORE,
                latency_ms=latency,
            )

        # Step 6: In production — orchestrate LLM prompt and call LLM
        # For MVP, generate a mock reply based on intent
        reply_text, emotion, action = self._mock_reply(event, session)

        # Step 7: Build reply record
        latency = (time.monotonic() - start_time) * 1000
        reply = ReplyRecord.create(
            session_id=session_id,
            danmaku_id=danmaku_id,
            channel=route_result.channel,
            reply_text=reply_text,
            emotion=emotion,
            action=action,
            latency_ms=latency,
        )
        self._reply_records[reply.reply_id] = reply
        self._update_avg_latency(session, latency)

        # Step 8: Publish reply event to Kafka
        if self._kafka:
            await self._publish_reply(reply, route_result)

        logger.debug(
            "pipeline.complete",
            danmaku_id=danmaku_id,
            channel=Channel(route_result.channel).name,
            intent=nlp_pb2.IntentCategory.Name(event.intent) if event.intent else "UNKNOWN",
            latency_ms=round(latency, 1),
        )

        return reply

    # ── Channel Routing ──

    def route_channel(
        self,
        text: str,
        intent: int,
        confidence: float,
        sentiment: int = 0,
        user_tags: dict[str, Any] | None = None,
        reply_threshold: float = 0.3,
    ) -> RouteResult:
        """Route a message to the appropriate channel based on NLP analysis.

        This is a standalone routing call (without the full pipeline).
        """
        return self._router.route(
            intent=intent,
            confidence=confidence,
            sentiment=sentiment,
            user_profile=user_tags or {},
            reply_threshold=reply_threshold,
        )

    # ── Moderator Actions ──

    async def get_moderator_action(
        self,
        session_id: str,
        trigger_event: str,
        context: dict[str, Any] | None = None,
    ) -> ModeratorAction:
        """Get an AI moderator action for the given trigger event."""
        moderator = self._moderators.get(session_id)
        if moderator is None:
            # Create temporary moderator if session doesn't exist
            moderator = TextModerator(session_id=session_id)
            self._moderators[session_id] = moderator

        action = await moderator.evaluate(trigger_event, context or {})

        # Update session stats
        session = self._sessions.get(session_id)
        if session and action.action_type != ModeratorActionType.NO_ACTION:
            session.stats.moderator_actions += 1

        return action

    # ── Collector Integration ──

    def create_collector(self, kafka: KafkaClient) -> DanmakuCollector:
        """Create a collector wired to this service's process_danmaku."""
        collector = DanmakuCollector(kafka)
        collector.set_handler(self._on_collected_danmaku)
        return collector

    async def _on_collected_danmaku(self, event: DanmakuEvent) -> None:
        """Callback for the collector's processed danmaku."""
        try:
            await self.process_danmaku(
                session_id=event.session_id or "",
                danmaku_id=event.danmaku_id,
                text=event.text,
                platform_user_id=event.platform_user_id,
                platform=event.platform,
                timestamp=event.timestamp,
            )
        except AppError as e:
            logger.warning(
                "pipeline.rejected",
                danmaku_id=event.danmaku_id,
                error=e.message,
            )
        except Exception:
            logger.exception(
                "pipeline.error",
                danmaku_id=event.danmaku_id,
            )

    # ── Helpers ──

    def _get_session(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise AppError(
                ErrorCode.NOT_FOUND,
                f"Session not found: {session_id}",
                domain=Domain.INTERACT,
            )
        return session

    @staticmethod
    def _update_avg_latency(session: Session, latency_ms: float) -> None:
        """Update running average latency."""
        total = session.stats.total_danmaku
        if total > 0:
            prev_avg = session.stats.avg_latency_ms
            session.stats.avg_latency_ms = prev_avg + (latency_ms - prev_avg) / total

    @staticmethod
    def _mock_nlp_analysis(text: str) -> dict[str, Any]:
        """Mock NLP analysis. In production, calls nlp-svc via gRPC.

        Simple keyword-based intent classification for development.
        """
        text_lower = text.lower()

        # Purchase intent
        if any(kw in text_lower for kw in ["怎么买", "下单", "购买", "链接", "多少钱", "价格", "怎么卖", "上链接"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT, "confidence": 0.92, "sentiment": nlp_pb2.SENTIMENT_POSITIVE, "intensity": 0.8, "needs_reply": True}

        # Bargain
        if any(kw in text_lower for kw in ["太贵", "便宜", "优惠", "打折", "降价", "能不能便宜", "贵了"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_BARGAIN, "confidence": 0.88, "sentiment": nlp_pb2.SENTIMENT_NEUTRAL, "intensity": 0.5, "needs_reply": True}

        # Questions
        if any(kw in text_lower for kw in ["什么", "怎么", "为什么", "哪个", "吗", "?", "？", "是不是", "能不能"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_QUESTION, "confidence": 0.85, "sentiment": nlp_pb2.SENTIMENT_NEUTRAL, "intensity": 0.5, "needs_reply": True}

        # Complaint
        if any(kw in text_lower for kw in ["差评", "不好", "垃圾", "退货", "退款", "投诉", "假货", "骗人", "太差", "质量差"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_COMPLAINT, "confidence": 0.9, "sentiment": nlp_pb2.SENTIMENT_NEGATIVE, "intensity": 0.8, "needs_reply": True}

        # Greeting
        if any(kw in text_lower for kw in ["你好", "大家好", "嗨", "hello", "hi", "主播好", "来了"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_GREETING, "confidence": 0.95, "sentiment": nlp_pb2.SENTIMENT_POSITIVE, "intensity": 0.6, "needs_reply": True}

        # Praise
        if any(kw in text_lower for kw in ["好看", "漂亮", "喜欢", "不错", "好棒", "厉害", "赞", "牛逼"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_PRAISE, "confidence": 0.9, "sentiment": nlp_pb2.SENTIMENT_POSITIVE, "intensity": 0.8, "needs_reply": True}

        # Compare
        if any(kw in text_lower for kw in ["对比", "哪个好", "vs", "比较", "区别", "不同"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_COMPARE, "confidence": 0.82, "sentiment": nlp_pb2.SENTIMENT_NEUTRAL, "intensity": 0.4, "needs_reply": True}

        # Request demo
        if any(kw in text_lower for kw in ["讲解", "展示", "示范", "演示", "介绍一下", "看看"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_REQUEST_DEMO, "confidence": 0.87, "sentiment": nlp_pb2.SENTIMENT_POSITIVE, "intensity": 0.6, "needs_reply": True}

        # After-sales
        if any(kw in text_lower for kw in ["售后", "维修", "保修", "换货", "客服"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_AFTERSALES, "confidence": 0.85, "sentiment": nlp_pb2.SENTIMENT_NEUTRAL, "intensity": 0.5, "needs_reply": True}

        # Urge
        if any(kw in text_lower for kw in ["快点", "加速", "赶紧", "快上", "等不及", "快快"]):
            return {"intent": nlp_pb2.INTENT_CATEGORY_URGE, "confidence": 0.75, "sentiment": nlp_pb2.SENTIMENT_EXCITED, "intensity": 0.7, "needs_reply": True}

        return {"intent": nlp_pb2.INTENT_CATEGORY_OTHER, "confidence": 0.2, "sentiment": nlp_pb2.SENTIMENT_NEUTRAL, "intensity": 0.3, "needs_reply": False}

    @staticmethod
    def _mock_reply(event: DanmakuEvent, session: Session) -> tuple[str, int, str]:
        """Generate a mock reply based on intent. LLM-powered in production.

        Returns (reply_text, emotion_enum_value, action_string).
        """
        intent = event.intent
        product_title = svc_config.product_title

        replies = {
            nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT: (
                f"{product_title} 现在下单只要 {svc_config.product_price} 元，点击下方链接购买哦~",
                2,  # EMOTION_HAPPY
                "show_product_card",
            ),
            nlp_pb2.INTENT_CATEGORY_QUESTION: (
                f"这款 {product_title} 富含三重玻尿酸，补水效果特别好哦！",
                4,  # EMOTION_WARM
                "point_product",
            ),
            nlp_pb2.INTENT_CATEGORY_REQUEST_DEMO: (
                f"好的，给大家详细讲解一下 {product_title}~",
                3,  # EMOTION_EXCITED
                "show_detail",
            ),
            nlp_pb2.INTENT_CATEGORY_BARGAIN: (
                f"亲，这个价格已经是最优惠了，性价比超高哦！",
                4,  # EMOTION_WARM
                "wave_hand",
            ),
            nlp_pb2.INTENT_CATEGORY_COMPLAINT: (
                "亲亲别着急，有什么问题可以私信客服帮您解决哦~",
                4,  # EMOTION_WARM
                "wave_hand",
            ),
            nlp_pb2.INTENT_CATEGORY_GREETING: (
                "欢迎来到直播间！喜欢的话点个关注哦~",
                2,  # EMOTION_HAPPY
                "wave_hand",
            ),
            nlp_pb2.INTENT_CATEGORY_PRAISE: (
                "谢谢亲的夸奖！喜欢的话记得分享给朋友哦~",
                2,  # EMOTION_HAPPY
                "wave_hand",
            ),
            nlp_pb2.INTENT_CATEGORY_COMPARE: (
                f"我们的 {product_title} 添加了三重玻尿酸成分，比同类产品补水效果更好哦！",
                3,  # EMOTION_EXCITED
                "show_detail",
            ),
            nlp_pb2.INTENT_CATEGORY_AFTERSALES: (
                "售后问题请私信客服，我们会第一时间为您处理！",
                4,  # EMOTION_WARM
                "wave_hand",
            ),
            nlp_pb2.INTENT_CATEGORY_URGE: (
                "马上给大家安排！正在准备中~",
                3,  # EMOTION_EXCITED
                "wave_hand",
            ),
        }

        default = (
            f"感谢您的关注！有什么问题可以随时问我哦~",
            2,  # EMOTION_HAPPY
            "wave_hand",
        )

        return replies.get(intent, default)

    @staticmethod
    async def _publish_reply(reply: ReplyRecord, route: RouteResult) -> None:
        """Publish reply event to Kafka for downstream consumers (TTS, frontend, etc.)."""
        # In production: serialize to protobuf and publish to INTERACTION_REPLY topic
        # For MVP, this is a placeholder
        logger.debug(
            "kafka.reply_published",
            reply_id=reply.reply_id,
            channel=Channel(reply.channel).name,
        )
