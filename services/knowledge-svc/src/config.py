"""Service configuration for knowledge-svc."""

from libs.common.config import ServiceConfig


class KnowledgeConfig(ServiceConfig):
    """Knowledge service configuration."""

    def __init__(self) -> None:
        super().__init__("knowledge-svc")

    @property
    def grpc_port(self) -> int:
        return self.get_int("GRPC_PORT", 50058)

    @property
    def http_port(self) -> int:
        return self.get_int("HTTP_PORT", 8007)

    @property
    def http_host(self) -> str:
        return self.get("HTTP_HOST", "0.0.0.0")

    @property
    def db_pool_size(self) -> int:
        return self.get_int("DB_POOL_SIZE", 10)

    # ── Vector Store ──

    @property
    def vector_backend(self) -> str:
        """Vector store backend: 'memory', 'milvus', or 'dashvector'."""
        return self.get("VECTOR_BACKEND", "memory")

    @property
    def milvus_host(self) -> str:
        return self.get("MILVUS_HOST", "localhost")

    @property
    def milvus_port(self) -> int:
        return self.get_int("MILVUS_PORT", 19530)

    @property
    def embedding_backend(self) -> str:
        """Embedding backend: 'hash', 'text2vec', or 'openai'."""
        return self.get("EMBEDDING_BACKEND", "hash")

    @property
    def embedding_model_name(self) -> str:
        return self.get("EMBEDDING_MODEL", "shibing624/text2vec-base-chinese")

    @property
    def embedding_api_key(self) -> str:
        return self.get("EMBEDDING_API_KEY", "")

    @property
    def vector_dim(self) -> int:
        return self.get_int("VECTOR_DIM", 768)

    @property
    def deepseek_api_key(self) -> str:
        return self.get("DEEPSEEK_API_KEY", "")


config = KnowledgeConfig()

# Legacy module-level compat
GRPC_PORT: int = config.grpc_port
HTTP_PORT: int = config.http_port
HTTP_HOST: str = config.http_host
DB_POOL_SIZE: int = config.db_pool_size
ENV: str = config.get("ENV", "dev")
