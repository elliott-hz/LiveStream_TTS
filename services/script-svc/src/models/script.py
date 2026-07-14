"""
SQLAlchemy ORM models for Script Service.

Script — main entity with versioning and status workflow.
ScriptSection — ordered sections within a script.
ScriptVersion — version snapshots for rollback.
ScriptTemplate — built-in industry templates (reference data, not stored in DB).
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy import Uuid as SA_Uuid
from sqlalchemy.orm import relationship

from libs.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Script(Base):
    __tablename__ = "scripts"

    script_id = Column(SA_Uuid(), primary_key=True, default=uuid.uuid4)
    product_id = Column(String(128), nullable=False, index=True)
    store_id = Column(String(128), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    status = Column(
        String(32),
        nullable=False,
        default="draft",
        index=True,
    )
    style = Column(String(32), nullable=False, default="passionate")
    industry = Column(String(64), nullable=False, default="")
    total_duration_estimate_ms = Column(Integer, nullable=False, default=0)
    ai_generated_prompt = Column(Text, nullable=True)
    created_by = Column(String(128), nullable=True)
    updated_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    sections = relationship(
        "ScriptSection",
        back_populates="script",
        cascade="all, delete-orphan",
        order_by="ScriptSection.order",
    )
    versions = relationship(
        "ScriptVersion",
        back_populates="script",
        cascade="all, delete-orphan",
        order_by="ScriptVersion.version_number.desc()",
    )

    def __repr__(self) -> str:
        return f"<Script {self.script_id} v{self.version} [{self.status}]>"


class ScriptSection(Base):
    __tablename__ = "script_sections"

    section_id = Column(SA_Uuid(), primary_key=True, default=uuid.uuid4)
    script_id = Column(
        SA_Uuid(), ForeignKey("scripts.script_id", ondelete="CASCADE"), nullable=False
    )
    order = Column(Integer, nullable=False)
    type = Column(String(32), nullable=False)
    text = Column(Text, nullable=False, default="")
    duration_estimate_ms = Column(Integer, nullable=False, default=0)
    emotion = Column(String(32), nullable=True, default="neutral")
    action = Column(String(32), nullable=True, default="")
    show_product_card = Column(Boolean, nullable=False, default=False)
    highlight_selling_point = Column(String(256), nullable=True)

    script = relationship("Script", back_populates="sections")

    def __repr__(self) -> str:
        return f"<ScriptSection #{self.order} [{self.type}]>"


class ScriptVersion(Base):
    __tablename__ = "script_versions"

    version_id = Column(SA_Uuid(), primary_key=True, default=uuid.uuid4)
    script_id = Column(
        SA_Uuid(), ForeignKey("scripts.script_id", ondelete="CASCADE"), nullable=False
    )
    version_number = Column(Integer, nullable=False)
    sections_snapshot = Column(JSON, nullable=False, default=list)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    script = relationship("Script", back_populates="versions")

    def __repr__(self) -> str:
        return f"<ScriptVersion v{self.version_number} [{self.script_id}]>"


# ── ScriptTemplate (in-memory reference data, no DB table) ──

class ScriptTemplateData:
    """Represents a built-in industry script template.

    Stored in memory / config rather than the database because templates
    are curated by the platform and rarely change.
    """

    def __init__(
        self,
        template_id: str,
        name: str,
        industry: str,
        style: str,
        template_sections: list[dict[str, Any]],
        description: str,
    ):
        self.template_id = template_id
        self.name = name
        self.industry = industry
        self.style = style
        self.template_sections = template_sections
        self.description = description

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "industry": self.industry,
            "style": self.style,
            "template_sections": self.template_sections,
            "description": self.description,
        }
