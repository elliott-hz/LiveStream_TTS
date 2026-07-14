"""
SQLAlchemy 2.0 ORM models for Voice/Timbre management.

Voice model stores voice metadata and clone task records.

Phase 2: Full training clone (CosyVoice2, 15min audio → 24h)
Phase 3: Few-shot clone (GPT-SoVITS / CosyVoice2 zero-shot, 3-10s audio)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Boolean, Float, func
from sqlalchemy.orm import Mapped, mapped_column

from libs.db import Base

try:
    from sqlalchemy.dialects.postgresql import JSON as _JSONType
except ImportError:
    from sqlalchemy import JSON as _JSONType  # type: ignore[assignment]


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.utcnow()


class Voice(Base):
    """Voice/Timbre master record.

    Supports:
      - Public voice library (pre-built voices)
      - Full training clone (Phase 2: 15min audio, CosyVoice2 fine-tune)
      - Few-shot clone (Phase 3: 3-10s audio, zero-shot speaker encoder)
    """

    __tablename__ = "voices"

    voice_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False, default="male")
    age_range: Mapped[str] = mapped_column(String(32), nullable=False, default="25-35")
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="zh-CN")
    style: Mapped[str] = mapped_column(
        String(32), nullable=False, default="professional",
        comment="VoiceStyle: passionate | professional | gentle | lively | authoritative",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True,
        comment="VoiceStatus: active | cloning | failed | pending_audit",
    )
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quality_metrics: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="VoiceQualityMetrics: mos_score, similarity_score, pronunciation_accuracy, evaluated_at",
    )
    # ── Clone-related (Phase 2/3) ──
    clone_method: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="CloneMethod: full_training | few_shot | speaker_encoder",
    )
    speaker_embedding_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="MinIO URL of speaker embedding vector file (Phase 2/3)",
    )
    few_shot_config: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="FewShotConfig: reference_audio_duration_sec, reference_audio_url, reference_transcript, similarity_threshold",
    )
    prompt_audio_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="MinIO URL of uploaded prompt audio file",
    )
    preview_audio_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="MinIO URL of generated preview audio",
    )
    # ── Audit ──
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
        onupdate=_utcnow,
    )

    def __repr__(self) -> str:
        return f"<Voice {self.voice_id} '{self.name}' style={self.style}>"


class VoiceCloneTask(Base):
    """Voice clone task record.

    Tracks the full lifecycle of a voice cloning operation:
    uploading → preprocessing → training → evaluating → pending_audit → success/failed/cancelled.
    """

    __tablename__ = "voice_clone_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    voice_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="Tenant-scoped for queries",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploading",
        comment="CloneStatus: uploading | preprocessing | training | evaluating | pending_audit | success | failed | cancelled",
    )
    clone_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="full_training",
        comment="CloneMethod: full_training | few_shot | speaker_encoder",
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_audio_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="MinIO URL of uploaded source audio",
    )
    source_transcript: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Optional transcript for alignment",
    )
    clone_config: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="CloneConfig: enable_emotion_cloning, enable_style_transfer, target_sample_rate, emotion_presets",
    )
    quality_metrics: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="VoiceQualityMetrics populated on success",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:
        return f"<VoiceCloneTask {self.task_id} status={self.status} method={self.clone_method}>"
