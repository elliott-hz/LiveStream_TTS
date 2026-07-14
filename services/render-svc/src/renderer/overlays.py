"""
Overlay definitions and rendering — product cards, price tags, coupons,
watermarks, and logos.

Each overlay is defined by an OverlayDefinition dataclass and a render
function that serialises it into a byte payload (placeholder).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from typing import Any

from libs.common.logging import get_logger

logger = get_logger(__name__)


# ── Overlay Types ──


class OverlayType(IntEnum):
    PRODUCT_CARD = 1
    PRICE_TAG = 2
    COUPON = 3
    WATERMARK = 4
    LOGO = 5


# ── Overlay Definition ──


@dataclass
class Position:
    """Position and sizing of an overlay on the frame."""

    x: int = 0
    y: int = 0
    width: int = 200
    height: int = 100
    opacity: float = 1.0


@dataclass
class OverlayDefinition:
    """Complete definition of a single overlay element."""

    overlay_id: str = ""
    type: OverlayType = OverlayType.PRODUCT_CARD
    content: str = ""
    position: Position = field(default_factory=Position)


# ── Render Helpers ──


def render_overlay(overlay: OverlayDefinition) -> bytes:
    """Render a single overlay to a serialised byte payload.

    In production this would composite the overlay onto the frame at
    the pixel level. Here we return a JSON-encoded metadata blob.
    """
    data: dict[str, Any] = {
        "overlay_id": overlay.overlay_id,
        "type": overlay.type,
        "content": overlay.content,
        "position": asdict(overlay.position),
    }
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def build_default_overlays() -> list[OverlayDefinition]:
    """Return a standard set of overlays for a livestream shopping scene."""
    return [
        OverlayDefinition(
            overlay_id="watermark",
            type=OverlayType.WATERMARK,
            content="LiveStream TTS",
            position=Position(x=20, y=20, width=200, height=40, opacity=0.6),
        ),
        OverlayDefinition(
            overlay_id="product_card",
            type=OverlayType.PRODUCT_CARD,
            content='{"product_id": "demo", "name": "Demo Product"}',
            position=Position(x=1600, y=50, width=280, height=400, opacity=0.9),
        ),
        OverlayDefinition(
            overlay_id="price_tag",
            type=OverlayType.PRICE_TAG,
            content="¥99.00",
            position=Position(x=1600, y=460, width=280, height=60, opacity=0.95),
        ),
    ]


def proto_overlay_to_definition(
    overlay_proto: Any,  # render.v1.Overlay
) -> OverlayDefinition:
    """Convert a proto Overlay message to an OverlayDefinition."""
    position = overlay_proto.position
    return OverlayDefinition(
        overlay_id=overlay_proto.overlay_id,
        type=OverlayType(overlay_proto.type),
        content=overlay_proto.content,
        position=Position(
            x=position.x,
            y=position.y,
            width=position.width,
            height=position.height,
            opacity=position.opacity,
        ),
    )
