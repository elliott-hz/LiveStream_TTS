"""
gRPC implementation of NLPService.

Implements all 5 RPCs defined in nlp/v1/nlp.proto:
  - AnalyzeDanmaku
  - BatchAnalyzeDanmaku
  - CheckSensitive
  - ExtractEntities
  - RewriteText

Converts between proto enums and internal representations.
Uses libs.common.errors for standardized error handling.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import grpc

# Monorepo path setup
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from libs.common.errors import AppError, ErrorCode, Domain, invalid_arg, internal
from libs.common.logging import get_logger

from nlp.v1 import nlp_pb2
from nlp.v1.nlp_pb2_grpc import NLPServiceServicer, add_NLPServiceServicer_to_server

from src.classifiers.intent import IntentType
from src.classifiers.sentiment import SentimentType
from src.detectors.sensitive import DetectionLayer
from src.services.nlp_service import nlp_service

logger = get_logger(__name__)


# ── Proto enum ↔ Internal enum mapping ──

def intent_to_proto(intent: IntentType) -> int:
    """Map internal IntentType to proto IntentCategory value."""
    mapping = {
        IntentType.UNSPECIFIED: nlp_pb2.INTENT_CATEGORY_UNSPECIFIED,
        IntentType.QUESTION: nlp_pb2.INTENT_CATEGORY_QUESTION,
        IntentType.REQUEST_DEMO: nlp_pb2.INTENT_CATEGORY_REQUEST_DEMO,
        IntentType.PURCHASE_INTENT: nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT,
        IntentType.BARGAIN: nlp_pb2.INTENT_CATEGORY_BARGAIN,
        IntentType.COMPLAINT: nlp_pb2.INTENT_CATEGORY_COMPLAINT,
        IntentType.GREETING: nlp_pb2.INTENT_CATEGORY_GREETING,
        IntentType.PRAISE: nlp_pb2.INTENT_CATEGORY_PRAISE,
        IntentType.QUESTION_PRODUCT: nlp_pb2.INTENT_CATEGORY_QUESTION_PRODUCT,
        IntentType.URGE: nlp_pb2.INTENT_CATEGORY_URGE,
        IntentType.COMPARE: nlp_pb2.INTENT_CATEGORY_COMPARE,
        IntentType.AFTERSALES: nlp_pb2.INTENT_CATEGORY_AFTERSALES,
        IntentType.OTHER: nlp_pb2.INTENT_CATEGORY_OTHER,
    }
    return mapping.get(intent, nlp_pb2.INTENT_CATEGORY_UNSPECIFIED)


def proto_to_intent(proto_val: int) -> IntentType:
    """Map proto IntentCategory value to internal IntentType."""
    mapping = {
        nlp_pb2.INTENT_CATEGORY_UNSPECIFIED: IntentType.UNSPECIFIED,
        nlp_pb2.INTENT_CATEGORY_QUESTION: IntentType.QUESTION,
        nlp_pb2.INTENT_CATEGORY_REQUEST_DEMO: IntentType.REQUEST_DEMO,
        nlp_pb2.INTENT_CATEGORY_PURCHASE_INTENT: IntentType.PURCHASE_INTENT,
        nlp_pb2.INTENT_CATEGORY_BARGAIN: IntentType.BARGAIN,
        nlp_pb2.INTENT_CATEGORY_COMPLAINT: IntentType.COMPLAINT,
        nlp_pb2.INTENT_CATEGORY_GREETING: IntentType.GREETING,
        nlp_pb2.INTENT_CATEGORY_PRAISE: IntentType.PRAISE,
        nlp_pb2.INTENT_CATEGORY_QUESTION_PRODUCT: IntentType.QUESTION_PRODUCT,
        nlp_pb2.INTENT_CATEGORY_URGE: IntentType.URGE,
        nlp_pb2.INTENT_CATEGORY_COMPARE: IntentType.COMPARE,
        nlp_pb2.INTENT_CATEGORY_AFTERSALES: IntentType.AFTERSALES,
        nlp_pb2.INTENT_CATEGORY_OTHER: IntentType.OTHER,
    }
    return mapping.get(proto_val, IntentType.OTHER)


def sentiment_to_proto(sentiment: SentimentType) -> int:
    """Map internal SentimentType to proto Sentiment value."""
    mapping = {
        SentimentType.UNSPECIFIED: nlp_pb2.SENTIMENT_UNSPECIFIED,
        SentimentType.POSITIVE: nlp_pb2.SENTIMENT_POSITIVE,
        SentimentType.NEGATIVE: nlp_pb2.SENTIMENT_NEGATIVE,
        SentimentType.NEUTRAL: nlp_pb2.SENTIMENT_NEUTRAL,
        SentimentType.ANGRY: nlp_pb2.SENTIMENT_ANGRY,
        SentimentType.EXCITED: nlp_pb2.SENTIMENT_EXCITED,
    }
    return mapping.get(sentiment, nlp_pb2.SENTIMENT_UNSPECIFIED)


def layer_to_proto(layer: DetectionLayer) -> int:
    """Map internal DetectionLayer to proto value."""
    mapping = {
        DetectionLayer.UNSPECIFIED: nlp_pb2.DETECTION_LAYER_UNSPECIFIED,
        DetectionLayer.AC_AUTOMATON: nlp_pb2.DETECTION_LAYER_AC_AUTOMATON,
        DetectionLayer.LLM_SEMANTIC: nlp_pb2.DETECTION_LAYER_LLM_SEMANTIC,
    }
    return mapping.get(layer, nlp_pb2.DETECTION_LAYER_UNSPECIFIED)


class NLPServiceServicerImpl(NLPServiceServicer):
    """Full implementation of the NLPService gRPC interface."""

    async def AnalyzeDanmaku(
        self,
        request: nlp_pb2.AnalyzeDanmakuRequest,
        context: grpc.aio.ServicerContext,
    ) -> nlp_pb2.AnalyzeDanmakuResponse:
        """Analyze a single danmaku message for intent + sentiment + reply need."""
        try:
            context_intent = proto_to_intent(request.context_intent) if request.context_intent else None

            result = await nlp_service.analyze_danmaku(
                text=request.text,
                user_id=request.user_id,
                live_room_id=request.live_room_id,
                context_intent=context_intent,
            )

            return nlp_pb2.AnalyzeDanmakuResponse(
                intent=intent_to_proto(result["intent"]),
                intent_confidence=result["intent_confidence"],
                sentiment=sentiment_to_proto(result["sentiment"]),
                sentiment_intensity=result["sentiment_intensity"],
                needs_reply=result["needs_reply"],
                reason=result["reason"],
                processing_ms=result["processing_ms"],
            )
        except AppError:
            raise
        except Exception as e:
            logger.error("analyze_danmaku.error", error=str(e), text=request.text[:50])
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {e}")
            return nlp_pb2.AnalyzeDanmakuResponse()

    async def BatchAnalyzeDanmaku(
        self,
        request: nlp_pb2.BatchAnalyzeDanmakuRequest,
        context: grpc.aio.ServicerContext,
    ) -> nlp_pb2.BatchAnalyzeDanmakuResponse:
        """Batch analyze multiple danmaku messages."""
        try:
            max_batch = request.max_batch_size or 32
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
                max_batch_size=max_batch,
            )

            response = nlp_pb2.BatchAnalyzeDanmakuResponse(
                total=result["total"],
                needs_reply_count=result["needs_reply_count"],
            )

            for r in result["results"]:
                resp_item = nlp_pb2.AnalyzeDanmakuResponse(
                    intent=intent_to_proto(r["intent"]),
                    intent_confidence=r["intent_confidence"],
                    sentiment=sentiment_to_proto(r["sentiment"]),
                    sentiment_intensity=r["sentiment_intensity"],
                    needs_reply=r["needs_reply"],
                    reason=r["reason"],
                    processing_ms=r["processing_ms"],
                )
                response.results.append(resp_item)

            return response

        except AppError:
            raise
        except Exception as e:
            logger.error("batch_analyze.error", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {e}")
            return nlp_pb2.BatchAnalyzeDanmakuResponse()

    async def CheckSensitive(
        self,
        request: nlp_pb2.CheckSensitiveRequest,
        context: grpc.aio.ServicerContext,
    ) -> nlp_pb2.CheckSensitiveResponse:
        """Check text for sensitive content (dual-mode)."""
        try:
            result = await nlp_service.check_sensitive(
                text=request.text,
                context=request.context or "danmaku",
            )

            response = nlp_pb2.CheckSensitiveResponse(
                is_sensitive=result.is_sensitive,
                processing_ms=int(result.processing_ms),
            )

            for match in result.matches:
                proto_match = nlp_pb2.SensitiveMatch(
                    word=match.word,
                    category=match.category,
                    start_pos=match.start_pos,
                    end_pos=match.end_pos,
                    layer=layer_to_proto(match.layer),
                )
                response.matches.append(proto_match)

            return response

        except AppError:
            raise
        except Exception as e:
            logger.error("check_sensitive.error", error=str(e), text=request.text[:50])
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {e}")
            return nlp_pb2.CheckSensitiveResponse()

    async def ExtractEntities(
        self,
        request: nlp_pb2.ExtractEntitiesRequest,
        context: grpc.aio.ServicerContext,
    ) -> nlp_pb2.ExtractEntitiesResponse:
        """Extract named entities from text."""
        try:
            entities = await nlp_service.extract_entities(
                text=request.text,
                entity_types=list(request.entity_types) or None,
            )

            response = nlp_pb2.ExtractEntitiesResponse()
            for ent in entities:
                proto_ent = nlp_pb2.Entity(
                    text=ent["text"],
                    type=ent["type"],
                    start_pos=ent["start_pos"],
                    end_pos=ent["end_pos"],
                    confidence=ent["confidence"],
                )
                response.entities.append(proto_ent)

            return response

        except AppError:
            raise
        except Exception as e:
            logger.error("extract_entities.error", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {e}")
            return nlp_pb2.ExtractEntitiesResponse()

    async def RewriteText(
        self,
        request: nlp_pb2.RewriteTextRequest,
        context: grpc.aio.ServicerContext,
    ) -> nlp_pb2.RewriteTextResponse:
        """Rewrite text in a specified style."""
        try:
            style_map = {
                nlp_pb2.REWRITE_STYLE_LIVE_COMMENT: "live_comment",
                nlp_pb2.REWRITE_STYLE_PRODUCT_SCRIPT: "product_script",
                nlp_pb2.REWRITE_STYLE_FIELD_CONTROL: "field_control",
            }
            style = style_map.get(request.style, "live_comment")

            result = await nlp_service.rewrite_text(
                text=request.text,
                style=style,
                context=request.context or "",
            )

            return nlp_pb2.RewriteTextResponse(
                rewritten_text=result["rewritten_text"],
            )

        except AppError:
            raise
        except Exception as e:
            logger.error("rewrite_text.error", error=str(e))
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Internal error: {e}")
            return nlp_pb2.RewriteTextResponse()
