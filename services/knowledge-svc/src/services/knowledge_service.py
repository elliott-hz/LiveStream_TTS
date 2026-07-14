"""
KnowledgeService — business logic for Knowledge Base CRUD,
document upload, FAQ management, and vector search (mock).
"""

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, ErrorCode, not_found, invalid_arg
from libs.common.logging import get_logger

from models.knowledge import KnowledgeBase, Document, FAQ, Chunk

logger = get_logger(__name__)

# ── Constants ──

VALID_KB_STATUSES = {"active", "building", "error"}
VALID_DOC_STATUSES = {"uploading", "chunking", "embedding", "ready", "failed"}
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class KnowledgeService:
    """Knowledge Base business logic — injected with a DB session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────────────────
    #  Knowledge Base CRUD
    # ──────────────────────────────────────────────────────────

    async def create_kb(
        self,
        store_id: str,
        name: str,
        description: str | None = None,
        industry: str | None = None,
        created_by: str | None = None,
    ) -> KnowledgeBase:
        """Create a new knowledge base."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")
        if not name or not name.strip():
            raise invalid_arg("name", "must not be empty")

        kb = KnowledgeBase(
            store_id=store_id,
            name=name.strip(),
            description=description,
            industry=industry,
            status="active",
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(kb)
        await self.db.flush()
        await self.db.refresh(kb)

        logger.info("kb.created", kb_id=kb.kb_id, store_id=store_id)
        return kb

    async def get_kb(self, kb_id: str) -> KnowledgeBase:
        """Fetch a single knowledge base by ID."""
        if not kb_id:
            raise invalid_arg("kb_id", "must not be empty")

        stmt = select(KnowledgeBase).where(KnowledgeBase.kb_id == kb_id)
        result = await self.db.execute(stmt)
        kb = result.scalars().one_or_none()
        if not kb:
            raise not_found("KnowledgeBase", kb_id)
        return kb

    async def delete_kb(self, kb_id: str) -> None:
        """Hard-delete a knowledge base and all its documents/FAQs/chunks."""
        kb = await self.get_kb(kb_id)

        # Delete associated chunks, documents, FAQs
        await self.db.execute(
            Chunk.__table__.delete().where(Chunk.kb_id == kb_id)  # type: ignore
        )
        await self.db.execute(
            Document.__table__.delete().where(Document.kb_id == kb_id)  # type: ignore
        )
        await self.db.execute(
            FAQ.__table__.delete().where(FAQ.kb_id == kb_id)  # type: ignore
        )
        await self.db.delete(kb)
        await self.db.flush()
        logger.info("kb.deleted", kb_id=kb_id)

    async def list_kbs(
        self,
        store_id: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[KnowledgeBase], int]:
        """Paginated KB listing."""
        if not store_id:
            raise invalid_arg("store_id", "must not be empty")

        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        conditions = [KnowledgeBase.store_id == store_id]

        count_stmt = select(func.count()).select_from(KnowledgeBase).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total_count: int = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(KnowledgeBase)
            .where(*conditions)
            .order_by(KnowledgeBase.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        kbs = list(result.scalars().all())

        return kbs, total_count

    # ──────────────────────────────────────────────────────────
    #  Document Management
    # ──────────────────────────────────────────────────────────

    async def upload_document(
        self,
        kb_id: str,
        filename: str,
        content: bytes | None = None,
        created_by: str | None = None,
    ) -> Document:
        """Upload a document to a knowledge base."""
        kb = await self.get_kb(kb_id)

        if not filename:
            raise invalid_arg("filename", "must not be empty")

        file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
        content_text = content.decode("utf-8", errors="replace") if content else ""

        doc = Document(
            kb_id=kb_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=len(content) if content else 0,
            status="ready",
            content_text=content_text,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(doc)
        await self.db.flush()

        # Simulate chunking: create mock chunks
        if content_text:
            chunks = _chunk_text(content_text, doc_id=doc.doc_id, kb_id=kb_id)
            for chunk in chunks:
                self.db.add(chunk)
            doc.chunk_count = len(chunks)
            kb.document_count = (kb.document_count or 0) + 1
            kb.total_chunks = (kb.total_chunks or 0) + len(chunks)

        await self.db.flush()
        await self.db.refresh(doc)
        logger.info("kb.document.uploaded", doc_id=doc.doc_id, kb_id=kb_id, filename=filename)
        return doc

    async def delete_document(self, doc_id: str) -> None:
        """Delete a document and its chunks."""
        stmt = select(Document).where(Document.doc_id == doc_id)
        result = await self.db.execute(stmt)
        doc = result.scalars().one_or_none()
        if not doc:
            raise not_found("Document", doc_id)

        # Delete chunks
        await self.db.execute(
            Chunk.__table__.delete().where(Chunk.doc_id == doc_id)  # type: ignore
        )

        # Update KB counters
        kb = await self.get_kb(doc.kb_id)
        kb.document_count = max(0, (kb.document_count or 0) - 1)
        kb.total_chunks = max(0, (kb.total_chunks or 0) - doc.chunk_count)

        await self.db.delete(doc)
        await self.db.flush()
        logger.info("kb.document.deleted", doc_id=doc_id)

    # ──────────────────────────────────────────────────────────
    #  FAQ Management
    # ──────────────────────────────────────────────────────────

    async def create_faq(
        self,
        kb_id: str,
        question: str,
        answer: str,
        tags: list[str] | None = None,
        created_by: str | None = None,
    ) -> FAQ:
        """Create a FAQ entry in a knowledge base."""
        kb = await self.get_kb(kb_id)

        if not question or not question.strip():
            raise invalid_arg("question", "must not be empty")
        if not answer or not answer.strip():
            raise invalid_arg("answer", "must not be empty")

        faq = FAQ(
            kb_id=kb_id,
            question=question.strip(),
            answer=answer.strip(),
            tags=tags or [],
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(faq)
        kb.faq_count = (kb.faq_count or 0) + 1
        await self.db.flush()
        await self.db.refresh(faq)
        logger.info("kb.faq.created", faq_id=faq.faq_id, kb_id=kb_id)
        return faq

    async def delete_faq(self, faq_id: str) -> None:
        """Delete a FAQ entry."""
        stmt = select(FAQ).where(FAQ.faq_id == faq_id)
        result = await self.db.execute(stmt)
        faq = result.scalars().one_or_none()
        if not faq:
            raise not_found("FAQ", faq_id)

        kb = await self.get_kb(faq.kb_id)
        kb.faq_count = max(0, (kb.faq_count or 0) - 1)

        await self.db.delete(faq)
        await self.db.flush()
        logger.info("kb.faq.deleted", faq_id=faq_id)

    async def list_faqs(
        self,
        kb_id: str,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[FAQ], int]:
        """Paginated FAQ listing for a KB."""
        await self.get_kb(kb_id)

        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        conditions = [FAQ.kb_id == kb_id]

        count_stmt = select(func.count()).select_from(FAQ).where(*conditions)
        total_result = await self.db.execute(count_stmt)
        total_count: int = total_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = (
            select(FAQ)
            .where(*conditions)
            .order_by(FAQ.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        faqs = list(result.scalars().all())

        return faqs, total_count

    # ──────────────────────────────────────────────────────────
    #  Search (mock vector search)
    # ──────────────────────────────────────────────────────────

    async def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> dict[str, Any]:
        """Mock vector search: fuzzy text match on chunks.

        Returns results list and simulated retrieval time.
        """
        await self.get_kb(kb_id)

        if not query or not query.strip():
            raise invalid_arg("query", "must not be empty")

        top_k = max(1, min(top_k, 50))

        # Simple keyword matching as mock vector search
        keywords = query.strip().lower().split()
        conditions = [Chunk.kb_id == kb_id]

        if keywords:
            keyword_conditions = []
            for kw in keywords:
                keyword_conditions.append(Chunk.content.ilike(f"%{kw}%"))
            conditions.append(or_(*keyword_conditions))

        stmt = (
            select(Chunk)
            .where(*conditions)
            .order_by(Chunk.chunk_index)
            .limit(top_k * 3)  # fetch extra for scoring
        )
        result = await self.db.execute(stmt)
        chunks = list(result.scalars().all())

        # Score results by keyword density
        scored = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            match_count = sum(content_lower.count(kw) for kw in keywords)
            score = min(1.0, match_count / max(len(chunk.content.split()), 1))

            if score >= min_score:
                # Fetch source document info
                doc_stmt = select(Document).where(Document.doc_id == chunk.doc_id)
                doc_result = await self.db.execute(doc_stmt)
                doc = doc_result.scalars().one_or_none()

                scored.append({
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "score": round(score, 4),
                    "source_doc_id": chunk.doc_id,
                    "source_filename": doc.filename if doc else "",
                })

        # Sort by score desc, take top_k
        scored.sort(key=lambda x: x["score"], reverse=True)
        scored = scored[:top_k]

        # Simulate retrieval time
        retrieval_ms = max(5, len(keywords) * 3 + len(chunks))

        return {
            "results": scored,
            "retrieval_ms": retrieval_ms,
        }


# ── Internal helpers ──


def _chunk_text(text: str, doc_id: str, kb_id: str, chunk_size: int = 500) -> list[Chunk]:
    """Split text into chunks, each ~chunk_size chars."""
    chunks = []
    start = 0
    index = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        content = text[start:end]

        # Generate a deterministic chunk_id from content hash
        chunk_id = f"chk_{hashlib.md5(f'{doc_id}_{index}'.encode()).hexdigest()[:12]}"

        chunk = Chunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            kb_id=kb_id,
            content=content,
            chunk_index=index,
            embedding=[0.0] * 128,  # mock embedding
        )
        chunks.append(chunk)
        start = end
        index += 1

    return chunks
