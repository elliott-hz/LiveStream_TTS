"""
SQLAlchemy 2.0 ORM models for Avatar management.

Avatar model stores digital human avatar metadata and clone task records.

Phase 2: 2D clone via GAN + FaceFormer
Phase 3: 3D clone via 3DGS / NeRF, 200+ customization params
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Float, Boolean, func
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


class Avatar(Base):
    """Digital Human Avatar master record.

    Supports 4 types:
      - 2d_real: LiveTalking / HeyGen-style 2D realistic (Phase 1/2)
      - 3d_cartoon: Unity/UE5 3D cartoon (Phase 1)
      - 2d_cartoon: 2D anime/cartoon (Phase 1)
      - 3d_real: Photorealistic 3D clone via 3DGS/NeRF (Phase 3)
    """

    __tablename__ = "avatars"

    avatar_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    avatar_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="2d_real",
        comment="AvatarType: 2d_real | 3d_cartoon | 2d_cartoon | 3d_real",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True,
        comment="AvatarStatus: active | cloning | pending_audit | rejected | training",
    )
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    model_path: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="MinIO path to model files (GAN checkpoint, 3DGS .ply, NeRF weights, etc.)",
    )
    custom_params: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="AvatarCustomParam: basic (4) + extended (8+) + free-form JSON for Phase 3 200+ params",
    )
    # ── Clone-related (Phase 2/3) ──
    clone_method: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="CloneMethod: gan_faceformer | 3dmm_recon | 3d_gaussian_splat | nerf",
    )
    source_person_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
        comment="Links cloned avatars to the source human for multi-avatar management",
    )
    source_video_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="MinIO URL of uploaded source video for cloning",
    )
    clone_quality: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="CloneQualityMetrics: fidelity_score, lip_sync_accuracy, expression_naturalness, motion_smoothness",
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
        return f"<Avatar {self.avatar_id} '{self.name}' type={self.avatar_type}>"


class CloneTask(Base):
    """Avatar clone task record.

    Tracks the full lifecycle of a cloning operation:
    uploading → preprocessing → training → evaluating → pending_audit → success/failed/cancelled.
    """

    __tablename__ = "avatar_clone_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    avatar_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    store_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="Tenant-scoped for queries",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploading",
        comment="CloneStatus: uploading | preprocessing | training | evaluating | pending_audit | success | failed | cancelled",
    )
    clone_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="gan_faceformer",
        comment="CloneMethod: gan_faceformer | 3dmm_recon | 3d_gaussian_splat | nerf",
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_video_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="MinIO URL of uploaded source video",
    )
    source_audio_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
        comment="Optional: MinIO URL of separate audio for voice sync",
    )
    clone_config: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="CloneConfig: video_duration_seconds, enable_expression_cloning, enable_gesture_cloning, output_fps, background_removal",
    )
    quality_metrics: Mapped[dict | None] = mapped_column(
        _JSONType, nullable=True,
        comment="CloneQualityMetrics populated on success: fidelity_score, lip_sync_accuracy, etc.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    def __repr__(self) -> str:
        return f"<CloneTask {self.task_id} status={self.status} method={self.clone_method}>"
