"""
FastAPI HTTP routes for knowledge-svc.

Provides REST-style endpoints mirroring the gRPC API for health checks and external integrations.
"""

from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError
from libs.common.logging import get_logger

from models.knowledge import KnowledgeBase, Document, FAQ
from services.knowledge_service import KnowledgeService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1")

_get_db: Any = None


def configure_routes(get_db_callable: Any) -> None:
    """Wire the database session factory into routes."""
    global _get_db
    _get_db = get_db_callable


async def _get_service() -> AsyncIterator[KnowledgeService]:
    """FastAPI dependency: yield a KnowledgeService with a request-scoped session."""
    if _get_db is None:
        raise RuntimeError("Routes not configured — call configure_routes first")
    async with _get_db() as session:
        yield KnowledgeService(db=session)


# ── Health ──


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "knowledge-svc"}


# ── Knowledge Bases ──


@router.get("/knowledge-bases")
async def list_kbs(
    store_id: str = Query(..., description="Store ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: KnowledgeService = Depends(_get_service),
) -> dict[str, Any]:
    """List knowledge bases with pagination."""
    try:
        kbs, total = await svc.list_kbs(
            store_id=store_id,
            page=page,
            page_size=page_size,
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)

    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "knowledge_bases": [_kb_dict(kb) for kb in kbs],
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": total_pages,
        },
    }


@router.post("/knowledge-bases", status_code=201)
async def create_kb(
    body: dict[str, Any],
    svc: KnowledgeService = Depends(_get_service),
) -> dict[str, Any]:
    """Create a new knowledge base."""
    try:
        kb = await svc.create_kb(
            store_id=body.get("store_id", ""),
            name=body.get("name", ""),
            description=body.get("description"),
            industry=body.get("industry"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _kb_dict(kb)


@router.get("/knowledge-bases/{kb_id}")
async def get_kb(
    kb_id: str,
    svc: KnowledgeService = Depends(_get_service),
) -> dict[str, Any]:
    """Get a single knowledge base by ID."""
    try:
        kb = await svc.get_kb(kb_id=kb_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _kb_dict(kb)


@router.delete("/knowledge-bases/{kb_id}", status_code=204)
async def delete_kb(
    kb_id: str,
    svc: KnowledgeService = Depends(_get_service),
) -> None:
    """Delete a knowledge base."""
    try:
        await svc.delete_kb(kb_id=kb_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)


# ── Documents ──


@router.post("/knowledge-bases/{kb_id}/documents", status_code=201)
async def upload_document(
    kb_id: str,
    body: dict[str, Any],
    svc: KnowledgeService = Depends(_get_service),
) -> dict[str, Any]:
    """Upload a document to a knowledge base."""
    try:
        doc = await svc.upload_document(
            kb_id=kb_id,
            filename=body.get("filename", ""),
            content=body.get("content", "").encode("utf-8") if body.get("content") else None,
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _document_dict(doc)


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    svc: KnowledgeService = Depends(_get_service),
) -> None:
    """Delete a document."""
    try:
        await svc.delete_document(doc_id=doc_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)


# ── FAQs ──


@router.get("/knowledge-bases/{kb_id}/faqs")
async def list_faqs(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    svc: KnowledgeService = Depends(_get_service),
) -> dict[str, Any]:
    """List FAQs for a knowledge base."""
    try:
        faqs, total = await svc.list_faqs(
            kb_id=kb_id,
            page=page,
            page_size=page_size,
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)

    total_pages = max(1, (total + page_size - 1) // page_size)
    return {
        "faqs": [_faq_dict(faq) for faq in faqs],
        "page_info": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": total_pages,
        },
    }


@router.post("/knowledge-bases/{kb_id}/faqs", status_code=201)
async def create_faq(
    kb_id: str,
    body: dict[str, Any],
    svc: KnowledgeService = Depends(_get_service),
) -> dict[str, Any]:
    """Create a FAQ entry."""
    try:
        faq = await svc.create_faq(
            kb_id=kb_id,
            question=body.get("question", ""),
            answer=body.get("answer", ""),
            tags=body.get("tags"),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return _faq_dict(faq)


@router.delete("/faqs/{faq_id}", status_code=204)
async def delete_faq(
    faq_id: str,
    svc: KnowledgeService = Depends(_get_service),
) -> None:
    """Delete a FAQ entry."""
    try:
        await svc.delete_faq(faq_id=faq_id)
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)


# ── Search ──


@router.post("/knowledge-bases/{kb_id}/search")
async def search(
    kb_id: str,
    body: dict[str, Any],
    svc: KnowledgeService = Depends(_get_service),
) -> dict[str, Any]:
    """Search a knowledge base (mock vector search)."""
    try:
        result = await svc.search(
            kb_id=kb_id,
            query=body.get("query", ""),
            top_k=body.get("top_k", 5),
            min_score=body.get("min_score", 0.0),
        )
    except AppError as exc:
        raise HTTPException(status_code=_app_error_status(exc), detail=exc.message)
    return result


# ── Converters ──


def _kb_dict(kb: KnowledgeBase) -> dict[str, Any]:
    return {
        "kb_id": kb.kb_id,
        "store_id": kb.store_id,
        "name": kb.name,
        "description": kb.description or "",
        "industry": kb.industry or "",
        "document_count": kb.document_count or 0,
        "faq_count": kb.faq_count or 0,
        "total_chunks": kb.total_chunks or 0,
        "status": kb.status,
        "created_by": kb.created_by or "",
        "updated_by": kb.updated_by or "",
        "created_at": int(kb.created_at.timestamp() * 1000),
        "updated_at": int(kb.updated_at.timestamp() * 1000),
    }


def _document_dict(doc: Document) -> dict[str, Any]:
    return {
        "doc_id": doc.doc_id,
        "kb_id": doc.kb_id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size_bytes": doc.file_size_bytes,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "created_by": doc.created_by or "",
        "updated_by": doc.updated_by or "",
        "created_at": int(doc.created_at.timestamp() * 1000),
        "updated_at": int(doc.updated_at.timestamp() * 1000),
    }


def _faq_dict(faq: FAQ) -> dict[str, Any]:
    return {
        "faq_id": faq.faq_id,
        "kb_id": faq.kb_id,
        "question": faq.question,
        "answer": faq.answer,
        "tags": list(faq.tags) if faq.tags else [],
        "created_by": faq.created_by or "",
        "updated_by": faq.updated_by or "",
        "created_at": int(faq.created_at.timestamp() * 1000),
        "updated_at": int(faq.updated_at.timestamp() * 1000),
    }


def _app_error_status(exc: AppError) -> int:
    code = exc.code.value if hasattr(exc.code, "value") else exc.code
    if 1001 <= code <= 1004:
        return 401 if code == 1001 else 403
    if 2001 <= code <= 2004:
        return 400
    if 3001 <= code <= 3008:
        return 404
    if 4001 <= code <= 4007:
        return 409
    return 500
