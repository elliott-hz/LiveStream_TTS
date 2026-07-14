"""
Pipeline integration tests — full danmaku processing flow.

Tests the InteractionService end-to-end:
  session management → danmaku processing → channel routing → reply generation

Uses mock in-memory components (no Kafka, no Redis, no NLP service).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Monorepo path setup
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_LIBS_PROTO = _REPO_ROOT / "libs" / "proto"
for p in [str(_REPO_ROOT), str(_LIBS_PROTO)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

from libs.common.errors import AppError
from libs.proto.nlp.v1 import nlp_pb2
from libs.proto.interact.v1 import interact_pb2

from src.models import (
    Channel,
    Session,
    SessionConfig,
    SessionStatus,
    ModeratorActionType,
)
from src.services import InteractionService
from src.pipeline import ChannelRouter, ProfileLookup


class TestPipelineIntegration:
    """Full pipeline integration tests."""

    @pytest.fixture
    def service(self) -> InteractionService:
        router = ChannelRouter()
        profiles = ProfileLookup()
        return InteractionService(router=router, profile_lookup=profiles)

    @pytest.fixture
    def session_config(self) -> SessionConfig:
        return SessionConfig(
            voice_id="test_voice",
            system_prompt="你是一名专业带货主播",
            reply_threshold=0.3,
            enable_moderator=True,
        )

    # ── Session Lifecycle ──

    def test_start_session(self, service: InteractionService, session_config: SessionConfig) -> None:
        """Starting a session should return a running session."""
        session = service.start_session("room_001", session_config)
        assert session.session_id.startswith("ses_")
        assert session.live_room_id == "room_001"
        assert session.status == SessionStatus.RUNNING
        assert session.started_at > 0

    def test_start_session_without_room_id_raises(
        self, service: InteractionService
    ) -> None:
        """Starting a session without live_room_id should raise."""
        with pytest.raises(AppError):
            service.start_session("", SessionConfig())

    def test_stop_session(self, service: InteractionService, session_config: SessionConfig) -> None:
        """Stopping a session should set status to STOPPED."""
        session = service.start_session("room_001", session_config)
        service.stop_session(session.session_id)
        stopped = service.get_session(session.session_id)
        assert stopped.status == SessionStatus.STOPPED
        assert stopped.ended_at > 0

    def test_stop_already_stopped_raises(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Stopping an already stopped session should raise."""
        session = service.start_session("room_001", session_config)
        service.stop_session(session.session_id)
        with pytest.raises(AppError):
            service.stop_session(session.session_id)

    def test_get_nonexistent_session_raises(self, service: InteractionService) -> None:
        """Getting a nonexistent session should raise NOT_FOUND."""
        with pytest.raises(AppError) as exc:
            service.get_session("nonexistent")
        assert exc.value.code.value == 3001

    def test_list_active_sessions(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """List active sessions should return only running sessions."""
        s1 = service.start_session("room_001", session_config)
        s2 = service.start_session("room_002", session_config)
        service.stop_session(s1.session_id)

        active = service.list_active_sessions()
        assert len(active) == 1
        assert active[0].session_id == s2.session_id

    # ── Danmaku Processing ──

    @pytest.mark.asyncio
    async def test_process_purchase_intent(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Purchase intent danmaku should route to VOICE channel with reply."""
        session = service.start_session("room_001", session_config)
        reply = await service.process_danmaku(
            session_id=session.session_id,
            danmaku_id="dm_001",
            text="这个怎么买？",
            platform_user_id="user_001",
            platform="douyin",
        )
        assert reply.channel == Channel.VOICE
        assert len(reply.reply_text) > 0
        assert reply.reply_id.startswith("rep_")
        assert reply.pipeline_latency_ms > 0

    @pytest.mark.asyncio
    async def test_process_greeting(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Greeting should route to TEXT channel (for non-new, non-VIP users)."""
        # Seed a non-new, non-VIP user so the greeting stays TEXT
        service._profile.seed("taobao:existing_user", {
            "is_new": False,
            "is_vip": False,
            "purchase_count": 1,
        })
        session = service.start_session("room_001", session_config)
        reply = await service.process_danmaku(
            session_id=session.session_id,
            danmaku_id="dm_002",
            text="大家好",
            platform_user_id="existing_user",
            platform="taobao",
        )
        assert reply.channel == Channel.TEXT

    @pytest.mark.asyncio
    async def test_process_low_confidence_ignored(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Low confidence/OTHER intent should be IGNORED."""
        session = service.start_session("room_001", session_config)
        reply = await service.process_danmaku(
            session_id=session.session_id,
            danmaku_id="dm_003",
            text="今天天气真好",
            platform_user_id="user_003",
            platform="jd",
        )
        assert reply.channel == Channel.IGNORE
        assert reply.reply_text == ""

    @pytest.mark.asyncio
    async def test_process_empty_text_raises(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Empty danmaku text should raise."""
        session = service.start_session("room_001", session_config)
        with pytest.raises(AppError):
            await service.process_danmaku(
                session_id=session.session_id,
                danmaku_id="dm_004",
                text="  ",
                platform_user_id="user_004",
                platform="kuaishou",
            )

    @pytest.mark.asyncio
    async def test_process_non_running_session_raises(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Processing a stopped session should raise."""
        session = service.start_session("room_001", session_config)
        service.stop_session(session.session_id)

        with pytest.raises(AppError) as exc:
            await service.process_danmaku(
                session_id=session.session_id,
                danmaku_id="dm_005",
                text="你好",
                platform_user_id="user_005",
            )
        assert "not running" in exc.value.message.lower()

    # ── Session Stats ──

    @pytest.mark.asyncio
    async def test_session_stats_tracked(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Session stats should be updated after processing danmaku."""
        # Seed existing users so greetings don't auto-upgrade to VOICE
        service._profile.seed("user_011", {
            "is_new": False, "is_vip": False, "purchase_count": 1,
        })
        session = service.start_session("room_001", session_config)

        await service.process_danmaku(
            session_id=session.session_id,
            danmaku_id="dm_010",
            text="多少钱",
            platform_user_id="user_010",
        )
        await service.process_danmaku(
            session_id=session.session_id,
            danmaku_id="dm_011",
            text="大家好",
            platform_user_id="user_011",
        )
        await service.process_danmaku(
            session_id=session.session_id,
            danmaku_id="dm_012",
            text="今天天气真好",
            platform_user_id="user_012",
        )

        updated = service.get_session(session.session_id)
        assert updated.stats.total_danmaku == 3
        assert updated.stats.voice_replies >= 1  # purchase intent
        assert updated.stats.text_replies >= 1  # greeting from existing user
        assert updated.stats.ignored_messages >= 1  # other
        assert updated.stats.avg_latency_ms > 0

    # ── VIP Routing ──

    @pytest.mark.asyncio
    async def test_vip_gets_voice_for_greeting(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """VIP user's greeting should be upgraded to VOICE."""
        # Seed VIP profile
        service._profile.seed("douyin:vip_user", {
            "is_vip": True,
            "is_new": False,
            "purchase_count": 5,
            "total_spent": 1500.0,
        })

        session = service.start_session("room_001", session_config)
        reply = await service.process_danmaku(
            session_id=session.session_id,
            danmaku_id="dm_020",
            text="大家好",
            platform_user_id="vip_user",
            platform="douyin",
        )
        assert reply.channel == Channel.VOICE, "VIP greeting should be upgraded to VOICE"

    # ── Moderator Actions ──

    @pytest.mark.asyncio
    async def test_moderator_interval(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Moderator on_interval should return a comment action."""
        session = service.start_session("room_001", session_config)
        action = await service.get_moderator_action(
            session_id=session.session_id,
            trigger_event="interval",
            context={"interval_seconds": "0", "product_title": "测试商品"},
        )
        assert action.action_type == ModeratorActionType.SEND_COMMENT
        assert len(action.comment_text) > 0

    @pytest.mark.asyncio
    async def test_moderator_negative_comment(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Moderator negative comment handler should hide and soothe."""
        session = service.start_session("room_001", session_config)
        action = await service.get_moderator_action(
            session_id=session.session_id,
            trigger_event="negative_comment",
            context={
                "comment_id": "cmt_999",
                "sentiment": str(nlp_pb2.SENTIMENT_NEGATIVE),
                "intensity": "0.9",
            },
        )
        assert action.action_type == ModeratorActionType.HIDE_COMMENT

    @pytest.mark.asyncio
    async def test_moderator_low_engagement(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Moderator low engagement handler should send prompt."""
        session = service.start_session("room_001", session_config)
        action = await service.get_moderator_action(
            session_id=session.session_id,
            trigger_event="low_engagement",
            context={
                "current_interaction_rate": "0.01",
                "threshold": "0.1",
            },
        )
        assert action.action_type == ModeratorActionType.SEND_COMMENT
        assert "问题" in action.comment_text

    # ── Standalone Route ──

    def test_standalone_route(self, service: InteractionService) -> None:
        """Standalone route_channel should work correctly."""
        result = service.route_channel(
            text="多少钱",
            intent=nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT,
            confidence=0.9,
        )
        assert result.channel == Channel.VOICE

        result = service.route_channel(
            text="你好",
            intent=nlp_pb2.INTENT_CATEGORY_GREETING,
            confidence=0.9,
            user_tags={"is_vip": True},
        )
        assert result.channel == Channel.VOICE  # VIP upgrade

    # ── Edge Cases ──

    @pytest.mark.asyncio
    async def test_consecutive_danmaku(
        self, service: InteractionService, session_config: SessionConfig
    ) -> None:
        """Multiple danmaku in sequence should all be processed."""
        session = service.start_session("room_001", session_config)
        for i in range(5):
            reply = await service.process_danmaku(
                session_id=session.session_id,
                danmaku_id=f"dm_batch_{i}",
                text=f"测试消息{i}",
                platform_user_id=f"user_{i}",
            )
            assert reply.reply_id.startswith("rep_")

    def test_nlp_mock_mappings(self) -> None:
        """Verify that _mock_nlp_analysis covers all expected intents."""
        test_cases = [
            ("怎么买", nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT),
            ("太贵了", nlp_pb2.INTENT_CATEGORY_BARGAIN),
            ("这是什么", nlp_pb2.INTENT_CATEGORY_QUESTION),
            ("质量太差了", nlp_pb2.INTENT_CATEGORY_COMPLAINT),
            ("你好", nlp_pb2.INTENT_CATEGORY_GREETING),
            ("真好看", nlp_pb2.INTENT_CATEGORY_PRAISE),
            ("对比一下这两个", nlp_pb2.INTENT_CATEGORY_COMPARE),
            ("讲解一下", nlp_pb2.INTENT_CATEGORY_REQUEST_DEMO),
            ("保修期多久", nlp_pb2.INTENT_CATEGORY_AFTERSALES),
            ("快点上", nlp_pb2.INTENT_CATEGORY_URGE),
            ("random text", nlp_pb2.INTENT_CATEGORY_OTHER),
        ]

        for text, expected_intent in test_cases:
            result = InteractionService._mock_nlp_analysis(text)
            assert result["intent"] == expected_intent, (
                f"Text '{text}' → expected {nlp_pb2.IntentCategory.Name(expected_intent)}, "
                f"got {nlp_pb2.IntentCategory.Name(result['intent'])}"
            )
