"""
HTTP/REST routes for the NLP Service.

Endpoints:
  GET  /api/v1/health              — Health check
  POST /api/v1/nlp/analyze         — Analyze single danmaku
  POST /api/v1/nlp/check-sensitive  — Check sensitive content
  POST /api/v1/nlp/batch-analyze   — Batch analyze danmaku messages
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from libs.common.errors import AppError, ErrorCode
from libs.common.logging import get_logger

from src.classifiers.intent import IntentType
from src.classifiers.sentiment import SentimentType
from src.detectors.sensitive import DetectionLayer
from src.services.nlp_service import nlp_service

logger = get_logger(__name__)

router = APIRouter()


# ── Request / Response models ──

class AnalyzeRequest(BaseModel):
    text: str
    user_id: str = ""
    live_room_id: str = ""
    context_intent: int | None = None


class AnalyzeResponse(BaseModel):
    intent: int
    intent_name: str
    intent_confidence: float
    sentiment: int
    sentiment_name: str
    sentiment_intensity: float
    needs_reply: bool
    reason: str
    processing_ms: int


class BatchAnalyzeRequest(BaseModel):
    items: list[AnalyzeRequest]
    max_batch_size: int = 32


class BatchAnalyzeResponse(BaseModel):
    results: list[AnalyzeResponse]
    total: int
    needs_reply_count: int


class CheckSensitiveRequest(BaseModel):
    text: str
    context: str = "danmaku"


class SensitiveMatchModel(BaseModel):
    word: str
    category: str
    start_pos: int
    end_pos: int
    layer: int


class CheckSensitiveResponse(BaseModel):
    is_sensitive: bool
    matches: list[SensitiveMatchModel]
    processing_ms: int


class ErrorResponse(BaseModel):
    error: str
    detail: str


# ── Intent/Sentiment name mappings ──

INTENT_NAMES = {
    0: "UNSPECIFIED",
    1: "QUESTION",
    2: "REQUEST_DEMO",
    3: "PURCHASE_INTENT",
    4: "BARGAIN",
    5: "COMPLAINT",
    6: "GREETING",
    7: "PRAISE",
    8: "QUESTION_PRODUCT",
    9: "URGE",
    10: "COMPARE",
    11: "AFTERSALES",
    12: "OTHER",
}

SENTIMENT_NAMES = {
    0: "UNSPECIFIED",
    1: "POSITIVE",
    2: "NEGATIVE",
    3: "NEUTRAL",
    4: "ANGRY",
    5: "EXCITED",
}


@router.get("/api/v1/health")
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "nlp-svc",
        "timestamp": int(time.time()),
    }


@router.post(
    "/api/v1/nlp/analyze",
    response_model=AnalyzeResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def analyze_danmaku(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a single danmaku message."""
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    try:
        context_intent = None
        if request.context_intent and request.context_intent != 0:
            context_intent = IntentType(request.context_intent)

        result = await nlp_service.analyze_danmaku(
            text=request.text,
            user_id=request.user_id,
            live_room_id=request.live_room_id,
            context_intent=context_intent,
        )

        return AnalyzeResponse(
            intent=result["intent"],
            intent_name=INTENT_NAMES.get(result["intent"], "UNKNOWN"),
            intent_confidence=result["intent_confidence"],
            sentiment=result["sentiment"],
            sentiment_name=SENTIMENT_NAMES.get(result["sentiment"], "UNKNOWN"),
            sentiment_intensity=result["sentiment_intensity"],
            needs_reply=result["needs_reply"],
            reason=result["reason"],
            processing_ms=result["processing_ms"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("http.analyze.error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@router.post(
    "/api/v1/nlp/batch-analyze",
    response_model=BatchAnalyzeResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def batch_analyze(request: BatchAnalyzeRequest) -> BatchAnalyzeResponse:
    """Batch analyze multiple danmaku messages."""
    if not request.items:
        raise HTTPException(status_code=400, detail="items is required")

    try:
        items = []
        for item in request.items:
            items.append({
                "text": item.text,
                "user_id": item.user_id,
                "live_room_id": item.live_room_id,
                "context_intent": item.context_intent,
            })

        result = await nlp_service.batch_analyze_danmaku(
            items=items,
            max_batch_size=request.max_batch_size,
        )

        analyze_responses = []
        for r in result["results"]:
            analyze_responses.append(AnalyzeResponse(
                intent=r["intent"],
                intent_name=INTENT_NAMES.get(r["intent"], "UNKNOWN"),
                intent_confidence=r["intent_confidence"],
                sentiment=r["sentiment"],
                sentiment_name=SENTIMENT_NAMES.get(r["sentiment"], "UNKNOWN"),
                sentiment_intensity=r["sentiment_intensity"],
                needs_reply=r["needs_reply"],
                reason=r["reason"],
                processing_ms=r["processing_ms"],
            ))

        return BatchAnalyzeResponse(
            results=analyze_responses,
            total=result["total"],
            needs_reply_count=result["needs_reply_count"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("http.batch_analyze.error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@router.post(
    "/api/v1/nlp/check-sensitive",
    response_model=CheckSensitiveResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def check_sensitive(request: CheckSensitiveRequest) -> CheckSensitiveResponse:
    """Check text for sensitive content."""
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="text is required")

    try:
        result = await nlp_service.check_sensitive(
            text=request.text,
            context=request.context,
        )

        return CheckSensitiveResponse(
            is_sensitive=result.is_sensitive,
            matches=[
                SensitiveMatchModel(
                    word=m.word,
                    category=m.category,
                    start_pos=m.start_pos,
                    end_pos=m.end_pos,
                    layer=m.layer,
                )
                for m in result.matches
            ],
            processing_ms=int(result.processing_ms),
        )

    except Exception as e:
        logger.error("http.check_sensitive.error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
