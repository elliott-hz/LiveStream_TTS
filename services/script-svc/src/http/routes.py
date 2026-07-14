"""
FastAPI REST routes for Script Service.

Mirrors the gRPC API surface for HTTP clients.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from libs.common.errors import AppError
from libs.common.logging import get_logger
from libs.db import Database

from src.config import ScriptConfig
from src.services.script_service import ScriptService
from src.services.ai_generator import AIGenerator

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/scripts", tags=["scripts"])

# ── Pydantic models ──


class SectionCreate(BaseModel):
    order: int = Field(ge=1)
    type: str = "opening"
    text: str = ""
    duration_estimate_ms: int = 0
    emotion: str = "neutral"
    action: str = ""
    show_product_card: bool = False
    highlight_selling_point: str | None = None


class ScriptCreate(BaseModel):
    product_id: str
    store_id: str
    style: str = "passionate"
    industry: str = ""
    sections: list[SectionCreate] = []


class ScriptUpdate(BaseModel):
    style: str | None = None
    sections: list[SectionCreate] | None = None


class ScriptGenerate(BaseModel):
    product_id: str
    style: str = "passionate"
    target_duration_seconds: int = 120
    highlight_selling_points: list[str] = []
    extra_context: str = ""


class ScriptResponse(BaseModel):
    script_id: str
    product_id: str
    store_id: str
    version: int
    status: str
    style: str
    industry: str
    sections: list[dict[str, Any]]
    total_duration_estimate_ms: int
    ai_generated_prompt: str | None
    created_by: str | None
    updated_by: str | None
    created_at: str
    updated_at: str


class VersionPublish(BaseModel):
    note: str | None = None


class VersionRollback(BaseModel):
    target_version: int


# ── Dependencies ──


async def get_script_service() -> ScriptService:
    """Dependency: provides ScriptService with DB session."""
    config = ScriptConfig()
    db = Database(config)
    await db.connect()
    session = db.session()
    try:
        yield ScriptService(session)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        await db.disconnect()


# ── Helper ──


def _script_to_response(script) -> dict[str, Any]:
    """Convert ORM Script to API response dict."""
    sections = []
    for s in script.sections or []:
        sections.append({
            "section_id": str(s.section_id),
            "order": s.order,
            "type": s.type,
            "text": s.text,
            "duration_estimate_ms": s.duration_estimate_ms,
            "emotion": s.emotion,
            "action": s.action,
            "show_product_card": s.show_product_card,
            "highlight_selling_point": s.highlight_selling_point,
        })

    return {
        "script_id": str(script.script_id),
        "product_id": script.product_id,
        "store_id": script.store_id,
        "version": script.version,
        "status": script.status,
        "style": script.style,
        "industry": script.industry,
        "sections": sections,
        "total_duration_estimate_ms": script.total_duration_estimate_ms,
        "ai_generated_prompt": script.ai_generated_prompt,
        "created_by": script.created_by,
        "updated_by": script.updated_by,
        "created_at": script.created_at.isoformat() if script.created_at else "",
        "updated_at": script.updated_at.isoformat() if script.updated_at else "",
    }


def _handle_app_error(e: AppError):
    """Convert AppError to HTTPException."""
    status_map = {
        1001: 401, 1002: 403, 1003: 401, 1004: 401,
        2001: 400, 2002: 400, 2003: 400, 2004: 400,
        3001: 404, 3002: 404, 3003: 404, 3004: 404,
        4001: 409, 4002: 409, 4003: 429, 4007: 400,
        5001: 500, 5002: 500,
    }
    status = status_map.get(e.code.value, 500)
    raise HTTPException(status_code=status, detail=e.message)


# ── Routes ──


@router.post("", response_model=ScriptResponse, status_code=201)
async def create_script(
    body: ScriptCreate,
    script_svc: ScriptService = Depends(get_script_service),
):
    """Create a new script."""
    try:
        sections_data = [s.model_dump() for s in body.sections]
        script = await script_svc.create_script(
            product_id=body.product_id,
            store_id=body.store_id,
            style=body.style,
            industry=body.industry,
            sections_data=sections_data,
        )
        return _script_to_response(script)
    except AppError as e:
        _handle_app_error(e)


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: str,
    script_svc: ScriptService = Depends(get_script_service),
):
    """Get a script by ID."""
    try:
        script = await script_svc.get_script(script_id)
        return _script_to_response(script)
    except AppError as e:
        _handle_app_error(e)


@router.put("/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: str,
    body: ScriptUpdate,
    script_svc: ScriptService = Depends(get_script_service),
):
    """Update a script."""
    try:
        sections_data = [s.model_dump() for s in body.sections] if body.sections else None
        script = await script_svc.update_script(
            script_id=script_id,
            style=body.style,
            sections_data=sections_data,
        )
        return _script_to_response(script)
    except AppError as e:
        _handle_app_error(e)


@router.delete("/{script_id}", status_code=204)
async def delete_script(
    script_id: str,
    script_svc: ScriptService = Depends(get_script_service),
):
    """Delete a script."""
    try:
        await script_svc.delete_script(script_id)
    except AppError as e:
        _handle_app_error(e)


@router.get("", response_model=dict)
async def list_scripts(
    store_id: str = Query(..., description="Store ID"),
    status: str | None = Query(None, description="Filter by status"),
    product_id: str | None = Query(None, description="Filter by product ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    script_svc: ScriptService = Depends(get_script_service),
):
    """List scripts with pagination and filtering."""
    try:
        scripts, total = await script_svc.list_scripts(
            store_id=store_id,
            status=status,
            product_id=product_id,
            page=page,
            page_size=page_size,
        )
        total_pages = (total + page_size - 1) // page_size
        return {
            "scripts": [_script_to_response(s) for s in scripts],
            "page_info": {
                "page": page,
                "page_size": page_size,
                "total_count": total,
                "total_pages": total_pages,
            },
        }
    except AppError as e:
        _handle_app_error(e)


@router.post("/generate", response_model=ScriptResponse, status_code=201)
async def generate_script(
    body: ScriptGenerate,
    script_svc: ScriptService = Depends(get_script_service),
    config: ScriptConfig = Depends(lambda: ScriptConfig()),
):
    """AI-generate a script from product info."""
    try:
        generator = AIGenerator(config)
        sections = await generator.generate_script(
            product_name=f"Product({body.product_id})",
            industry="",
            style=body.style,
            selling_points=body.highlight_selling_points or [],
            target_duration_seconds=body.target_duration_seconds or 120,
            extra_context=body.extra_context or "",
        )

        import json
        prompt_used = json.dumps(body.model_dump(), ensure_ascii=False)

        script = await script_svc.create_script(
            product_id=body.product_id,
            store_id="ai_generated",
            style=body.style,
            sections_data=sections,
        )
        script.ai_generated_prompt = prompt_used
        # Re-fetch to get updated data
        script = await script_svc.get_script(str(script.script_id))
        return _script_to_response(script)
    except AppError as e:
        _handle_app_error(e)


@router.post("/{script_id}/publish", response_model=ScriptResponse)
async def publish_version(
    script_id: str,
    body: VersionPublish,
    script_svc: ScriptService = Depends(get_script_service),
):
    """Publish a new version (snapshot current sections)."""
    try:
        script = await script_svc.publish_version(
            script_id=script_id,
            note=body.note,
        )
        return _script_to_response(script)
    except AppError as e:
        _handle_app_error(e)


@router.post("/{script_id}/rollback", response_model=ScriptResponse)
async def rollback_version(
    script_id: str,
    body: VersionRollback,
    script_svc: ScriptService = Depends(get_script_service),
):
    """Rollback to a previous version."""
    try:
        script = await script_svc.rollback_version(
            script_id=script_id,
            target_version=body.target_version,
        )
        return _script_to_response(script)
    except AppError as e:
        _handle_app_error(e)


# ── Templates ──

TEMPLATES_ROUTER = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@TEMPLATES_ROUTER.get("", response_model=dict)
async def list_templates(
    industry: str | None = Query(None),
    style: str | None = Query(None),
):
    """List built-in industry script templates."""
    try:
        svc = ScriptService.__new__(ScriptService)  # Static method, no DB needed
        templates = await svc.list_templates(industry=industry, style=style)
        return {
            "templates": [
                {
                    "template_id": t.template_id,
                    "name": t.name,
                    "industry": t.industry,
                    "style": t.style,
                    "template_sections": t.template_sections,
                    "description": t.description,
                }
                for t in templates
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Health ──

@router.get("/health", include_in_schema=False)
async def health():
    return {"status": "healthy", "service": "script-svc"}
