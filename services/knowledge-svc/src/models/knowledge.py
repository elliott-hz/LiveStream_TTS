"""
SQLAlchemy 2.0 ORM models for Knowledge Base management.

Models: KnowledgeBase, Document, FAQ, Chunk (for vector search mock).
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


class KnowledgeBase(Base):
    """Knowledge Base master record."""

    __tablename__ = "knowledge_bases"

    kb_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    faq_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", index=True
    )
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
        return f"<KnowledgeBase {self.kb_id} '{self.name}'>"


class Document(Base):
    """Document attached to a knowledge base."""

    __tablename__ = "kb_documents"

    doc_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    kb_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False, default="txt")
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="uploading"
    )
    content_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Extracted text content"
    )
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
        return f"<Document {self.doc_id} '{self.filename}'>"


class FAQ(Base):
    """FAQ entry in a knowledge base."""

    __tablename__ = "kb_faqs"

    faq_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    kb_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list | None] = mapped_column(
        _JSONType, nullable=True, comment="JSON array of tag strings"
    )
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
        return f"<FAQ {self.faq_id} '{self.question[:30]}'>"


class Chunk(Base):
    """Text chunk with embedding vector for search (mock)."""

    __tablename__ = "kb_chunks"

    chunk_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    doc_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kb_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(
        _JSONType, nullable=True, comment="Mock embedding vector"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Chunk {self.chunk_id} doc={self.doc_id}>"
