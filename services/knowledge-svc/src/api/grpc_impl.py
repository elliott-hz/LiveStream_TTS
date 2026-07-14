"""
gRPC service implementation for KnowledgeService.

Maps each RPC to the corresponding KnowledgeService method.
Converts DB ORM models <-> proto messages.
Translates AppError exceptions to gRPC status codes.
"""

from typing import Any, Callable, Coroutine

import grpc
from grpc import aio

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

from knowledge.v1 import knowledge_pb2 as pb
from knowledge.v1 import knowledge_pb2_grpc as pb_grpc
from common.v1 import common_pb2 as common_pb

from models.knowledge import KnowledgeBase, Document, FAQ
from services.knowledge_service import KnowledgeService

logger = get_logger(__name__)

ServiceFactory = Callable[[], Coroutine[Any, Any, KnowledgeService]]


# ── Exception → gRPC error mapping ──

_ERROR_CODE_TO_GRPC: dict[ErrorCode, grpc.StatusCode] = {
    ErrorCode.UNAUTHENTICATED: grpc.StatusCode.UNAUTHENTICATED,
    ErrorCode.PERMISSION_DENIED: grpc.StatusCode.PERMISSION_DENIED,
    ErrorCode.INVALID_ARGUMENT: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.MISSING_REQUIRED_FIELD: grpc.StatusCode.INVALID_ARGUMENT,
    ErrorCode.NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.KNOWLEDGE_BASE_NOT_FOUND: grpc.StatusCode.NOT_FOUND,
    ErrorCode.DUPLICATE_RESOURCE: grpc.StatusCode.ALREADY_EXISTS,
    ErrorCode.INTERNAL_ERROR: grpc.StatusCode.INTERNAL,
    ErrorCode.DATABASE_ERROR: grpc.StatusCode.INTERNAL,
}


def _app_error_to_grpc_context(exc: AppError, context: aio.ServicerContext) -> None:
    grpc_code = _ERROR_CODE_TO_GRPC.get(exc.code, grpc.StatusCode.UNKNOWN)
    context.set_code(grpc_code)
    context.set_details(exc.message)
    error_proto = common_pb.Error(
        code=exc.full_code,
        message=exc.message,
        details=exc.details,
    )
    context.set_trailing_metadata(
        ("x-error-code", str(exc.full_code)),
        ("x-error-bin", error_proto.SerializeToString()),
    )


# ── Proto ↔ ORM converters ──


def _kb_to_proto(kb: KnowledgeBase) -> pb.KnowledgeBase:
    """Convert an ORM KnowledgeBase to a proto KnowledgeBase message."""
    audit = common_pb.AuditInfo(
        created_by=kb.created_by or "",
        updated_by=kb.updated_by or "",
        timestamps=common_pb.Timestamps(
            created_at=int(kb.created_at.timestamp() * 1000),
            updated_at=int(kb.updated_at.timestamp() * 1000),
        ),
    )

    return pb.KnowledgeBase(
        kb_id=kb.kb_id,
        store_id=kb.store_id,
        name=kb.name,
        description=kb.description or "",
        industry=kb.industry or "",
        document_count=kb.document_count or 0,
        faq_count=kb.faq_count or 0,
        total_chunks=kb.total_chunks or 0,
        status=_kb_status_to_proto(kb.status),
        audit_info=audit,
    )


def _document_to_proto(doc: Document) -> pb.Document:
    audit = common_pb.AuditInfo(
        created_by=doc.created_by or "",
        updated_by=doc.updated_by or "",
        timestamps=common_pb.Timestamps(
            created_at=int(doc.created_at.timestamp() * 1000),
            updated_at=int(doc.updated_at.timestamp() * 1000),
        ),
    )

    return pb.Document(
        doc_id=doc.doc_id,
        kb_id=doc.kb_id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        chunk_count=doc.chunk_count,
        status=_doc_status_to_proto(doc.status),
        audit_info=audit,
    )


def _faq_to_proto(faq: FAQ) -> pb.FAQ:
    audit = common_pb.AuditInfo(
        created_by=faq.created_by or "",
        updated_by=faq.updated_by or "",
        timestamps=common_pb.Timestamps(
            created_at=int(faq.created_at.timestamp() * 1000),
            updated_at=int(faq.updated_at.timestamp() * 1000),
        ),
    )

    return pb.FAQ(
        faq_id=faq.faq_id,
        kb_id=faq.kb_id,
        question=faq.question,
        answer=faq.answer,
        tags=list(faq.tags) if faq.tags else [],
        audit_info=audit,
    )


# ── Enum converters ──

_MAP_KB_STATUS = {
    "active": pb.KBStatus.KB_STATUS_ACTIVE,
    "building": pb.KBStatus.KB_STATUS_BUILDING,
    "error": pb.KBStatus.KB_STATUS_ERROR,
}
_REV_KB_STATUS = {v: k for k, v in _MAP_KB_STATUS.items()}


def _kb_status_to_proto(s: str) -> pb.KBStatus:
    return _MAP_KB_STATUS.get(s, pb.KBStatus.KB_STATUS_UNSPECIFIED)


def _kb_status_from_proto(s: pb.KBStatus) -> str:
    return _REV_KB_STATUS.get(s, "active")


_MAP_DOC_STATUS = {
    "uploading": pb.DocStatus.DOC_STATUS_UPLOADING,
    "chunking": pb.DocStatus.DOC_STATUS_CHUNKING,
    "embedding": pb.DocStatus.DOC_STATUS_EMBEDDING,
    "ready": pb.DocStatus.DOC_STATUS_READY,
    "failed": pb.DocStatus.DOC_STATUS_FAILED,
}
_REV_DOC_STATUS = {v: k for k, v in _MAP_DOC_STATUS.items()}


def _doc_status_to_proto(s: str) -> pb.DocStatus:
    return _MAP_DOC_STATUS.get(s, pb.DocStatus.DOC_STATUS_UNSPECIFIED)


def _doc_status_from_proto(s: pb.DocStatus) -> str:
    return _REV_DOC_STATUS.get(s, "uploading")


# ── Servicer ──


class KnowledgeServiceServicer(pb_grpc.KnowledgeServiceServicer):
    """gRPC servicer that delegates to KnowledgeService for business logic."""

    def __init__(self, knowledge_service_factory: ServiceFactory) -> None:
        self._svc_factory = knowledge_service_factory

    async def _svc(self) -> KnowledgeService:
        return await self._svc_factory()

    async def _run(
        self,
        handler,
        request,
        context: aio.ServicerContext,
    ) -> Any:
        try:
            svc = await self._svc()
            return await handler(svc, request)
        except AppError as exc:
            _app_error_to_grpc_context(exc, context)
            return None
        except Exception as exc:
            logger.exception("grpc.handler_error", method=context.method)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return None

    # ── Knowledge Base ──

    async def CreateKB(
        self,
        request: pb.CreateKBRequest,
        context: aio.ServicerContext,
    ) -> pb.KnowledgeBase:
        async def handler(svc: KnowledgeService, req: pb.CreateKBRequest) -> pb.KnowledgeBase:
            kb = await svc.create_kb(
                store_id=req.store_id,
                name=req.name,
                description=req.description or None,
                industry=req.industry or None,
            )
            return _kb_to_proto(kb)

        return await self._run(handler, request, context)

    async def GetKB(
        self,
        request: pb.GetKBRequest,
        context: aio.ServicerContext,
    ) -> pb.KnowledgeBase:
        async def handler(svc: KnowledgeService, req: pb.GetKBRequest) -> pb.KnowledgeBase:
            kb = await svc.get_kb(kb_id=req.kb_id)
            return _kb_to_proto(kb)

        return await self._run(handler, request, context)

    async def DeleteKB(
        self,
        request: pb.DeleteKBRequest,
        context: aio.ServicerContext,
    ) -> common_pb.Error:
        async def handler(svc: KnowledgeService, req: pb.DeleteKBRequest) -> common_pb.Error:
            await svc.delete_kb(kb_id=req.kb_id)
            return common_pb.Error(code=0, message="ok")

        return await self._run(handler, request, context)

    async def ListKBs(
        self,
        request: pb.ListKBsRequest,
        context: aio.ServicerContext,
    ) -> pb.ListKBsResponse:
        async def handler(
            svc: KnowledgeService,
            req: pb.ListKBsRequest,
        ) -> pb.ListKBsResponse:
            pagination = req.pagination
            page = pagination.page if pagination and pagination.page else 1
            page_size = pagination.page_size if pagination and pagination.page_size else 20

            kbs, total_count = await svc.list_kbs(
                store_id=req.store_id,
                page=page,
                page_size=page_size,
            )
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            return pb.ListKBsResponse(
                kbs=[_kb_to_proto(kb) for kb in kbs],
                page_info=common_pb.PageInfo(
                    page=page,
                    page_size=page_size,
                    total_count=total_count,
                    total_pages=total_pages,
                ),
            )

        return await self._run(handler, request, context)

    # ── Documents ──

    async def UploadDocument(
        self,
        request: pb.UploadDocumentRequest,
        context: aio.ServicerContext,
    ) -> pb.Document:
        async def handler(svc: KnowledgeService, req: pb.UploadDocumentRequest) -> pb.Document:
            doc = await svc.upload_document(
                kb_id=req.kb_id,
                filename=req.filename,
                content=req.content or None,
            )
            return _document_to_proto(doc)

        return await self._run(handler, request, context)

    async def DeleteDocument(
        self,
        request: pb.DeleteDocumentRequest,
        context: aio.ServicerContext,
    ) -> common_pb.Error:
        async def handler(svc: KnowledgeService, req: pb.DeleteDocumentRequest) -> common_pb.Error:
            await svc.delete_document(doc_id=req.doc_id)
            return common_pb.Error(code=0, message="ok")

        return await self._run(handler, request, context)

    # ── FAQ ──

    async def CreateFAQ(
        self,
        request: pb.CreateFAQRequest,
        context: aio.ServicerContext,
    ) -> pb.FAQ:
        async def handler(svc: KnowledgeService, req: pb.CreateFAQRequest) -> pb.FAQ:
            faq = await svc.create_faq(
                kb_id=req.kb_id,
                question=req.question,
                answer=req.answer,
                tags=list(req.tags) if req.tags else None,
            )
            return _faq_to_proto(faq)

        return await self._run(handler, request, context)

    async def DeleteFAQ(
        self,
        request: pb.DeleteFAQRequest,
        context: aio.ServicerContext,
    ) -> common_pb.Error:
        async def handler(svc: KnowledgeService, req: pb.DeleteFAQRequest) -> common_pb.Error:
            await svc.delete_faq(faq_id=req.faq_id)
            return common_pb.Error(code=0, message="ok")

        return await self._run(handler, request, context)

    async def ListFAQs(
        self,
        request: pb.ListFAQsRequest,
        context: aio.ServicerContext,
    ) -> pb.ListFAQsResponse:
        async def handler(
            svc: KnowledgeService,
            req: pb.ListFAQsRequest,
        ) -> pb.ListFAQsResponse:
            pagination = req.pagination
            page = pagination.page if pagination and pagination.page else 1
            page_size = pagination.page_size if pagination and pagination.page_size else 20

            faqs, total_count = await svc.list_faqs(
                kb_id=req.kb_id,
                page=page,
                page_size=page_size,
            )
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            return pb.ListFAQsResponse(
                faqs=[_faq_to_proto(faq) for faq in faqs],
                page_info=common_pb.PageInfo(
                    page=page,
                    page_size=page_size,
                    total_count=total_count,
                    total_pages=total_pages,
                ),
            )

        return await self._run(handler, request, context)

    # ── Search ──

    async def Search(
        self,
        request: pb.SearchRequest,
        context: aio.ServicerContext,
    ) -> pb.SearchResponse:
        async def handler(
            svc: KnowledgeService,
            req: pb.SearchRequest,
        ) -> pb.SearchResponse:
            result = await svc.search(
                kb_id=req.kb_id,
                query=req.query,
                top_k=req.top_k or 5,
                min_score=req.min_score or 0.0,
            )

            search_results = [
                pb.SearchResult(
                    chunk_id=r["chunk_id"],
                    content=r["content"],
                    score=r["score"],
                    source_doc_id=r["source_doc_id"],
                    source_filename=r["source_filename"],
                )
                for r in result["results"]
            ]

            return pb.SearchResponse(
                results=search_results,
                retrieval_ms=result["retrieval_ms"],
            )

        return await self._run(handler, request, context)
