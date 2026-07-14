"""
KnowledgeService — business logic for Knowledge Base CRUD,
document upload, FAQ management, and vector search.

Phase 2 upgrade: replaces mock keyword search with real vector search
using configurable embedding + vector store backends.
"""

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError, ErrorCode, not_found, invalid_arg
from libs.common.logging import get_logger

from models.knowledge import KnowledgeBase, Document, FAQ, Chunk
from .embedding_service import EmbeddingBackend, HashEmbedding
from .vector_store import VectorStore, MemoryVectorStore, VectorSearchResponse

logger = get_logger(__name__)

# ── Constants ──

VALID_KB_STATUSES = {"active", "building", "error"}
VALID_DOC_STATUSES = {"uploading", "chunking", "embedding", "ready", "failed"}
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class KnowledgeService:
    """Knowledge Base business logic — injected with a DB session.

    Phase 2: supports vector search via pluggable embedding + vector store.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding: EmbeddingBackend | None = None,
        vector_store: VectorStore | None = None,
    ):
        self.db = db
        self.embedding = embedding or HashEmbedding()
        self.vector_store = vector_store or MemoryVectorStore()

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
    #  Search (vector + keyword hybrid)
    # ──────────────────────────────────────────────────────────

    async def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> dict[str, Any]:
        """Vector search on knowledge base chunks.

        Pipeline:
        1. Embed query text → vector
        2. Search vector store for similar chunks
        3. Augment results with source document metadata
        4. Fall back to keyword search if vector store is empty

        Returns dict with ``results`` list and ``retrieval_ms``.
        """
        await self.get_kb(kb_id)

        if not query or not query.strip():
            raise invalid_arg("query", "must not be empty")

        top_k = max(1, min(top_k, 50))

        # Step 1: Embed the query
        try:
            query_vec = await self.embedding.embed(query.strip())
        except Exception as e:
            logger.warning("kb.search.embed_failed", error=str(e), query=query[:50])
            return await self._keyword_search_fallback(kb_id, query, top_k, min_score)

        # Step 2: Vector search
        try:
            response: VectorSearchResponse = await self.vector_store.search(
                query_vector=query_vec,
                top_k=top_k,
                min_score=min_score,
            )
        except Exception as e:
            logger.warning("kb.search.vector_search_failed", error=str(e))
            return await self._keyword_search_fallback(kb_id, query, top_k, min_score)

        # If vector store returned nothing (empty store), fall back to keyword
        if not response.results and self.vector_store.size == 0:
            return await self._keyword_search_fallback(kb_id, query, top_k, min_score)

        # Step 3: Augment with source document metadata from DB
        results = []
        for hit in response.results:
            result = {
                "chunk_id": hit.chunk_id,
                "content": hit.content,
                "score": hit.score,
                "source_doc_id": hit.doc_id,
                "source_filename": hit.metadata.get("filename", ""),
            }

            # If doc info not in vector metadata, fetch from DB
            if not result["source_filename"] and hit.doc_id:
                doc_stmt = select(Document).where(Document.doc_id == hit.doc_id)
                doc_result = await self.db.execute(doc_stmt)
                doc = doc_result.scalars().one_or_none()
                if doc:
                    result["source_filename"] = doc.filename

            results.append(result)

        logger.debug(
            "kb.search.complete",
            kb_id=kb_id,
            query=query[:80],
            hits=len(results),
            backend=response.backend,
            retrieval_ms=response.retrieval_ms,
        )

        return {
            "results": results,
            "retrieval_ms": response.retrieval_ms,
            "backend": response.backend,
        }

    async def _keyword_search_fallback(
        self,
        kb_id: str,
        query: str,
        top_k: int,
        min_score: float,
    ) -> dict[str, Any]:
        """Fallback: keyword matching on DB chunks."""
        import time
        start = time.monotonic()

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
            .limit(top_k * 3)
        )
        result = await self.db.execute(stmt)
        chunks = list(result.scalars().all())

        scored = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            match_count = sum(content_lower.count(kw) for kw in keywords)
            score = min(1.0, match_count / max(len(chunk.content.split()), 1))
            if score >= min_score:
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

        scored.sort(key=lambda x: x["score"], reverse=True)
        scored = scored[:top_k]
        retrieval_ms = (time.monotonic() - start) * 1000

        return {
            "results": scored,
            "retrieval_ms": round(retrieval_ms, 2),
            "backend": "keyword_fallback",
        }

    # ──────────────────────────────────────────────────────────
    #  Index (build vector index for a knowledge base)
    # ──────────────────────────────────────────────────────────

    async def index_kb(self, kb_id: str) -> dict[str, Any]:
        """Index all chunks in a knowledge base into the vector store.

        This should be called after uploading documents to enable
        vector search for the knowledge base.
        """
        await self.get_kb(kb_id)

        # Fetch all chunks for this KB
        stmt = (
            select(Chunk)
            .where(Chunk.kb_id == kb_id)
            .order_by(Chunk.chunk_index)
        )
        result = await self.db.execute(stmt)
        chunks = list(result.scalars().all())

        if not chunks:
            return {"indexed": 0, "message": "No chunks to index"}

        # Embed all chunks in batches
        texts = [chunk.content for chunk in chunks]
        try:
            vectors = await self.embedding.embed_batch(texts)
        except Exception as e:
            logger.error("kb.index.embed_failed", error=str(e))
            return {"indexed": 0, "error": str(e)}

        # Insert into vector store
        doc_ids = [chunk.doc_id for chunk in chunks]
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        contents = [chunk.content for chunk in chunks]

        count = await self.vector_store.insert(
            vectors=vectors,
            doc_ids=doc_ids,
            chunk_ids=chunk_ids,
            contents=contents,
        )

        logger.info(
            "kb.indexed",
            kb_id=kb_id,
            chunks=count,
            vector_store_size=self.vector_store.size,
        )

        return {"indexed": count}


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
