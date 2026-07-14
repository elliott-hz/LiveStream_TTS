"""
Text embedding service for knowledge base retrieval.

Supports multiple backends:
  - ``text2vec`` — text2vec-base-chinese via sentence-transformers (recommended)
  - ``openai`` — OpenAI-compatible embedding API (DashVector/DeepSeek)
  - ``hash`` — deterministic hash-based mock (no model needed)

All backends return normalized float vectors suitable for cosine similarity.
"""

from __future__ import annotations

import hashlib
import struct
from abc import ABC, abstractmethod

from libs.common.logging import get_logger

logger = get_logger(__name__)

DEFAULT_DIM = 768  # text2vec-base-chinese dimension


class EmbeddingBackend(ABC):
    """Abstract embedding backend."""

    dim: int = DEFAULT_DIM

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Convert text to a normalized embedding vector."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embed multiple texts."""
        ...

    @abstractmethod
    def is_loaded(self) -> bool:
        """Whether the model is loaded and ready."""
        ...


class HashEmbedding(EmbeddingBackend):
    """Deterministic hash-based mock embedding (no model needed).

    Produces pseudo-random but deterministic vectors of the given dimension.
    Suitable for development/testing when no ML model is available.
    Results are reproducible: same text → same vector.
    """

    dim: int = DEFAULT_DIM

    def __init__(self, dim: int = DEFAULT_DIM) -> None:
        self.dim = dim

    def is_loaded(self) -> bool:
        return True

    async def embed(self, text: str) -> list[float]:
        """Generate a deterministic mock embedding from text hash."""
        # Use SHA256 to generate seed bytes, then expand to fill dim
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(self.dim):
            # Use different byte combinations for each dimension
            seed = h[i % 32] + h[(i * 7 + 13) % 32]
            # Map 0-510 to -1.0 to 1.0
            val = (seed / 255.0) * 2.0 - 1.0
            vec.append(round(val, 6))
        # L2 normalize
        return self._normalize(vec)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]

    @staticmethod
    def _normalize(vec: list[float]) -> list[float]:
        """L2 normalize a vector."""
        norm = sum(v * v for v in vec) ** 0.5
        if norm == 0:
            return vec
        return [round(v / norm, 6) for v in vec]


class Text2VecEmbedding(EmbeddingBackend):
    """text2vec-base-chinese via sentence-transformers.

    Lazy-loads the model on first use. ~400MB RAM.

    Requires: ``pip install sentence-transformers``
    """

    dim: int = DEFAULT_DIM

    def __init__(self, model_name: str = "shibing624/text2vec-base-chinese",
                 device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        self._model = None

    def is_loaded(self) -> bool:
        return self._model is not None

    def _load_model(self) -> None:
        """Lazy-load the sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)
            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim:
                self.dim = actual_dim
            logger.info(
                "embedding.model_loaded",
                model=self.model_name,
                dim=self.dim,
                device=self.device,
            )
        except ImportError:
            logger.warning(
                "embedding.no_sentence_transformers",
                hint="pip install sentence-transformers",
            )
        except Exception as e:
            logger.error("embedding.load_failed", error=str(e))

    async def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        self.ensure_loaded()
        if self._model is None:
            # Fallback to hash
            fallback = HashEmbedding(dim=self.dim)
            return await fallback.embed(text)

        import asyncio
        loop = asyncio.get_running_loop()
        vec = await loop.run_in_executor(None, self._model.encode, text, None, True)
        return [round(float(v), 6) for v in vec]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embed multiple texts (more efficient than per-text)."""
        self.ensure_loaded()
        if self._model is None:
            fallback = HashEmbedding(dim=self.dim)
            return await fallback.embed_batch(texts)

        import asyncio
        loop = asyncio.get_running_loop()
        vecs = await loop.run_in_executor(None, self._model.encode, texts, None, True)
        return [[round(float(v), 6) for v in vec] for vec in vecs]

    def ensure_loaded(self) -> None:
        if not self.is_loaded():
            self._load_model()


class OpenAIEmbedding(EmbeddingBackend):
    """OpenAI-compatible embedding API.

    Works with DeepSeek, DashVector, or any OpenAI-compatible embedding endpoint.
    No local model needed.

    Requires: ``pip install httpx``
    """

    dim: int = 1536  # Default for text-embedding-ada-002

    def __init__(
        self,
        api_key: str = "",
        api_base: str = "https://api.deepseek.com",
        model: str = "text-embedding-ada-002",
    ) -> None:
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self._client = None

    def is_loaded(self) -> bool:
        return bool(self.api_key)

    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Call the embedding API for a single text."""
        if not self.api_key:
            fallback = HashEmbedding(dim=self.dim)
            return await fallback.embed(text)

        try:
            client = await self._get_client()
            url = f"{self.api_base}/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            resp = await client.post(url, json={
                "model": self.model,
                "input": text,
            }, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return [round(float(v), 6) for v in data["data"][0]["embedding"]]
        except Exception as e:
            logger.warning("embedding.api_failed", error=str(e))
            fallback = HashEmbedding(dim=self.dim)
            return await fallback.embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            fallback = HashEmbedding(dim=self.dim)
            return await fallback.embed_batch(texts)

        try:
            client = await self._get_client()
            url = f"{self.api_base}/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            resp = await client.post(url, json={
                "model": self.model,
                "input": texts,
            }, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return [[round(float(v), 6) for v in item["embedding"]] for item in data["data"]]
        except Exception as e:
            logger.warning("embedding.batch_api_failed", error=str(e))
            fallback = HashEmbedding(dim=self.dim)
            return await fallback.embed_batch(texts)
