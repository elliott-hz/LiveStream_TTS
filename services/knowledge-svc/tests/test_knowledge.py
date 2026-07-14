"""
Integration tests: Knowledge Base CRUD, document upload, FAQ management, and search.
"""

import pytest
from sqlalchemy import select

from models.knowledge import Document
from services.knowledge_service import KnowledgeService


@pytest.mark.asyncio
async def test_create_kb(db_session):
    """Create a knowledge base and verify it's persisted."""
    svc = KnowledgeService(db=db_session)
    kb = await svc.create_kb(
        store_id="store_001",
        name="测试知识库A",
        description="这是一个测试知识库",
        industry="服装",
    )
    assert kb.kb_id is not None
    assert kb.name == "测试知识库A"
    assert kb.store_id == "store_001"
    assert kb.industry == "服装"
    assert kb.status == "active"
    assert kb.document_count == 0
    assert kb.faq_count == 0
    assert kb.created_at is not None


@pytest.mark.asyncio
async def test_get_kb(db_session):
    """Create and then fetch a KB by ID."""
    svc = KnowledgeService(db=db_session)
    created = await svc.create_kb(
        store_id="store_001",
        name="可查询的知识库",
    )
    fetched = await svc.get_kb(created.kb_id)
    assert fetched.kb_id == created.kb_id
    assert fetched.name == "可查询的知识库"


@pytest.mark.asyncio
async def test_get_kb_not_found(db_session):
    """Fetching a non-existent KB should raise AppError."""
    svc = KnowledgeService(db=db_session)
    with pytest.raises(Exception) as excinfo:
        await svc.get_kb("non_existent_id")
    assert "not found" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_list_kbs(db_session):
    """List knowledge bases with pagination."""
    svc = KnowledgeService(db=db_session)
    for i in range(5):
        await svc.create_kb(
            store_id="store_001",
            name=f"知识库{i}",
        )

    # All KBs
    kbs, total = await svc.list_kbs(store_id="store_001")
    assert total == 5
    assert len(kbs) == 5

    # Pagination
    kbs, total = await svc.list_kbs(store_id="store_001", page=1, page_size=2)
    assert len(kbs) == 2
    assert total == 5

    # Different store
    kbs, total = await svc.list_kbs(store_id="store_002")
    assert total == 0


@pytest.mark.asyncio
async def test_delete_kb(db_session):
    """Delete a KB and verify it's gone."""
    svc = KnowledgeService(db=db_session)
    kb = await svc.create_kb(
        store_id="store_001", name="待删除知识库"
    )
    await svc.delete_kb(kb.kb_id)

    with pytest.raises(Exception) as excinfo:
        await svc.get_kb(kb.kb_id)
    assert "not found" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_upload_and_delete_document(db_session):
    """Upload a document to a KB and then delete it."""
    svc = KnowledgeService(db=db_session)
    kb = await svc.create_kb(
        store_id="store_001", name="含文档的知识库"
    )

    # Upload document
    doc = await svc.upload_document(
        kb_id=kb.kb_id,
        filename="products.txt",
        content="连衣裙 T恤 牛仔裤 外套\n热卖商品 新款上市".encode("utf-8"),
    )
    assert doc.doc_id is not None
    assert doc.filename == "products.txt"
    assert doc.status == "ready"
    assert doc.chunk_count > 0

    # KB counters updated
    updated_kb = await svc.get_kb(kb.kb_id)
    assert updated_kb.document_count == 1
    assert updated_kb.total_chunks == doc.chunk_count

    # Delete document
    await svc.delete_document(doc.doc_id)

    # Verify the document is gone
    stmt = select(Document).where(Document.doc_id == doc.doc_id)  # type: ignore
    result = await db_session.execute(stmt)
    assert result.scalars().one_or_none() is None

    # KB counter decremented
    updated_kb2 = await svc.get_kb(kb.kb_id)
    assert updated_kb2.document_count == 0


@pytest.mark.asyncio
async def test_faq_crud(db_session):
    """Create, list, and delete FAQs."""
    svc = KnowledgeService(db=db_session)
    kb = await svc.create_kb(
        store_id="store_001", name="含FAQ的知识库"
    )

    # Create FAQs
    faq1 = await svc.create_faq(
        kb_id=kb.kb_id,
        question="你们有什么商品？",
        answer="我们主打服装类商品，包括连衣裙、T恤等。",
        tags=["服装", "商品"],
    )
    assert faq1.faq_id is not None
    assert faq1.question == "你们有什么商品？"
    assert faq1.tags == ["服装", "商品"]

    faq2 = await svc.create_faq(
        kb_id=kb.kb_id,
        question="发货时间？",
        answer="下单后48小时内发货。",
        tags=["物流"],
    )

    # List FAQs
    faqs, total = await svc.list_faqs(kb_id=kb.kb_id)
    assert total == 2
    assert len(faqs) == 2

    # KB faq_count updated
    updated_kb = await svc.get_kb(kb.kb_id)
    assert updated_kb.faq_count == 2

    # Delete FAQ
    await svc.delete_faq(faq1.faq_id)
    faqs, total = await svc.list_faqs(kb_id=kb.kb_id)
    assert total == 1


@pytest.mark.asyncio
async def test_search(db_session):
    """Mock vector search on document chunks."""
    svc = KnowledgeService(db=db_session)
    kb = await svc.create_kb(
        store_id="store_001", name="可搜索的知识库"
    )

    # Upload a document with content
    await svc.upload_document(
        kb_id=kb.kb_id,
        filename="products.txt",
        content="连衣裙是夏季热卖商品，采用优质棉料制成。"
        "T恤是百搭单品，适合各种场合。"
        "牛仔裤经典不过时，永不过时的时尚单品。".encode("utf-8"),
    )

    # Search
    result = await svc.search(
        kb_id=kb.kb_id,
        query="连衣裙",
        top_k=3,
        min_score=0.0,
    )
    assert "results" in result
    assert len(result["results"]) > 0
    assert result["retrieval_ms"] > 0

    # Verify result content
    first = result["results"][0]
    assert "chunk_id" in first
    assert "content" in first
    assert "score" in first
    assert first["score"] > 0

    # Search with score threshold
    result_high = await svc.search(
        kb_id=kb.kb_id,
        query="连衣裙",
        top_k=3,
        min_score=0.5,
    )
    # Some results may be filtered out
    assert "results" in result_high


@pytest.mark.asyncio
async def test_create_kb_invalid(db_session):
    """Creating a KB without required fields should raise."""
    svc = KnowledgeService(db=db_session)
    with pytest.raises(Exception) as excinfo:
        await svc.create_kb(store_id="", name="")
    assert "store_id" in str(excinfo.value).lower() or "name" in str(excinfo.value).lower()
