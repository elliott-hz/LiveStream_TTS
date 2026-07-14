"""
Vector store abstraction for knowledge base retrieval.

Backends:
  - ``memory`` — in-memory numpy cosine similarity (no external deps)
  - ``milvus`` — Milvus standalone via pymilvus
  - ``dashvector`` — Alibaba Cloud DashVector (production)

All backends implement the same interface for transparent switching.
"""

from __future__ import annotations

import logging
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from libs.common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VectorSearchResult:
    """A single vector search hit."""
    doc_id: str = ""
    chunk_id: str = ""
    content: str = ""
    score: float = 0.0        # cosine similarity, higher = better
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VectorSearchResponse:
    """Response from a vector search query."""
    results: list[VectorSearchResult] = field(default_factory=list)
    retrieval_ms: float = 0.0
    backend: str = ""


class VectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    async def insert(
        self,
        vectors: list[list[float]],
        doc_ids: list[str],
        chunk_ids: list[str],
        contents: list[str],
        metadata: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert vectors with metadata. Returns count inserted."""
        ...

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        min_score: float = 0.0,
        filter_expr: str | None = None,
    ) -> VectorSearchResponse:
        """Search for similar vectors. Returns ranked results."""
        ...

    @abstractmethod
    async def delete(self, chunk_ids: list[str]) -> int:
        """Delete vectors by chunk_id. Returns count deleted."""
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        """Whether the store is connected and ready."""
        ...


# ── In-Memory Vector Store ────────────────────────────────────


class MemoryVectorStore(VectorStore):
    """In-memory vector store using numpy for cosine similarity.

    Good for:
      - Development/testing without external services
      - Small knowledge bases (< 10k vectors)
      - Unit tests

    No external dependencies required.
    """

    def __init__(self, dim: int = 768) -> None:
        self.dim = dim
        self._vectors: list[list[float]] = []
        self._doc_ids: list[str] = []
        self._chunk_ids: list[str] = []
        self._contents: list[str] = []
        self._metadata: list[dict[str, Any]] = []

    def is_ready(self) -> bool:
        return True

    async def insert(
        self,
        vectors: list[list[float]],
        doc_ids: list[str],
        chunk_ids: list[str],
        contents: list[str],
        metadata: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert vectors into in-memory store."""
        meta = metadata or [{}] * len(chunk_ids)
        count = 0
        for i in range(len(vectors)):
            if len(vectors[i]) != self.dim:
                logger.warning(
                    "vector_store.dim_mismatch",
                    expected=self.dim,
                    got=len(vectors[i]),
                    chunk_id=chunk_ids[i],
                )
                continue
            self._vectors.append(vectors[i])
            self._doc_ids.append(doc_ids[i])
            self._chunk_ids.append(chunk_ids[i])
            self._contents.append(contents[i])
            self._metadata.append(meta[i] if i < len(meta) else {})
            count += 1

        logger.debug("memory_vs.inserted", count=count, total=len(self._vectors))
        return count

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        min_score: float = 0.0,
        filter_expr: str | None = None,
    ) -> VectorSearchResponse:
        """Search using cosine similarity."""
        start = time.monotonic()

        if not self._vectors:
            return VectorSearchResponse(
                retrieval_ms=round((time.monotonic() - start) * 1000, 2),
                backend="memory",
            )

        scores = self._cosine_similarity_batch(query_vector, self._vectors)

        # Rank by score descending
        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )

        results: list[VectorSearchResult] = []
        for idx, score in ranked:
            if score < min_score:
                continue
            if len(results) >= top_k:
                break
            results.append(VectorSearchResult(
                doc_id=self._doc_ids[idx],
                chunk_id=self._chunk_ids[idx],
                content=self._contents[idx],
                score=round(score, 4),
                metadata=self._metadata[idx],
            ))

        elapsed = (time.monotonic() - start) * 1000
        return VectorSearchResponse(
            results=results,
            retrieval_ms=round(elapsed, 2),
            backend="memory",
        )

    async def delete(self, chunk_ids: list[str]) -> int:
        """Delete vectors by chunk_id."""
        ids_to_delete = set(chunk_ids)
        indices_to_keep = [
            i for i, cid in enumerate(self._chunk_ids)
            if cid not in ids_to_delete
        ]
        deleted = len(self._chunk_ids) - len(indices_to_keep)

        self._vectors = [self._vectors[i] for i in indices_to_keep]
        self._doc_ids = [self._doc_ids[i] for i in indices_to_keep]
        self._chunk_ids = [self._chunk_ids[i] for i in indices_to_keep]
        self._contents = [self._contents[i] for i in indices_to_keep]
        self._metadata = [self._metadata[i] for i in indices_to_keep]

        return deleted

    @staticmethod
    def _cosine_similarity_batch(
        query: list[float],
        vectors: list[list[float]],
    ) -> list[float]:
        """Compute cosine similarity between query and all vectors.

        Uses pure Python — fast enough for < 10k vectors.
        For larger datasets, use numpy.
        """
        q_norm = math.sqrt(sum(v * v for v in query))
        if q_norm == 0:
            return [0.0] * len(vectors)

        scores = []
        for vec in vectors:
            v_norm = math.sqrt(sum(v * v for v in vec))
            if v_norm == 0:
                scores.append(0.0)
                continue
            dot = sum(q * v for q, v in zip(query, vec))
            scores.append(dot / (q_norm * v_norm))

        return scores

    @property
    def size(self) -> int:
        return len(self._vectors)


# ── Milvus Vector Store ──────────────────────────────────────


class MilvusVectorStore(VectorStore):
    """Milvus standalone vector store (for development / Phase 2).

    Uses pymilvus to connect to a local Milvus instance.
    Start with: docker compose --profile phase2 up -d

    Requires: ``pip install pymilvus``
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = "knowledge_chunks",
        dim: int = 768,
    ) -> None:
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.dim = dim
        self._collection = None
        self._connected = False

    def is_ready(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Connect to Milvus and ensure the collection exists."""
        try:
            from pymilvus import (
                Collection,
                CollectionSchema,
                DataType,
                FieldSchema,
                connections,
                utility,
            )

            connections.connect(
                alias="default",
                host=self.host,
                port=str(self.port),
            )

            # Check if collection exists, create if not
            if utility.has_collection(self.collection_name):
                self._collection = Collection(self.collection_name)
            else:
                fields = [
                    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=4096),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
                ]
                schema = CollectionSchema(fields, description="Knowledge base chunk vectors")
                self._collection = Collection(self.collection_name, schema)

                # Create IVF_FLAT index
                index_params = {
                    "metric_type": "COSINE",
                    "index_type": "IVF_FLAT",
                    "params": {"nlist": 128},
                }
                self._collection.create_index("embedding", index_params)

            self._collection.load()
            self._connected = True
            logger.info(
                "milvus.connected",
                host=self.host,
                port=self.port,
                collection=self.collection_name,
            )

        except ImportError:
            logger.warning("milvus.no_pymilvus", hint="pip install pymilvus")
        except Exception as e:
            logger.error("milvus.connect_failed", error=str(e))

    async def insert(
        self,
        vectors: list[list[float]],
        doc_ids: list[str],
        chunk_ids: list[str],
        contents: list[str],
        metadata: list[dict[str, Any]] | None = None,
    ) -> int:
        """Insert vectors into Milvus."""
        if not self._connected:
            return 0

        try:
            data = [
                chunk_ids,
                doc_ids,
                contents,
                vectors,
            ]
            mr = self._collection.insert(data)
            self._collection.flush()
            return mr.insert_count
        except Exception as e:
            logger.error("milvus.insert_failed", error=str(e))
            return 0

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        min_score: float = 0.0,
        filter_expr: str | None = None,
    ) -> VectorSearchResponse:
        """Search Milvus for similar vectors."""
        start = time.monotonic()

        if not self._connected:
            return VectorSearchResponse(
                retrieval_ms=round((time.monotonic() - start) * 1000, 2),
                backend="milvus(disconnected)",
            )

        try:
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}

            results = self._collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expr,
                output_fields=["chunk_id", "doc_id", "content"],
            )

            vector_results: list[VectorSearchResult] = []
            for hits in results:
                for hit in hits:
                    if hit.score < min_score:
                        continue
                    vector_results.append(VectorSearchResult(
                        doc_id=hit.entity.get("doc_id", ""),
                        chunk_id=hit.entity.get("chunk_id", ""),
                        content=hit.entity.get("content", ""),
                        score=round(hit.score, 4),
                    ))

            elapsed = (time.monotonic() - start) * 1000
            return VectorSearchResponse(
                results=vector_results[:top_k],
                retrieval_ms=round(elapsed, 2),
                backend="milvus",
            )

        except Exception as e:
            logger.error("milvus.search_failed", error=str(e))
            return VectorSearchResponse(
                retrieval_ms=round((time.monotonic() - start) * 1000, 2),
                backend="milvus(error)",
            )

    async def delete(self, chunk_ids: list[str]) -> int:
        """Delete vectors from Milvus by chunk_id."""
        if not self._connected:
            return 0

        try:
            expr = f"chunk_id in [{', '.join(repr(cid) for cid in chunk_ids)}]"
            self._collection.delete(expr)
            return len(chunk_ids)
        except Exception as e:
            logger.error("milvus.delete_failed", error=str(e))
            return 0


# ── Factory ──────────────────────────────────────────────────

def create_vector_store(config: dict[str, Any]) -> VectorStore:
    """Create the appropriate vector store from configuration.

    Args:
        config: Dict with keys:
            - backend: "memory" | "milvus" | "dashvector"
            - milvus_host, milvus_port (for milvus)
            - dim: vector dimension
    """
    backend = config.get("backend", "memory")

    if backend == "milvus":
        store = MilvusVectorStore(
            host=config.get("milvus_host", "localhost"),
            port=int(config.get("milvus_port", 19530)),
            collection_name=config.get("collection_name", "knowledge_chunks"),
            dim=int(config.get("dim", 768)),
        )
        return store

    # Default: in-memory
    return MemoryVectorStore(dim=int(config.get("dim", 768)))
