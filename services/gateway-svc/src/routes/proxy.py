"""
REST-to-gRPC proxy routes.

Maps RESTful HTTP endpoints to downstream gRPC service calls.
Handles request/response translation, error mapping, and WebSocket proxying
for the TTS streaming synthesis endpoint.

Route mappings:
  Auth:     POST /api/v1/auth/{register,login,refresh}
  Users:    GET/PUT /api/v1/users/{user_id}
  Products: CRUD /api/v1/products/*
  Scripts:  CRUD /api/v1/scripts/*
  TTS:      POST /api/v1/tts/synthesize, WS /api/v1/ws/tts/synthesize
  Voice:    CRUD /api/v1/voices/*
"""

from __future__ import annotations

import json
import time
from typing import Any

import grpc
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from libs.common.errors import ErrorCode
from libs.common.logging import get_logger

from ..grpc_client import grpc_manager
from .deps import get_current_user

logger = get_logger(__name__)

router = APIRouter(tags=["proxy"])

# ── Constants ──

_REQUEST_TIMEOUT = 30.0  # Default gRPC call timeout in seconds
_STREAM_TIMEOUT = 300.0  # Streaming call timeout


# ── Error mapping ──

def _grpc_to_http_status(grpc_code: grpc.StatusCode) -> int:
    """Map gRPC status codes to HTTP status codes."""
    mapping = {
        grpc.StatusCode.OK: 200,
        grpc.StatusCode.CANCELLED: 499,
        grpc.StatusCode.UNKNOWN: 500,
        grpc.StatusCode.INVALID_ARGUMENT: 400,
        grpc.StatusCode.DEADLINE_EXCEEDED: 504,
        grpc.StatusCode.NOT_FOUND: 404,
        grpc.StatusCode.ALREADY_EXISTS: 409,
        grpc.StatusCode.PERMISSION_DENIED: 403,
        grpc.StatusCode.UNAUTHENTICATED: 401,
        grpc.StatusCode.RESOURCE_EXHAUSTED: 429,
        grpc.StatusCode.FAILED_PRECONDITION: 400,
        grpc.StatusCode.ABORTED: 409,
        grpc.StatusCode.OUT_OF_RANGE: 400,
        grpc.StatusCode.UNIMPLEMENTED: 501,
        grpc.StatusCode.INTERNAL: 500,
        grpc.StatusCode.UNAVAILABLE: 503,
        grpc.StatusCode.DATA_LOSS: 500,
    }
    return mapping.get(grpc_code, 500)


def _handle_grpc_error(exc: grpc.RpcError) -> JSONResponse:
    """Convert a gRPC RpcError to a FastAPI JSONResponse."""
    status_code = _grpc_to_http_status(exc.code())
    details = exc.details() if exc.details() else str(exc)
    logger.warning(
        "proxy.grpc_error",
        grpc_code=str(exc.code()),
        http_status=status_code,
        details=details,
    )
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_ERROR,
                "message": details,
            }
        },
    )


# ── Helper: protobuf JSON parsing (snake_case <-> camelCase) ──

def _pb_to_dict(msg: Any) -> dict:
    """Convert a protobuf message to a JSON-safe dict."""
    from google.protobuf.json_format import MessageToDict
    return MessageToDict(
        msg,
        preserving_proto_field_name=True,
        including_default_value_fields=False,
    )


def _dict_to_pb(data: dict, msg_class: type) -> Any:
    """Convert a dict to a protobuf message."""
    from google.protobuf.json_format import ParseDict
    return ParseDict(data, msg_class())


# ── Auth Routes ──

@router.post("/api/v1/auth/register")
async def auth_register(request: Request):
    """Register a new user account."""
    try:
        from proto.user.v1 import user_pb2
        body = await request.json()
        req = _dict_to_pb(body, user_pb2.RegisterRequest)
        resp = await grpc_manager.user_stub.Register(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.post("/api/v1/auth/login")
async def auth_login(request: Request):
    """Authenticate and receive JWT tokens."""
    try:
        from proto.user.v1 import user_pb2
        body = await request.json()
        req = _dict_to_pb(body, user_pb2.LoginRequest)
        resp = await grpc_manager.user_stub.Login(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.post("/api/v1/auth/refresh")
async def auth_refresh(request: Request):
    """Refresh an expired JWT token using a refresh token."""
    try:
        from proto.user.v1 import user_pb2
        body = await request.json()
        req = _dict_to_pb(body, user_pb2.RefreshTokenRequest)
        resp = await grpc_manager.user_stub.RefreshToken(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


# ── User Routes ──

@router.get("/api/v1/users/me")
async def get_current_user_profile(request: Request, user=Depends(get_current_user)):
    """Get the authenticated user's profile."""
    try:
        from proto.user.v1 import user_pb2
        req = user_pb2.GetUserRequest(user_id=user.user_id)
        resp = await grpc_manager.user_stub.GetUser(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.get("/api/v1/users/{user_id}")
async def get_user(user_id: str, request: Request, user=Depends(get_current_user)):
    """Get a user by ID (admin or self)."""
    try:
        from proto.user.v1 import user_pb2
        req = user_pb2.GetUserRequest(user_id=user_id)
        resp = await grpc_manager.user_stub.GetUser(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.put("/api/v1/users/{user_id}")
async def update_user(user_id: str, request: Request, user=Depends(get_current_user)):
    """Update a user profile."""
    try:
        from proto.user.v1 import user_pb2
        body = await request.json()
        body["user_id"] = user_id
        req = _dict_to_pb(body, user_pb2.UpdateUserRequest)
        resp = await grpc_manager.user_stub.UpdateUser(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.get("/api/v1/users")
async def list_users(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    user=Depends(get_current_user),
):
    """List users (admin only)."""
    try:
        from proto.user.v1 import user_pb2
        req = user_pb2.ListUsersRequest(
            pagination=user_pb2.Pagination(page=page, page_size=page_size),
        )
        resp = await grpc_manager.user_stub.ListUsers(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


# ── Product Routes ──

@router.post("/api/v1/products")
async def create_product(request: Request, user=Depends(get_current_user)):
    """Create a new product."""
    try:
        from proto.product.v1 import product_pb2
        body = await request.json()
        body["store_id"] = body.get("store_id", user.store_id)
        req = _dict_to_pb(body, product_pb2.CreateProductRequest)
        resp = await grpc_manager.product_stub.CreateProduct(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.get("/api/v1/products/{product_id}")
async def get_product(product_id: str, request: Request, user=Depends(get_current_user)):
    """Get a product by ID."""
    try:
        from proto.product.v1 import product_pb2
        req = product_pb2.GetProductRequest(product_id=product_id)
        resp = await grpc_manager.product_stub.GetProduct(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.put("/api/v1/products/{product_id}")
async def update_product(
    product_id: str, request: Request, user=Depends(get_current_user)
):
    """Update a product."""
    try:
        from proto.product.v1 import product_pb2
        body = await request.json()
        body["product_id"] = product_id
        req = _dict_to_pb(body, product_pb2.UpdateProductRequest)
        resp = await grpc_manager.product_stub.UpdateProduct(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.delete("/api/v1/products/{product_id}")
async def delete_product(
    product_id: str, request: Request, user=Depends(get_current_user)
):
    """Delete a product."""
    try:
        from proto.product.v1 import product_pb2
        req = product_pb2.DeleteProductRequest(product_id=product_id)
        await grpc_manager.product_stub.DeleteProduct(req, timeout=_REQUEST_TIMEOUT)
        return {"success": True, "product_id": product_id}
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.get("/api/v1/products")
async def list_products(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    store_id: str | None = None,
    user=Depends(get_current_user),
):
    """List products with pagination."""
    try:
        from proto.product.v1 import product_pb2
        req = product_pb2.ListProductsRequest(
            pagination=product_pb2.Pagination(page=page, page_size=page_size),
            store_id=store_id or user.store_id or "",
        )
        resp = await grpc_manager.product_stub.ListProducts(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


# ── Script Routes ──

@router.post("/api/v1/scripts")
async def create_script(request: Request, user=Depends(get_current_user)):
    """Create a new script."""
    try:
        from proto.script.v1 import script_pb2
        body = await request.json()
        body["store_id"] = body.get("store_id", user.store_id)
        req = _dict_to_pb(body, script_pb2.CreateScriptRequest)
        resp = await grpc_manager.script_stub.CreateScript(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.get("/api/v1/scripts/{script_id}")
async def get_script(script_id: str, request: Request, user=Depends(get_current_user)):
    """Get a script by ID."""
    try:
        from proto.script.v1 import script_pb2
        req = script_pb2.GetScriptRequest(script_id=script_id)
        resp = await grpc_manager.script_stub.GetScript(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.put("/api/v1/scripts/{script_id}")
async def update_script(
    script_id: str, request: Request, user=Depends(get_current_user)
):
    """Update a script."""
    try:
        from proto.script.v1 import script_pb2
        body = await request.json()
        body["script_id"] = script_id
        req = _dict_to_pb(body, script_pb2.UpdateScriptRequest)
        resp = await grpc_manager.script_stub.UpdateScript(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.delete("/api/v1/scripts/{script_id}")
async def delete_script(
    script_id: str, request: Request, user=Depends(get_current_user)
):
    """Delete a script."""
    try:
        from proto.script.v1 import script_pb2
        req = script_pb2.DeleteScriptRequest(script_id=script_id)
        await grpc_manager.script_stub.DeleteScript(req, timeout=_REQUEST_TIMEOUT)
        return {"success": True, "script_id": script_id}
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.get("/api/v1/scripts")
async def list_scripts(
    request: Request,
    page: int = 1,
    page_size: int = 20,
    store_id: str | None = None,
    product_id: str | None = None,
    user=Depends(get_current_user),
):
    """List scripts with pagination."""
    try:
        from proto.script.v1 import script_pb2
        req = script_pb2.ListScriptsRequest(
            pagination=script_pb2.Pagination(page=page, page_size=page_size),
            store_id=store_id or user.store_id or "",
            product_id=product_id or "",
        )
        resp = await grpc_manager.script_stub.ListScripts(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


# ── TTS Routes ──

@router.post("/api/v1/tts/synthesize")
async def tts_synthesize(request: Request, user=Depends(get_current_user)):
    """Synthesize speech from text (non-streaming convenience wrapper).

    For streaming, use the WebSocket endpoint at /api/v1/ws/tts/synthesize.
    """
    try:
        from proto.tts.v1 import tts_pb2
        body = await request.json()
        req = _dict_to_pb(body, tts_pb2.SynthesisRequest)

        # Collect all audio chunks from the server-streaming response
        audio_chunks: list[bytes] = []
        metadata: dict[str, Any] = {}
        async for response in grpc_manager.tts_stub.Synthesize(req, timeout=_STREAM_TIMEOUT):
            response_type = response.WhichOneof("response")
            if response_type == "audio_chunk":
                audio_chunks.append(response.audio_chunk.data)
            elif response_type == "complete":
                metadata = _pb_to_dict(response.complete)
            elif response_type == "error":
                logger.error("tts.synthesis_error", error=response.error.message)
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "code": ErrorCode.TTS_SYNTHESIS_FAILED,
                            "message": response.error.message,
                        }
                    },
                )

        return {
            "audio_data": [chunk.hex() for chunk in audio_chunks],
            "metadata": metadata,
        }
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


@router.get("/api/v1/tts/voices")
async def list_tts_voices(request: Request, user=Depends(get_current_user)):
    """List available TTS voices."""
    try:
        from proto.tts.v1 import tts_pb2
        req = tts_pb2.ListVoicesRequest()
        resp = await grpc_manager.tts_stub.ListVoices(req, timeout=_REQUEST_TIMEOUT)
        return _pb_to_dict(resp)
    except grpc.RpcError as exc:
        return _handle_grpc_error(exc)


# ── TTS WebSocket Proxy ──

@router.websocket("/api/v1/ws/tts/synthesize")
async def tts_synthesize_ws(websocket: WebSocket):
    """WebSocket proxy for streaming TTS synthesis.

    Accepts JSON messages with SynthesisRequest fields and streams back
    audio chunks as binary messages, with JSON metadata/error messages.

    Protocol:
      Client -> Server: JSON with synthesis params (text, voice_id, etc.)
      Server -> Client: Binary (audio chunk) or JSON (metadata/error)
    """
    await websocket.accept()

    # Track connection for rate limiting
    client_ip = websocket.client.host if websocket.client else "unknown"
    connection_id = f"ws-{time.time_ns()}"

    from ..middleware.ratelimit import rate_limiter_registry

    try:
        allowed = await rate_limiter_registry.try_acquire_ws(client_ip, connection_id)
        if not allowed:
            await websocket.send_json({
                "type": "error",
                "code": 4003,
                "message": f"WebSocket connection limit exceeded "
                f"({rate_limiter_registry.get_route_rps('/api/v1/ws/tts')} per IP).",
            })
            await websocket.close(code=1008)
            return

        # Wait for the synthesis request from the client
        raw = await websocket.receive_text()
        body = json.loads(raw)

        from proto.tts.v1 import tts_pb2
        req = _dict_to_pb(body, tts_pb2.SynthesisRequest)

        # Stream audio chunks back
        async for response in grpc_manager.tts_stub.Synthesize(req, timeout=_STREAM_TIMEOUT):
            response_type = response.WhichOneof("response")
            if response_type == "audio_chunk":
                chunk = response.audio_chunk
                # Send binary: audio data
                await websocket.send_bytes(chunk.data)
            elif response_type == "complete":
                await websocket.send_json({
                    "type": "complete",
                    "data": _pb_to_dict(response.complete),
                })
            elif response_type == "error":
                await websocket.send_json({
                    "type": "error",
                    "message": response.error.message,
                })

    except WebSocketDisconnect:
        logger.debug("ws.disconnect", client_ip=client_ip)
    except Exception as exc:
        logger.error("ws.error", client_ip=client_ip, error=str(exc))
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Internal error: {str(exc)}",
            })
        except Exception:
            pass
    finally:
        await rate_limiter_registry.release_ws(client_ip, connection_id)
