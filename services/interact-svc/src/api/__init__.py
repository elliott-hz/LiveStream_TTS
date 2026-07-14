"""
gRPC API — implements InteractionService RPCs defined in interact.v1.
"""

from .grpc_impl import InteractionServiceServicer

__all__ = ["InteractionServiceServicer"]
